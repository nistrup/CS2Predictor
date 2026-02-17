#!/usr/bin/env python3
"""Rebuild map-level team Elo history into the team_elo table."""

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
from elo.team_elo import EloParameters, TeamEloCalculator, TeamEloEvent
from repositories.team_elo_repository import (
    count_tracked_teams,
    ensure_team_elo_schema,
    fetch_map_results,
    insert_team_elo_events,
    truncate_team_elo,
)

DEFAULT_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/cs2predictor"

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Team Elo jobs.",
)


def _flush_batch(batch: list[TeamEloEvent]) -> list[TeamEloEvent]:
    payload = batch[:]
    batch.clear()
    return payload


@app.command("rebuild")
def rebuild_team_elo(
    db_url: Annotated[
        str,
        typer.Option(
            "--db-url",
            help=(
                "Database URL. Defaults to the local cs2predictor postgres instance."
            ),
        ),
    ] = DEFAULT_DB_URL,
    initial_elo: Annotated[float, typer.Option("--initial-elo")] = 1500.0,
    k_factor: Annotated[float, typer.Option("--k-factor")] = 20.0,
    scale_factor: Annotated[float, typer.Option("--scale-factor")] = 400.0,
    batch_size: Annotated[
        int,
        typer.Option("--batch-size", help="Batch size for inserting Elo events."),
    ] = 5000,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Compute Elo without writing to team_elo."),
    ] = False,
) -> None:
    """Recompute team Elo from maps in chronological order."""
    if batch_size <= 0:
        raise typer.BadParameter("--batch-size must be greater than 0")

    params = EloParameters(
        initial_elo=initial_elo,
        k_factor=k_factor,
        scale_factor=scale_factor,
    )

    engine = create_db_engine(db_url)
    ensure_team_elo_schema(engine)
    session_factory = create_session_factory(engine)

    inserted_events = 0
    with session_factory() as session:
        map_results = fetch_map_results(session)
        total_maps = len(map_results)
        calculator = TeamEloCalculator(params=params)

        if dry_run:
            for map_result in map_results:
                calculator.process_map(map_result)
            typer.echo(
                f"[dry-run] processed_maps={total_maps} "
                f"tracked_teams={calculator.tracked_team_count()}"
            )
            return

        buffered_events: list[TeamEloEvent] = []
        with session.begin():
            truncate_team_elo(session)

            for index, map_result in enumerate(map_results, start=1):
                team1_event, team2_event = calculator.process_map(map_result)
                buffered_events.append(team1_event)
                buffered_events.append(team2_event)

                if len(buffered_events) >= batch_size:
                    payload = _flush_batch(buffered_events)
                    insert_team_elo_events(session, payload)
                    inserted_events += len(payload)

                if index % 10_000 == 0:
                    typer.echo(f"processed_maps={index}/{total_maps}")

            if buffered_events:
                payload = _flush_batch(buffered_events)
                insert_team_elo_events(session, payload)
                inserted_events += len(payload)

        tracked_teams = count_tracked_teams(session)
        typer.echo(
            "completed "
            f"processed_maps={total_maps} "
            f"inserted_events={inserted_events} "
            f"tracked_teams={tracked_teams}"
        )


if __name__ == "__main__":
    app()
