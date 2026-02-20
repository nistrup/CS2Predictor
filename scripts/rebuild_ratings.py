#!/usr/bin/env python3
"""Unified CLI for rating system rebuilds across algorithm/granularity/subject."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from db import create_db_engine, create_session_factory
from domain.pipeline import rebuild_single_system
from domain.protocol import Granularity, Subject
from domain.registry import RatingSystemDescriptor, get, get_all

DEFAULT_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/cs2predictor"

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Unified rating rebuild commands.",
)


def rebuild_registered_system(
    *,
    algorithm: str,
    granularity: Granularity,
    subject: Subject,
    db_url: str,
    config_dir: Path | None,
    config_name: str | None,
    batch_size: int,
    dry_run: bool,
) -> None:
    """Rebuild one registered system for all or one config file."""
    if batch_size <= 0:
        raise typer.BadParameter("--batch-size must be greater than 0")

    descriptor = get(algorithm, granularity, subject)
    target_config_dir = config_dir or descriptor.config_dir
    configs = descriptor.load_configs(target_config_dir)

    if config_name is not None:
        configs = [config for config in configs if config.file_path.name == config_name]
        if not configs:
            raise typer.BadParameter(
                f"No config named '{config_name}' found in {target_config_dir}",
                param_hint="--config-name",
            )

    engine = create_db_engine(db_url)
    descriptor.ensure_schema(engine)
    session_factory = create_session_factory(engine)

    typer.echo(
        f"loaded_configs={len(configs)} "
        f"config_dir={target_config_dir} "
        f"algorithm={descriptor.algorithm} "
        f"granularity={descriptor.granularity.value} "
        f"subject={descriptor.subject.value}"
    )

    for config in configs:
        rebuild_single_system(
            session_factory=session_factory,
            descriptor=descriptor,
            system_config=config,
            batch_size=batch_size,
            dry_run=dry_run,
            echo=typer.echo,
        )


@app.command()
def rebuild(
    algorithm: Annotated[
        str,
        typer.Argument(help="Algorithm key (elo, glicko2, openskill)."),
    ],
    granularity: Annotated[
        Granularity,
        typer.Option(
            "--granularity",
            help="Rating granularity (map).",
        ),
    ] = Granularity.MAP,
    subject: Annotated[
        Subject,
        typer.Option(
            "--subject",
            help="Rated subject (team, player).",
        ),
    ] = Subject.TEAM,
    db_url: Annotated[
        str,
        typer.Option(
            "--db-url",
            help="Database URL. Defaults to the local cs2predictor postgres instance.",
        ),
    ] = DEFAULT_DB_URL,
    config_dir: Annotated[
        Path | None,
        typer.Option(
            "--config-dir",
            help="Optional override for descriptor config directory.",
        ),
    ] = None,
    config_name: Annotated[
        str | None,
        typer.Option(
            "--config-name",
            help="Optional single config filename (for example: default.toml).",
        ),
    ] = None,
    batch_size: Annotated[
        int,
        typer.Option("--batch-size", help="Batch size for inserting rating events."),
    ] = 5000,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Compute ratings without writing events."),
    ] = False,
) -> None:
    """Rebuild one registered rating system."""
    rebuild_registered_system(
        algorithm=algorithm,
        granularity=granularity,
        subject=subject,
        db_url=db_url,
        config_dir=config_dir,
        config_name=config_name,
        batch_size=batch_size,
        dry_run=dry_run,
    )


@app.command()
def list_systems() -> None:
    """Print all registered (algorithm, granularity, subject) combinations."""
    descriptors: list[RatingSystemDescriptor] = get_all()
    if not descriptors:
        typer.echo("no registered systems")
        return

    for descriptor in descriptors:
        typer.echo(
            f"{descriptor.algorithm}/{descriptor.granularity.value}/{descriptor.subject.value} "
            f"config_dir={descriptor.config_dir}"
        )


if __name__ == "__main__":
    app()
