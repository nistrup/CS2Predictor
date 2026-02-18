#!/usr/bin/env python3
"""Show top teams for a stored rating system, with optional activity filter."""

from __future__ import annotations

import sys
from dataclasses import dataclass
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


@dataclass(frozen=True)
class AlgorithmSpec:
    algorithm: str
    default_system_name: str
    systems_table: str
    events_table: str
    events_system_id_column: str
    primary_column: str
    primary_label: str
    extra_columns: tuple[tuple[str, str], ...]


ALGORITHM_SPECS = {
    "elo": AlgorithmSpec(
        algorithm="elo",
        default_system_name="team_elo_default",
        systems_table="elo_systems",
        events_table="team_elo",
        events_system_id_column="elo_system_id",
        primary_column="post_elo",
        primary_label="elo",
        extra_columns=(),
    ),
    "glicko2": AlgorithmSpec(
        algorithm="glicko2",
        default_system_name="team_glicko2_default",
        systems_table="glicko2_systems",
        events_table="team_glicko2",
        events_system_id_column="glicko2_system_id",
        primary_column="post_rating",
        primary_label="rating",
        extra_columns=(("post_rd", "post_rd"), ("post_volatility", "post_volatility")),
    ),
    "openskill": AlgorithmSpec(
        algorithm="openskill",
        default_system_name="team_openskill_default",
        systems_table="openskill_systems",
        events_table="team_openskill",
        events_system_id_column="openskill_system_id",
        primary_column="post_ordinal",
        primary_label="ordinal",
        extra_columns=(("post_mu", "post_mu"), ("post_sigma", "post_sigma")),
    ),
}

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Query top teams from a selected algorithm/system.",
)


def _get_algorithm_spec(algorithm: str) -> AlgorithmSpec:
    try:
        return ALGORITHM_SPECS[algorithm.lower()]
    except KeyError as exc:
        available = ", ".join(sorted(ALGORITHM_SPECS.keys()))
        raise typer.BadParameter(
            f"Unsupported algorithm '{algorithm}'. Choose one of: {available}.",
            param_hint="algorithm",
        ) from exc


def _build_statement(spec: AlgorithmSpec):
    latest_extra_columns = "".join(
        f",\n                te.{column_name} AS {alias}"
        for column_name, alias in spec.extra_columns
    )
    select_extra_columns = "".join(
        f",\n            lpt.{alias}"
        for _, alias in spec.extra_columns
    )

    return text(
        f"""
        WITH target_system AS (
            SELECT id
            FROM {spec.systems_table}
            WHERE name = :system_name
            ORDER BY id DESC
            LIMIT 1
        ),
        latest_per_team AS (
            SELECT
                te.team_id,
                te.{spec.primary_column} AS primary_value{latest_extra_columns},
                te.event_time,
                te.map_id,
                ROW_NUMBER() OVER (
                    PARTITION BY te.team_id
                    ORDER BY te.event_time DESC, te.map_id DESC, te.id DESC
                ) AS rn
            FROM {spec.events_table} te
            JOIN target_system ts ON ts.id = te.{spec.events_system_id_column}
        ),
        recent_activity AS (
            SELECT
                te.team_id,
                COUNT(*)::int AS recent_maps
            FROM {spec.events_table} te
            JOIN target_system ts ON ts.id = te.{spec.events_system_id_column}
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
            lpt.primary_value{select_extra_columns},
            lpt.event_time,
            COALESCE(ra.recent_maps, 0) AS recent_maps
        FROM latest_per_team lpt
        JOIN teams t ON t.id = lpt.team_id
        LEFT JOIN recent_activity ra ON ra.team_id = lpt.team_id
        WHERE
            lpt.rn = 1
            AND COALESCE(ra.recent_maps, 0) >= :min_recent_maps
        ORDER BY lpt.primary_value DESC
        LIMIT :top_n
        """
    )


def _render_row(index: int, row, spec: AlgorithmSpec) -> str:
    if spec.algorithm == "elo":
        return (
            f"{index:2d}. {row.team_name:<20} "
            f"elo={row.primary_value:8.2f} recent_maps={row.recent_maps:3d} "
            f"last_event={row.event_time}"
        )

    if spec.algorithm == "glicko2":
        return (
            f"{index:2d}. {row.team_name:<20} "
            f"rating={row.primary_value:8.2f} rd={row.post_rd:7.2f} vol={row.post_volatility:7.5f} "
            f"recent_maps={row.recent_maps:3d} last_event={row.event_time}"
        )

    return (
        f"{index:2d}. {row.team_name:<20} "
        f"ordinal={row.primary_value:8.3f} mu={row.post_mu:7.3f} sigma={row.post_sigma:7.3f} "
        f"recent_maps={row.recent_maps:3d} last_event={row.event_time}"
    )


@app.command()
def show_team_top(
    algorithm: Annotated[
        str,
        typer.Argument(help="Algorithm key (elo, glicko2, openskill)."),
    ],
    system_name: Annotated[
        str | None,
        typer.Option(
            "--system-name",
            help="System name in the selected algorithm's systems table.",
        ),
    ] = None,
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
    """Print top teams by latest rating, with optional activity filtering."""
    if top_n <= 0:
        raise typer.BadParameter("--top-n must be greater than 0")
    if active_window_days < 0:
        raise typer.BadParameter("--active-window-days must be >= 0")
    if min_recent_maps < 0:
        raise typer.BadParameter("--min-recent-maps must be >= 0")

    spec = _get_algorithm_spec(algorithm)
    resolved_system_name = system_name or spec.default_system_name

    engine = create_db_engine(db_url)
    statement = _build_statement(spec)

    with engine.connect() as connection:
        rows = connection.execute(
            statement,
            {
                "system_name": resolved_system_name,
                "top_n": top_n,
                "active_window_days": active_window_days,
                "min_recent_maps": min_recent_maps,
            },
        ).fetchall()

    if not rows:
        typer.echo(
            f"No rows found for algorithm='{spec.algorithm}' system='{resolved_system_name}' with "
            f"active_window_days={active_window_days} and min_recent_maps={min_recent_maps}."
        )
        return

    typer.echo(
        f"algorithm={spec.algorithm} system={resolved_system_name} top_n={top_n} "
        f"active_window_days={active_window_days} min_recent_maps={min_recent_maps} "
        f"rank_by={spec.primary_label}"
    )
    for index, row in enumerate(rows, start=1):
        typer.echo(_render_row(index, row, spec))


if __name__ == "__main__":
    app()
