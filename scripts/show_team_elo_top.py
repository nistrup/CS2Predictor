#!/usr/bin/env python3
"""Show top teams for a stored Elo system, with optional recent-activity filter."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from db import create_db_engine

DEFAULT_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/cs2predictor"

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Query top teams from team_elo by system.",
)


@app.command()
def show_team_elo_top(
    system_name: Annotated[
        str,
        typer.Option(
            "--system-name",
            help="Elo system name from elo_systems.name.",
        ),
    ] = "team_elo_default",
    top_n: Annotated[
        int,
        typer.Option("--top-n", help="Number of teams to return."),
    ] = 20,
    active_window_days: Annotated[
        int,
        typer.Option(
            "--active-window-days",
            help=(
                "Require each team to have recent maps in this window. "
                "Use 0 to disable the activity window."
            ),
        ),
    ] = 90,
    min_recent_maps: Annotated[
        int,
        typer.Option(
            "--min-recent-maps",
            help="Minimum maps in the activity window (or all-time when active-window-days=0).",
        ),
    ] = 1,
    db_url: Annotated[
        str,
        typer.Option(
            "--db-url",
            help="Database URL. Defaults to the local cs2predictor postgres instance.",
        ),
    ] = DEFAULT_DB_URL,
) -> None:
    """Print top teams by latest Elo, optionally filtering stale/inactive teams."""
    if top_n <= 0:
        raise typer.BadParameter("--top-n must be greater than 0")
    if active_window_days < 0:
        raise typer.BadParameter("--active-window-days must be >= 0")
    if min_recent_maps < 0:
        raise typer.BadParameter("--min-recent-maps must be >= 0")

    engine = create_db_engine(db_url)

    statement = text(
        """
        WITH target_system AS (
            SELECT id
            FROM elo_systems
            WHERE name = :system_name
            ORDER BY id DESC
            LIMIT 1
        ),
        latest_per_team AS (
            SELECT
                te.team_id,
                te.post_elo,
                te.event_time,
                te.map_id,
                ROW_NUMBER() OVER (
                    PARTITION BY te.team_id
                    ORDER BY te.event_time DESC, te.map_id DESC, te.id DESC
                ) AS rn
            FROM team_elo te
            JOIN target_system ts ON ts.id = te.elo_system_id
        ),
        recent_activity AS (
            SELECT
                te.team_id,
                COUNT(*)::int AS recent_maps
            FROM team_elo te
            JOIN target_system ts ON ts.id = te.elo_system_id
            WHERE (
                :active_window_days = 0
                OR te.event_time >= (
                    CURRENT_TIMESTAMP - make_interval(days => :active_window_days)
                )
            )
            GROUP BY te.team_id
        )
        SELECT
            t.name AS team_name,
            lpt.post_elo,
            lpt.event_time,
            COALESCE(ra.recent_maps, 0) AS recent_maps
        FROM latest_per_team lpt
        JOIN teams t ON t.id = lpt.team_id
        LEFT JOIN recent_activity ra ON ra.team_id = lpt.team_id
        WHERE
            lpt.rn = 1
            AND COALESCE(ra.recent_maps, 0) >= :min_recent_maps
        ORDER BY lpt.post_elo DESC
        LIMIT :top_n
        """
    )

    with engine.connect() as connection:
        rows = connection.execute(
            statement,
            {
                "system_name": system_name,
                "top_n": top_n,
                "active_window_days": active_window_days,
                "min_recent_maps": min_recent_maps,
            },
        ).fetchall()

    if not rows:
        typer.echo(
            f"No rows found for system '{system_name}' with "
            f"active_window_days={active_window_days} and min_recent_maps={min_recent_maps}."
        )
        return

    typer.echo(
        f"system={system_name} top_n={top_n} "
        f"active_window_days={active_window_days} min_recent_maps={min_recent_maps}"
    )
    for index, row in enumerate(rows, start=1):
        typer.echo(
            f"{index:2d}. {row.team_name:<20} "
            f"elo={row.post_elo:8.2f} recent_maps={row.recent_maps:3d} "
            f"last_event={row.event_time}"
        )


if __name__ == "__main__":
    app()
