#!/usr/bin/env python3
"""Run default config rebuilds for Elo, Glicko-2, and OpenSkill."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, Callable

import typer

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rebuild_team_elo import (
    DEFAULT_CONFIG_DIR as DEFAULT_ELO_CONFIG_DIR,
    DEFAULT_DB_URL,
    rebuild_team_elo,
)
from rebuild_team_glicko2 import (
    DEFAULT_CONFIG_DIR as DEFAULT_GLICKO2_CONFIG_DIR,
    rebuild_team_glicko2,
)
from rebuild_team_openskill import (
    DEFAULT_CONFIG_DIR as DEFAULT_OPENSKILL_CONFIG_DIR,
    rebuild_team_openskill,
)

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Run default config rebuilds for all rating systems.",
)


def _run_system(
    *,
    label: str,
    rebuild_fn: Callable[..., None],
    db_url: str,
    config_dir: Path,
    config_name: str,
    batch_size: int,
    dry_run: bool,
) -> None:
    typer.echo(f"==> starting {label} (config={config_name})")
    rebuild_fn(
        db_url=db_url,
        config_dir=config_dir,
        config_name=config_name,
        batch_size=batch_size,
        dry_run=dry_run,
    )
    typer.echo(f"<== completed {label}")


@app.command()
def rebuild_all_default_ratings(
    db_url: Annotated[
        str,
        typer.Option(
            "--db-url",
            help="Database URL. Defaults to the local cs2predictor postgres instance.",
        ),
    ] = DEFAULT_DB_URL,
    config_name: Annotated[
        str,
        typer.Option(
            "--config-name",
            help="Config filename to run in each system config directory.",
        ),
    ] = "default.toml",
    elo_config_dir: Annotated[
        Path,
        typer.Option(
            "--elo-config-dir",
            help="Directory containing Elo system config files.",
        ),
    ] = DEFAULT_ELO_CONFIG_DIR,
    glicko2_config_dir: Annotated[
        Path,
        typer.Option(
            "--glicko2-config-dir",
            help="Directory containing Glicko-2 system config files.",
        ),
    ] = DEFAULT_GLICKO2_CONFIG_DIR,
    openskill_config_dir: Annotated[
        Path,
        typer.Option(
            "--openskill-config-dir",
            help="Directory containing OpenSkill system config files.",
        ),
    ] = DEFAULT_OPENSKILL_CONFIG_DIR,
    batch_size: Annotated[
        int,
        typer.Option("--batch-size", help="Batch size for inserting rating events."),
    ] = 5000,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Compute all systems without writing rating events.",
        ),
    ] = False,
    continue_on_error: Annotated[
        bool,
        typer.Option(
            "--continue-on-error",
            help="Continue running remaining systems if one system fails.",
        ),
    ] = False,
) -> None:
    """Recompute all rating systems for one config filename (default: default.toml)."""
    if batch_size <= 0:
        raise typer.BadParameter("--batch-size must be greater than 0")

    failures: list[str] = []

    for label, rebuild_fn, config_dir in [
        ("Elo", rebuild_team_elo, elo_config_dir),
        ("Glicko-2", rebuild_team_glicko2, glicko2_config_dir),
        ("OpenSkill", rebuild_team_openskill, openskill_config_dir),
    ]:
        try:
            _run_system(
                label=label,
                rebuild_fn=rebuild_fn,
                db_url=db_url,
                config_dir=config_dir,
                config_name=config_name,
                batch_size=batch_size,
                dry_run=dry_run,
            )
        except Exception as exc:
            message = f"{label} failed: {exc}"
            failures.append(message)
            typer.echo(message, err=True)
            if not continue_on_error:
                raise typer.Exit(code=1) from exc

    if failures:
        typer.echo("completed with errors:", err=True)
        for failure in failures:
            typer.echo(f"- {failure}", err=True)
        raise typer.Exit(code=1)

    typer.echo("all systems completed successfully")


if __name__ == "__main__":
    app()
