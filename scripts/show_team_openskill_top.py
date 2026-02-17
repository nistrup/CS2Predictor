#!/usr/bin/env python3
"""Show top teams for a stored OpenSkill system, with optional activity filter."""

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
    help="Query top teams from team_openskill by system.",
)


@app.command()
def show_team_openskill_top(
    system_name: Annotated[
        str,
        typer.Option(
            "--system-name",
            help="OpenSkill system name from openskill_systems.name.",
        ),
    ] = "team_openskill_default",
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
    """Print top teams by latest OpenSkill conservative rating, with optional activity filter."""
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
            FROM openskill_systems
            WHERE name = :system_name
            ORDER BY id DESC
            LIMIT 1
        ),
        latest_per_team AS (
            SELECT
                tos.team_id,
                tos.post_mu,
                tos.post_sigma,
                tos.post_ordinal,
                tos.event_time,
                tos.map_id,
                ROW_NUMBER() OVER (
                    PARTITION BY tos.team_id
                    ORDER BY tos.event_time DESC, tos.map_id DESC, tos.id DESC
                ) AS rn
            FROM team_openskill tos
            JOIN target_system ts ON ts.id = tos.openskill_system_id
        ),
        recent_activity AS (
            SELECT
                tos.team_id,
                COUNT(*)::int AS recent_maps
            FROM team_openskill tos
            JOIN target_system ts ON ts.id = tos.openskill_system_id
            WHERE (
                :active_window_days = 0
                OR tos.event_time >= (
                    CURRENT_TIMESTAMP - make_interval(days => :active_window_days)
                )
            )
            GROUP BY tos.team_id
        )
        SELECT
            t.name AS team_name,
            lpt.post_mu,
            lpt.post_sigma,
            lpt.post_ordinal,
            lpt.event_time,
            COALESCE(ra.recent_maps, 0) AS recent_maps
        FROM latest_per_team lpt
        JOIN teams t ON t.id = lpt.team_id
        LEFT JOIN recent_activity ra ON ra.team_id = lpt.team_id
        WHERE
            lpt.rn = 1
            AND COALESCE(ra.recent_maps, 0) >= :min_recent_maps
        ORDER BY lpt.post_ordinal DESC
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
            f"ordinal={row.post_ordinal:8.3f} mu={row.post_mu:7.3f} sigma={row.post_sigma:7.3f} "
            f"recent_maps={row.recent_maps:3d} last_event={row.event_time}"
        )


if __name__ == "__main__":
    app()
