#!/usr/bin/env python3
"""Run default config rebuilds for all registered rating systems."""

from __future__ import annotations

import sys
from typing import Annotated

import typer

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from domain.ratings.protocol import Granularity, Subject
from domain.ratings.registry import get_all
from rebuild_ratings import DEFAULT_DB_URL, rebuild_registered_system

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Run default config rebuilds for all registered rating systems.",
)


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
    include_match_elo: Annotated[
        bool,
        typer.Option(
            "--include-match-elo/--skip-match-elo",
            help="Include match-level Elo rebuild.",
        ),
    ] = True,
    include_map_elo: Annotated[
        bool,
        typer.Option(
            "--include-map-elo/--skip-map-elo",
            help="Include map-specific Elo rebuild.",
        ),
    ] = True,
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
    """Recompute all registered team-level rating systems for one config filename."""
    if batch_size <= 0:
        raise typer.BadParameter("--batch-size must be greater than 0")

    failures: list[str] = []

    for descriptor in get_all():
        if descriptor.subject is not Subject.TEAM:
            continue

        if (
            descriptor.algorithm == "elo"
            and descriptor.granularity is Granularity.MATCH
            and not include_match_elo
        ):
            continue

        if (
            descriptor.algorithm == "elo"
            and descriptor.granularity is Granularity.MAP_SPECIFIC
            and not include_map_elo
        ):
            continue

        label = (
            f"{descriptor.algorithm}/"
            f"{descriptor.granularity.value}/"
            f"{descriptor.subject.value}"
        )
        typer.echo(f"==> starting {label} (config={config_name})")
        try:
            rebuild_registered_system(
                algorithm=descriptor.algorithm,
                granularity=descriptor.granularity,
                subject=descriptor.subject,
                db_url=db_url,
                config_dir=descriptor.config_dir,
                config_name=config_name,
                batch_size=batch_size,
                dry_run=dry_run,
            )
            typer.echo(f"<== completed {label}")
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
