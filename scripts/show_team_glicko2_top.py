#!/usr/bin/env python3
"""Show top teams for a stored Glicko-2 system, with optional activity filter."""

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
    help="Query top teams from team_glicko2 by system.",
)


@app.command()
def show_team_glicko2_top(
    system_name: Annotated[
        str,
        typer.Option(
            "--system-name",
            help="Glicko-2 system name from glicko2_systems.name.",
        ),
    ] = "team_glicko2_default",
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
    """Print top teams by latest Glicko-2 rating, with optional activity filter."""
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
            FROM glicko2_systems
            WHERE name = :system_name
            ORDER BY id DESC
            LIMIT 1
        ),
        latest_per_team AS (
            SELECT
                tg.team_id,
                tg.post_rating,
                tg.post_rd,
                tg.post_volatility,
                tg.event_time,
                tg.map_id,
                ROW_NUMBER() OVER (
                    PARTITION BY tg.team_id
                    ORDER BY tg.event_time DESC, tg.map_id DESC, tg.id DESC
                ) AS rn
            FROM team_glicko2 tg
            JOIN target_system ts ON ts.id = tg.glicko2_system_id
        ),
        recent_activity AS (
            SELECT
                tg.team_id,
                COUNT(*)::int AS recent_maps
            FROM team_glicko2 tg
            JOIN target_system ts ON ts.id = tg.glicko2_system_id
            WHERE (
                :active_window_days = 0
                OR tg.event_time >= (
                    CURRENT_TIMESTAMP - make_interval(days => :active_window_days)
                )
            )
            GROUP BY tg.team_id
        )
        SELECT
            t.name AS team_name,
            lpt.post_rating,
            lpt.post_rd,
            lpt.post_volatility,
            lpt.event_time,
            COALESCE(ra.recent_maps, 0) AS recent_maps
        FROM latest_per_team lpt
        JOIN teams t ON t.id = lpt.team_id
        LEFT JOIN recent_activity ra ON ra.team_id = lpt.team_id
        WHERE
            lpt.rn = 1
            AND COALESCE(ra.recent_maps, 0) >= :min_recent_maps
        ORDER BY lpt.post_rating DESC
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
            f"rating={row.post_rating:8.2f} rd={row.post_rd:7.2f} vol={row.post_volatility:7.5f} "
            f"recent_maps={row.recent_maps:3d} last_event={row.event_time}"
        )


if __name__ == "__main__":
    app()
