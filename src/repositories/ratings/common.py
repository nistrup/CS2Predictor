"""Shared repository helpers for team-based rating systems."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    cast,
    case,
    func,
    or_,
    select,
)
from sqlalchemy.orm import Session

from domain.ratings.common import TeamMapResult, TeamMatchResult

_metadata = MetaData()

_matches = Table(
    "matches",
    _metadata,
    Column("id", Integer),
    Column("team1_id", Integer),
    Column("team2_id", Integer),
    Column("event_id", Integer),
    Column("format", String),
    Column("status", String),
    Column("date", DateTime(timezone=False)),
    Column("updated_at", DateTime(timezone=False)),
    Column("created_at", DateTime(timezone=False)),
)

_events = Table(
    "events",
    _metadata,
    Column("id", Integer),
    Column("lan", Boolean),
)

_maps = Table(
    "maps",
    _metadata,
    Column("id", Integer),
    Column("match_id", Integer),
    Column("map_name", String),
    Column("map_number", Integer),
    Column("winner_id", Integer),
    Column("score_team1", Integer),
    Column("score_team2", Integer),
)

_map_player_stats = Table(
    "map_player_stats",
    _metadata,
    Column("map_id", Integer),
    Column("team_id", Integer),
    Column("kills", Integer),
    Column("deaths", Integer),
)


def fetch_map_results(session: Session, lookback_days: int | None = 365) -> list[TeamMapResult]:
    """Fetch map outcomes in deterministic chronological order."""
    cutoff_time = None
    if lookback_days is not None and lookback_days > 0:
        cutoff_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=lookback_days)

    event_time_expr = func.coalesce(
        _matches.c.date,
        _matches.c.updated_at,
        _matches.c.created_at,
    ).label("event_time")

    conditions = [
        cast(_matches.c.status, String) == "FINISHED",
        _maps.c.winner_id.is_not(None),
        or_(
            _maps.c.winner_id == _matches.c.team1_id,
            _maps.c.winner_id == _matches.c.team2_id,
        ),
    ]
    if cutoff_time is not None:
        conditions.append(event_time_expr >= cutoff_time)

    filtered_maps = (
        select(
            _matches.c.id.label("match_id"),
            _maps.c.id.label("map_id"),
            cast(_maps.c.map_name, String).label("map_name"),
            _maps.c.map_number.label("map_number"),
            event_time_expr,
            _matches.c.team1_id.label("team1_id"),
            _matches.c.team2_id.label("team2_id"),
            _maps.c.winner_id.label("winner_id"),
            _maps.c.score_team1.label("team1_score"),
            _maps.c.score_team2.label("team2_score"),
            func.coalesce(_events.c.lan, False).label("is_lan"),
            cast(_matches.c.format, String).label("match_format"),
        )
        .select_from(_maps.join(_matches, _maps.c.match_id == _matches.c.id).outerjoin(
            _events, _matches.c.event_id == _events.c.id
        ))
        .where(*conditions)
        .cte("filtered_maps")
    )

    from_obj = filtered_maps.outerjoin(
        _map_player_stats,
        _map_player_stats.c.map_id == filtered_maps.c.map_id,
    )

    team1_kills = func.sum(
        case(
            (
                _map_player_stats.c.team_id == filtered_maps.c.team1_id,
                _map_player_stats.c.kills,
            ),
            else_=0,
        )
    )
    team1_deaths = func.sum(
        case(
            (
                _map_player_stats.c.team_id == filtered_maps.c.team1_id,
                _map_player_stats.c.deaths,
            ),
            else_=0,
        )
    )
    team2_kills = func.sum(
        case(
            (
                _map_player_stats.c.team_id == filtered_maps.c.team2_id,
                _map_player_stats.c.kills,
            ),
            else_=0,
        )
    )
    team2_deaths = func.sum(
        case(
            (
                _map_player_stats.c.team_id == filtered_maps.c.team2_id,
                _map_player_stats.c.deaths,
            ),
            else_=0,
        )
    )

    statement = (
        select(
            filtered_maps.c.match_id,
            filtered_maps.c.map_id,
            filtered_maps.c.map_name,
            filtered_maps.c.map_number,
            filtered_maps.c.event_time,
            filtered_maps.c.team1_id,
            filtered_maps.c.team2_id,
            filtered_maps.c.winner_id,
            filtered_maps.c.team1_score,
            filtered_maps.c.team2_score,
            (
                cast(team1_kills, Float)
                / func.nullif(cast(team1_deaths, Float), 0.0)
            ).label("team1_kd_ratio"),
            (
                cast(team2_kills, Float)
                / func.nullif(cast(team2_deaths, Float), 0.0)
            ).label("team2_kd_ratio"),
            filtered_maps.c.is_lan,
            filtered_maps.c.match_format,
        )
        .select_from(from_obj)
        .group_by(
            filtered_maps.c.match_id,
            filtered_maps.c.map_id,
            filtered_maps.c.map_name,
            filtered_maps.c.map_number,
            filtered_maps.c.event_time,
            filtered_maps.c.team1_id,
            filtered_maps.c.team2_id,
            filtered_maps.c.winner_id,
            filtered_maps.c.team1_score,
            filtered_maps.c.team2_score,
            filtered_maps.c.is_lan,
            filtered_maps.c.match_format,
        )
        .order_by(
            filtered_maps.c.event_time,
            filtered_maps.c.match_id,
            filtered_maps.c.map_number,
            filtered_maps.c.map_id,
        )
    )

    rows = session.execute(statement).mappings().all()

    map_results: list[TeamMapResult] = []
    for row in rows:
        event_time = row["event_time"]
        if not isinstance(event_time, datetime):
            raise ValueError(f"map_id={row['map_id']} has invalid event_time={event_time!r}")

        map_results.append(
            TeamMapResult(
                match_id=row["match_id"],
                map_id=row["map_id"],
                map_name=row["map_name"],
                map_number=row["map_number"],
                event_time=event_time,
                team1_id=row["team1_id"],
                team2_id=row["team2_id"],
                winner_id=row["winner_id"],
                team1_score=row["team1_score"],
                team2_score=row["team2_score"],
                team1_kd_ratio=(
                    float(row["team1_kd_ratio"]) if row["team1_kd_ratio"] is not None else None
                ),
                team2_kd_ratio=(
                    float(row["team2_kd_ratio"]) if row["team2_kd_ratio"] is not None else None
                ),
                is_lan=bool(row["is_lan"]),
                match_format=row["match_format"],
            )
        )

    return map_results


def fetch_match_results(session: Session, lookback_days: int | None = 365) -> list[TeamMatchResult]:
    """Fetch decisive match outcomes in deterministic chronological order."""
    cutoff_time = None
    if lookback_days is not None and lookback_days > 0:
        cutoff_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=lookback_days)

    event_time_expr = func.coalesce(
        _matches.c.date,
        _matches.c.updated_at,
        _matches.c.created_at,
    ).label("event_time")

    conditions = [
        cast(_matches.c.status, String) == "FINISHED",
        _maps.c.winner_id.is_not(None),
        or_(
            _maps.c.winner_id == _matches.c.team1_id,
            _maps.c.winner_id == _matches.c.team2_id,
        ),
    ]
    if cutoff_time is not None:
        conditions.append(event_time_expr >= cutoff_time)

    team1_maps_won = func.sum(
        case(
            (_maps.c.winner_id == _matches.c.team1_id, 1),
            else_=0,
        )
    ).label("team1_maps_won")
    team2_maps_won = func.sum(
        case(
            (_maps.c.winner_id == _matches.c.team2_id, 1),
            else_=0,
        )
    ).label("team2_maps_won")

    statement = (
        select(
            _matches.c.id.label("match_id"),
            event_time_expr,
            _matches.c.team1_id.label("team1_id"),
            _matches.c.team2_id.label("team2_id"),
            team1_maps_won,
            team2_maps_won,
            func.coalesce(_events.c.lan, False).label("is_lan"),
            cast(_matches.c.format, String).label("match_format"),
        )
        .select_from(_matches.join(_maps, _maps.c.match_id == _matches.c.id).outerjoin(
            _events, _matches.c.event_id == _events.c.id
        ))
        .where(*conditions)
        .group_by(
            _matches.c.id,
            event_time_expr,
            _matches.c.team1_id,
            _matches.c.team2_id,
            _events.c.lan,
            _matches.c.format,
        )
        .having(team1_maps_won != team2_maps_won)
        .order_by(event_time_expr, _matches.c.id)
    )

    rows = session.execute(statement).mappings().all()

    match_results: list[TeamMatchResult] = []
    for row in rows:
        event_time = row["event_time"]
        if not isinstance(event_time, datetime):
            raise ValueError(f"match_id={row['match_id']} has invalid event_time={event_time!r}")

        team1_id = int(row["team1_id"])
        team2_id = int(row["team2_id"])
        team1_wins = int(row["team1_maps_won"])
        team2_wins = int(row["team2_maps_won"])
        winner_id = team1_id if team1_wins > team2_wins else team2_id

        match_results.append(
            TeamMatchResult(
                match_id=int(row["match_id"]),
                event_time=event_time,
                team1_id=team1_id,
                team2_id=team2_id,
                winner_id=winner_id,
                team1_maps_won=team1_wins,
                team2_maps_won=team2_wins,
                is_lan=bool(row["is_lan"]),
                match_format=row["match_format"],
            )
        )

    return match_results
