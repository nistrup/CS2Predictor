#!/usr/bin/env python3
"""Rebuild map-level team Glicko-2 history into the team_glicko2 table."""

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
from domain.ratings.glicko2.config import Glicko2SystemConfig, load_glicko2_system_configs
from domain.ratings.glicko2.calculator import TeamGlicko2Calculator, TeamGlicko2Event
from repositories.ratings.glicko2.repository import (
    count_tracked_teams,
    delete_team_glicko2_for_system,
    ensure_team_glicko2_schema,
    fetch_map_results,
    insert_team_glicko2_events,
    upsert_glicko2_system,
)

DEFAULT_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/cs2predictor"
DEFAULT_CONFIG_DIR = ROOT_DIR / "configs" / "ratings" / "glicko2"

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Team Glicko-2 jobs.",
)


def _flush_batch(batch: list[TeamGlicko2Event]) -> list[TeamGlicko2Event]:
    payload = batch[:]
    batch.clear()
    return payload


def _run_single_system(
    *,
    session_factory,
    system_config: Glicko2SystemConfig,
    batch_size: int,
    dry_run: bool,
) -> None:
    inserted_events = 0
    with session_factory() as session:
        lookback = None if system_config.lookback_days == 0 else system_config.lookback_days
        map_results = fetch_map_results(session, lookback_days=lookback)
        total_maps = len(map_results)
        calculator = TeamGlicko2Calculator(params=system_config.parameters)

        glicko2_system = upsert_glicko2_system(
            session,
            name=system_config.name,
            description=system_config.description,
            config_json=system_config.as_config_json(),
        )
        glicko2_system_id = glicko2_system.id

        if dry_run:
            for map_result in map_results:
                calculator.process_map(map_result)
            typer.echo(
                f"[dry-run] config={system_config.file_path.name} "
                f"glicko2_system={system_config.name} "
                f"processed_maps={total_maps} "
                f"tracked_teams={calculator.tracked_team_count()}"
            )
            session.rollback()
            return

        buffered_events: list[TeamGlicko2Event] = []
        try:
            delete_team_glicko2_for_system(session, glicko2_system_id)

            for index, map_result in enumerate(map_results, start=1):
                team1_event, team2_event = calculator.process_map(map_result)
                buffered_events.append(team1_event)
                buffered_events.append(team2_event)

                if len(buffered_events) >= batch_size:
                    payload = _flush_batch(buffered_events)
                    insert_team_glicko2_events(session, payload, glicko2_system_id=glicko2_system_id)
                    inserted_events += len(payload)

                if index % 10_000 == 0:
                    typer.echo(
                        f"config={system_config.file_path.name} "
                        f"processed_maps={index}/{total_maps}"
                    )

            if buffered_events:
                payload = _flush_batch(buffered_events)
                insert_team_glicko2_events(session, payload, glicko2_system_id=glicko2_system_id)
                inserted_events += len(payload)

            session.commit()
        except Exception:
            session.rollback()
            raise

        tracked_teams = count_tracked_teams(session, glicko2_system_id=glicko2_system_id)
        typer.echo(
            "completed "
            f"config={system_config.file_path.name} "
            f"glicko2_system={system_config.name} "
            f"glicko2_system_id={glicko2_system_id} "
            f"processed_maps={total_maps} "
            f"inserted_events={inserted_events} "
            f"tracked_teams={tracked_teams}"
        )


@app.command()
def rebuild_team_glicko2(
    db_url: Annotated[
        str,
        typer.Option(
            "--db-url",
            help=(
                "Database URL. Defaults to the local cs2predictor postgres instance."
            ),
        ),
    ] = DEFAULT_DB_URL,
    config_dir: Annotated[
        Path,
        typer.Option(
            "--config-dir",
            help="Directory containing Glicko-2 system TOML config files.",
        ),
    ] = DEFAULT_CONFIG_DIR,
    config_name: Annotated[
        str | None,
        typer.Option(
            "--config-name",
            help="Optional single config filename (for example: default.toml).",
        ),
    ] = None,
    batch_size: Annotated[
        int,
        typer.Option("--batch-size", help="Batch size for inserting Glicko-2 events."),
    ] = 5000,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Compute Glicko-2 without writing to team_glicko2."),
    ] = False,
) -> None:
    """Recompute team Glicko-2 for all configs in a directory."""
    if batch_size <= 0:
        raise typer.BadParameter("--batch-size must be greater than 0")

    configs = load_glicko2_system_configs(config_dir)
    if config_name is not None:
        configs = [config for config in configs if config.file_path.name == config_name]
        if not configs:
            raise typer.BadParameter(
                f"No config named '{config_name}' found in {config_dir}",
                param_hint="--config-name",
            )

    engine = create_db_engine(db_url)
    ensure_team_glicko2_schema(engine)
    session_factory = create_session_factory(engine)

    typer.echo(f"loaded_configs={len(configs)} config_dir={config_dir}")
    for config in configs:
        _run_single_system(
            session_factory=session_factory,
            system_config=config,
            batch_size=batch_size,
            dry_run=dry_run,
        )


if __name__ == "__main__":
    app()
