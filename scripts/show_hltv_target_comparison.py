#!/usr/bin/env python3
"""Show side-by-side HLTV target ranks vs Elo/Glicko-2/OpenSkill ranks."""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Annotated, Any

import typer
from sqlalchemy import text

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from db import create_db_engine

DEFAULT_DB_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/cs2predictor"
DEFAULT_TARGET_PATH = ROOT_DIR / "configs" / "targets" / "hltv_world_2026-02-16_top20.json"

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Compare target ranks from JSON against latest Elo/Glicko-2/OpenSkill ranks.",
)


@dataclass(frozen=True)
class TargetTeam:
    rank: int
    name: str


@dataclass(frozen=True)
class ComparisonRow:
    team_name: str
    hltv_rank: int
    elo_rank: int | None
    glicko2_rank: int | None
    openskill_rank: int | None


def _load_target_teams(target_path: Path, top_n: int) -> list[TargetTeam]:
    payload = json.loads(target_path.read_text())
    teams = payload.get("teams")
    if not isinstance(teams, list):
        raise typer.BadParameter(
            f"Target file '{target_path}' does not contain a valid 'teams' list.",
            param_hint="--target-path",
        )

    parsed: list[TargetTeam] = []
    for item in teams:
        if not isinstance(item, dict):
            continue
        rank = item.get("rank")
        name = item.get("name")
        if not isinstance(rank, int) or not isinstance(name, str):
            continue
        parsed.append(TargetTeam(rank=rank, name=name.strip()))

    parsed.sort(key=lambda team: team.rank)
    return parsed[:top_n]


def _fetch_rank_rows(
    *,
    connection,
    elo_system_name: str,
    glicko2_system_name: str,
    openskill_system_name: str,
) -> list[dict[str, Any]]:
    statement = text(
        """
        WITH elo_system AS (
            SELECT id
            FROM rating_systems
            WHERE
                name = :elo_system_name
                AND algorithm = 'elo'
                AND granularity = 'map'
                AND subject = 'team'
            ORDER BY id DESC
            LIMIT 1
        ),
        glicko2_system AS (
            SELECT id
            FROM rating_systems
            WHERE
                name = :glicko2_system_name
                AND algorithm = 'glicko2'
                AND granularity = 'map'
                AND subject = 'team'
            ORDER BY id DESC
            LIMIT 1
        ),
        openskill_system AS (
            SELECT id
            FROM rating_systems
            WHERE
                name = :openskill_system_name
                AND algorithm = 'openskill'
                AND granularity = 'map'
                AND subject = 'team'
            ORDER BY id DESC
            LIMIT 1
        ),
        elo_latest AS (
            SELECT
                tr.team_id,
                tr.post_ranking,
                tr.event_time,
                ROW_NUMBER() OVER (
                    PARTITION BY tr.team_id
                    ORDER BY tr.event_time DESC, tr.map_id DESC, tr.id DESC
                ) AS rn
            FROM team_ratings tr
            JOIN elo_system es ON es.id = tr.rating_system_id
        ),
        elo_ranked AS (
            SELECT
                team_id,
                ROW_NUMBER() OVER (ORDER BY post_ranking DESC, team_id) AS elo_rank,
                event_time AS elo_last_event
            FROM elo_latest
            WHERE rn = 1
        ),
        glicko2_latest AS (
            SELECT
                tr.team_id,
                tr.post_ranking,
                tr.event_time,
                ROW_NUMBER() OVER (
                    PARTITION BY tr.team_id
                    ORDER BY tr.event_time DESC, tr.map_id DESC, tr.id DESC
                ) AS rn
            FROM team_ratings tr
            JOIN glicko2_system gs ON gs.id = tr.rating_system_id
        ),
        glicko2_ranked AS (
            SELECT
                team_id,
                ROW_NUMBER() OVER (ORDER BY post_ranking DESC, team_id) AS glicko2_rank,
                event_time AS glicko2_last_event
            FROM glicko2_latest
            WHERE rn = 1
        ),
        openskill_latest AS (
            SELECT
                tr.team_id,
                tr.post_ranking,
                tr.event_time,
                ROW_NUMBER() OVER (
                    PARTITION BY tr.team_id
                    ORDER BY tr.event_time DESC, tr.map_id DESC, tr.id DESC
                ) AS rn
            FROM team_ratings tr
            JOIN openskill_system os ON os.id = tr.rating_system_id
        ),
        openskill_ranked AS (
            SELECT
                team_id,
                ROW_NUMBER() OVER (ORDER BY post_ranking DESC, team_id) AS openskill_rank,
                event_time AS openskill_last_event
            FROM openskill_latest
            WHERE rn = 1
        )
        SELECT
            t.id AS team_id,
            t.name AS team_name,
            er.elo_rank,
            gr.glicko2_rank,
            orr.openskill_rank,
            er.elo_last_event,
            gr.glicko2_last_event,
            orr.openskill_last_event
        FROM teams t
        LEFT JOIN elo_ranked er ON er.team_id = t.id
        LEFT JOIN glicko2_ranked gr ON gr.team_id = t.id
        LEFT JOIN openskill_ranked orr ON orr.team_id = t.id
        """
    )

    rows = connection.execute(
        statement,
        {
            "elo_system_name": elo_system_name,
            "glicko2_system_name": glicko2_system_name,
            "openskill_system_name": openskill_system_name,
        },
    ).mappings()
    return [dict(row) for row in rows]


def _pick_best_candidate(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not candidates:
        return None

    best_candidate: dict[str, Any] | None = None
    best_present = -1
    best_avg_rank = float("inf")
    best_latest_event = datetime.min
    best_team_id = 0

    for candidate in candidates:
        ranks = [
            candidate.get("elo_rank"),
            candidate.get("glicko2_rank"),
            candidate.get("openskill_rank"),
        ]
        present = sum(rank is not None for rank in ranks)
        avg_rank = (
            sum(float(rank) for rank in ranks if rank is not None) / present
            if present > 0
            else float("inf")
        )

        timestamps = [
            candidate.get("elo_last_event"),
            candidate.get("glicko2_last_event"),
            candidate.get("openskill_last_event"),
        ]
        latest_event = max(
            (timestamp for timestamp in timestamps if isinstance(timestamp, datetime)),
            default=datetime.min,
        )
        team_id = int(candidate.get("team_id") or 0)

        if best_candidate is None:
            best_candidate = candidate
            best_present = present
            best_avg_rank = avg_rank
            best_latest_event = latest_event
            best_team_id = team_id
            continue

        if present > best_present:
            better = True
        elif present < best_present:
            better = False
        elif avg_rank < best_avg_rank:
            better = True
        elif avg_rank > best_avg_rank:
            better = False
        elif latest_event > best_latest_event:
            better = True
        elif latest_event < best_latest_event:
            better = False
        else:
            better = team_id < best_team_id

        if better:
            best_candidate = candidate
            best_present = present
            best_avg_rank = avg_rank
            best_latest_event = latest_event
            best_team_id = team_id

    return best_candidate


def _mae(actual: list[int], predicted: list[int]) -> float:
    return mean(abs(a - p) for a, p in zip(actual, predicted))


def _rmse(actual: list[int], predicted: list[int]) -> float:
    return math.sqrt(mean((a - p) ** 2 for a, p in zip(actual, predicted)))


def _pearson(actual: list[int], predicted: list[int]) -> float:
    mean_actual = mean(actual)
    mean_predicted = mean(predicted)

    numerator = sum(
        (a - mean_actual) * (p - mean_predicted)
        for a, p in zip(actual, predicted)
    )
    denominator_a = math.sqrt(sum((a - mean_actual) ** 2 for a in actual))
    denominator_b = math.sqrt(sum((p - mean_predicted) ** 2 for p in predicted))

    if denominator_a == 0 or denominator_b == 0:
        return float("nan")
    return numerator / (denominator_a * denominator_b)


def _format_rank(rank: int | None) -> str:
    return "N/A" if rank is None else str(rank)


@app.command()
def show_hltv_target_comparison(
    target_path: Annotated[
        Path,
        typer.Option(
            "--target-path",
            help="Path to the target ranking JSON file.",
        ),
    ] = DEFAULT_TARGET_PATH,
    top_n: Annotated[
        int,
        typer.Option("--top-n", help="Number of target teams to compare."),
    ] = 20,
    elo_system_name: Annotated[
        str,
        typer.Option("--elo-system-name", help="System name from rating_systems.name."),
    ] = "team_elo_default",
    glicko2_system_name: Annotated[
        str,
        typer.Option(
            "--glicko2-system-name",
            help="System name from rating_systems.name.",
        ),
    ] = "team_glicko2_default",
    openskill_system_name: Annotated[
        str,
        typer.Option(
            "--openskill-system-name",
            help="System name from rating_systems.name.",
        ),
    ] = "team_openskill_default",
    show_metrics: Annotated[
        bool,
        typer.Option(
            "--show-metrics/--no-show-metrics",
            help="Show MAE/RMSE/Pearson and exact-match counts below the table.",
        ),
    ] = True,
    db_url: Annotated[
        str,
        typer.Option(
            "--db-url",
            help="Database URL. Defaults to the local cs2predictor postgres instance.",
        ),
    ] = DEFAULT_DB_URL,
) -> None:
    """Print a side-by-side comparison table for target and model ranks."""
    if top_n <= 0:
        raise typer.BadParameter("--top-n must be greater than 0")

    target_teams = _load_target_teams(target_path=target_path, top_n=top_n)
    if not target_teams:
        raise typer.BadParameter(
            f"No valid teams found in target file '{target_path}'.",
            param_hint="--target-path",
        )

    engine = create_db_engine(db_url)
    with engine.connect() as connection:
        rank_rows = _fetch_rank_rows(
            connection=connection,
            elo_system_name=elo_system_name,
            glicko2_system_name=glicko2_system_name,
            openskill_system_name=openskill_system_name,
        )

    by_name: dict[str, list[dict[str, Any]]] = {}
    for row in rank_rows:
        team_name = row.get("team_name")
        if not isinstance(team_name, str):
            continue
        by_name.setdefault(team_name.strip().casefold(), []).append(row)

    comparison_rows: list[ComparisonRow] = []
    for target_team in target_teams:
        candidates = by_name.get(target_team.name.casefold(), [])
        best_candidate = _pick_best_candidate(candidates)

        comparison_rows.append(
            ComparisonRow(
                team_name=target_team.name,
                hltv_rank=target_team.rank,
                elo_rank=(
                    int(best_candidate["elo_rank"])
                    if best_candidate and best_candidate.get("elo_rank") is not None
                    else None
                ),
                glicko2_rank=(
                    int(best_candidate["glicko2_rank"])
                    if best_candidate and best_candidate.get("glicko2_rank") is not None
                    else None
                ),
                openskill_rank=(
                    int(best_candidate["openskill_rank"])
                    if best_candidate and best_candidate.get("openskill_rank") is not None
                    else None
                ),
            )
        )

    typer.echo("| Team | HLTV Rank | Elo Rank | Glicko2 Rank | OpenSkill Rank |")
    typer.echo("|---|---:|---:|---:|---:|")
    for row in comparison_rows:
        typer.echo(
            f"| {row.team_name} | {row.hltv_rank} | "
            f"{_format_rank(row.elo_rank)} | "
            f"{_format_rank(row.glicko2_rank)} | "
            f"{_format_rank(row.openskill_rank)} |"
        )

    if not show_metrics:
        return

    fully_matched_rows = [
        row
        for row in comparison_rows
        if row.elo_rank is not None
        and row.glicko2_rank is not None
        and row.openskill_rank is not None
    ]
    if not fully_matched_rows:
        typer.echo("\nNo teams have rank data in all three systems; skipping metrics.")
        return

    hltv_ranks = [row.hltv_rank for row in fully_matched_rows]
    elo_ranks = [int(row.elo_rank) for row in fully_matched_rows]
    glicko2_ranks = [int(row.glicko2_rank) for row in fully_matched_rows]
    openskill_ranks = [int(row.openskill_rank) for row in fully_matched_rows]

    typer.echo("\nMetrics (only teams with non-null ranks in all three systems):")
    typer.echo(f"matched_teams={len(fully_matched_rows)}")

    for name, predicted in [
        ("Elo", elo_ranks),
        ("Glicko2", glicko2_ranks),
        ("OpenSkill", openskill_ranks),
    ]:
        exact_matches = sum(
            1 for expected, actual in zip(hltv_ranks, predicted) if expected == actual
        )
        typer.echo(
            f"{name}: "
            f"MAE={_mae(hltv_ranks, predicted):.3f} "
            f"RMSE={_rmse(hltv_ranks, predicted):.3f} "
            f"Pearson={_pearson(hltv_ranks, predicted):.3f} "
            f"Exact={exact_matches}"
        )


if __name__ == "__main__":
    app()
