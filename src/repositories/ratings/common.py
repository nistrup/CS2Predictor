"""Shared repository helpers for team- and player-based rating systems."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

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

from domain.ratings.common import (
    PlayerMapParticipant,
    PlayerMapResult,
    PlayerMatchParticipant,
    PlayerMatchResult,
    TeamMapResult,
    TeamMatchResult,
)

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
    Column("player_id", Integer),
    Column("team_id", Integer),
    Column("side", String),
    Column("kills", Integer),
    Column("deaths", Integer),
    Column("adr", Float),
    Column("kast", Float),
    Column("rating", Float),
    Column("swing", Float),
)


def _build_cutoff_time(lookback_days: int | None) -> datetime | None:
    if lookback_days is None or lookback_days <= 0:
        return None
    return datetime.now(UTC).replace(tzinfo=None) - timedelta(days=lookback_days)


def _event_time_expr():
    return func.coalesce(
        _matches.c.date,
        _matches.c.updated_at,
        _matches.c.created_at,
    ).label("event_time")


def _map_result_conditions(cutoff_time: datetime | None) -> list[Any]:
    event_time = _event_time_expr()
    conditions: list[Any] = [
        cast(_matches.c.status, String) == "FINISHED",
        _maps.c.winner_id.is_not(None),
        or_(
            _maps.c.winner_id == _matches.c.team1_id,
            _maps.c.winner_id == _matches.c.team2_id,
        ),
    ]
    if cutoff_time is not None:
        conditions.append(event_time >= cutoff_time)
    return conditions


def _base_filtered_maps(cutoff_time: datetime | None):
    event_time = _event_time_expr()
    return (
        select(
            _matches.c.id.label("match_id"),
            _maps.c.id.label("map_id"),
            cast(_maps.c.map_name, String).label("map_name"),
            _maps.c.map_number.label("map_number"),
            event_time,
            _matches.c.team1_id.label("team1_id"),
            _matches.c.team2_id.label("team2_id"),
            _maps.c.winner_id.label("winner_id"),
            _maps.c.score_team1.label("team1_score"),
            _maps.c.score_team2.label("team2_score"),
            func.coalesce(_events.c.lan, False).label("is_lan"),
            cast(_matches.c.format, String).label("match_format"),
        )
        .select_from(
            _maps.join(_matches, _maps.c.match_id == _matches.c.id).outerjoin(
                _events,
                _matches.c.event_id == _events.c.id,
            )
        )
        .where(*_map_result_conditions(cutoff_time))
        .cte("filtered_maps")
    )


def _decisive_matches_cte(cutoff_time: datetime | None):
    event_time = _event_time_expr()
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
            event_time,
            _matches.c.team1_id.label("team1_id"),
            _matches.c.team2_id.label("team2_id"),
            team1_maps_won,
            team2_maps_won,
            func.coalesce(_events.c.lan, False).label("is_lan"),
            cast(_matches.c.format, String).label("match_format"),
        )
        .select_from(
            _matches.join(_maps, _maps.c.match_id == _matches.c.id).outerjoin(
                _events,
                _matches.c.event_id == _events.c.id,
            )
        )
        .where(*_map_result_conditions(cutoff_time))
        .group_by(
            _matches.c.id,
            event_time,
            _matches.c.team1_id,
            _matches.c.team2_id,
            _events.c.lan,
            _matches.c.format,
        )
        .having(team1_maps_won != team2_maps_won)
        .order_by(event_time, _matches.c.id)
    )
    return statement.cte("decisive_matches")


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _participants_kd_ratio(participants: tuple[PlayerMapParticipant, ...]) -> float | None:
    kills = 0
    deaths = 0
    for participant in participants:
        if participant.kills is None or participant.deaths is None:
            continue
        kills += participant.kills
        deaths += participant.deaths
    if deaths <= 0:
        return None
    return float(kills) / float(deaths)


def fetch_map_results(session: Session, lookback_days: int | None = 365) -> list[TeamMapResult]:
    """Fetch map outcomes in deterministic chronological order."""
    cutoff_time = _build_cutoff_time(lookback_days)
    filtered_maps = _base_filtered_maps(cutoff_time)

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
            (cast(team1_kills, Float) / func.nullif(cast(team1_deaths, Float), 0.0)).label("team1_kd_ratio"),
            (cast(team2_kills, Float) / func.nullif(cast(team2_deaths, Float), 0.0)).label("team2_kd_ratio"),
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
                match_id=int(row["match_id"]),
                map_id=int(row["map_id"]),
                map_name=row["map_name"],
                map_number=int(row["map_number"]),
                event_time=event_time,
                team1_id=int(row["team1_id"]),
                team2_id=int(row["team2_id"]),
                winner_id=int(row["winner_id"]),
                team1_score=_optional_int(row["team1_score"]),
                team2_score=_optional_int(row["team2_score"]),
                team1_kd_ratio=_optional_float(row["team1_kd_ratio"]),
                team2_kd_ratio=_optional_float(row["team2_kd_ratio"]),
                is_lan=bool(row["is_lan"]),
                match_format=row["match_format"],
            )
        )

    return map_results


def fetch_player_map_results(session: Session, lookback_days: int | None = 365) -> list[PlayerMapResult]:
    """Fetch player-level map outcomes in deterministic chronological order."""
    cutoff_time = _build_cutoff_time(lookback_days)
    filtered_maps = _base_filtered_maps(cutoff_time)

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
            filtered_maps.c.is_lan,
            filtered_maps.c.match_format,
            _map_player_stats.c.player_id,
            _map_player_stats.c.team_id,
            _map_player_stats.c.kills,
            _map_player_stats.c.deaths,
            _map_player_stats.c.adr,
            _map_player_stats.c.kast,
            _map_player_stats.c.rating,
            _map_player_stats.c.swing,
        )
        .select_from(
            filtered_maps.join(
                _map_player_stats,
                _map_player_stats.c.map_id == filtered_maps.c.map_id,
            )
        )
        .where(
            _map_player_stats.c.player_id.is_not(None),
            cast(_map_player_stats.c.side, String) == "BOTH",
            or_(
                _map_player_stats.c.team_id == filtered_maps.c.team1_id,
                _map_player_stats.c.team_id == filtered_maps.c.team2_id,
            ),
        )
        .order_by(
            filtered_maps.c.event_time,
            filtered_maps.c.match_id,
            filtered_maps.c.map_number,
            filtered_maps.c.map_id,
            _map_player_stats.c.team_id,
            _map_player_stats.c.player_id,
        )
    )

    rows = session.execute(statement).mappings().all()

    grouped: dict[int, dict[str, Any]] = {}
    ordered_map_ids: list[int] = []

    for row in rows:
        map_id = int(row["map_id"])
        payload = grouped.get(map_id)
        if payload is None:
            event_time = row["event_time"]
            if not isinstance(event_time, datetime):
                raise ValueError(f"map_id={map_id} has invalid event_time={event_time!r}")
            payload = {
                "match_id": int(row["match_id"]),
                "map_id": map_id,
                "map_name": row["map_name"],
                "map_number": int(row["map_number"]),
                "event_time": event_time,
                "team1_id": int(row["team1_id"]),
                "team2_id": int(row["team2_id"]),
                "winner_id": int(row["winner_id"]),
                "team1_score": _optional_int(row["team1_score"]),
                "team2_score": _optional_int(row["team2_score"]),
                "is_lan": bool(row["is_lan"]),
                "match_format": row["match_format"],
                "team1_players": [],
                "team2_players": [],
            }
            grouped[map_id] = payload
            ordered_map_ids.append(map_id)

        participant = PlayerMapParticipant(
            player_id=int(row["player_id"]),
            team_id=int(row["team_id"]),
            kills=_optional_int(row["kills"]),
            deaths=_optional_int(row["deaths"]),
            adr=_optional_float(row["adr"]),
            kast=_optional_float(row["kast"]),
            rating=_optional_float(row["rating"]),
            swing=_optional_float(row["swing"]),
        )

        if participant.team_id == payload["team1_id"]:
            payload["team1_players"].append(participant)
        elif participant.team_id == payload["team2_id"]:
            payload["team2_players"].append(participant)

    map_results: list[PlayerMapResult] = []
    for map_id in ordered_map_ids:
        payload = grouped[map_id]
        team1_players = tuple(payload["team1_players"])
        team2_players = tuple(payload["team2_players"])

        if not team1_players or not team2_players:
            continue

        map_results.append(
            PlayerMapResult(
                match_id=payload["match_id"],
                map_id=payload["map_id"],
                map_name=payload["map_name"],
                map_number=payload["map_number"],
                event_time=payload["event_time"],
                team1_id=payload["team1_id"],
                team2_id=payload["team2_id"],
                winner_id=payload["winner_id"],
                team1_players=team1_players,
                team2_players=team2_players,
                team1_score=payload["team1_score"],
                team2_score=payload["team2_score"],
                team1_kd_ratio=_participants_kd_ratio(team1_players),
                team2_kd_ratio=_participants_kd_ratio(team2_players),
                is_lan=payload["is_lan"],
                match_format=payload["match_format"],
            )
        )

    return map_results


def fetch_match_results(session: Session, lookback_days: int | None = 365) -> list[TeamMatchResult]:
    """Fetch decisive match outcomes in deterministic chronological order."""
    cutoff_time = _build_cutoff_time(lookback_days)
    decisive_matches = _decisive_matches_cte(cutoff_time)

    rows = session.execute(select(decisive_matches).order_by(decisive_matches.c.event_time, decisive_matches.c.match_id)).mappings().all()

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


def fetch_player_match_results(session: Session, lookback_days: int | None = 365) -> list[PlayerMatchResult]:
    """Fetch player-level match outcomes in deterministic chronological order."""
    cutoff_time = _build_cutoff_time(lookback_days)
    decisive_matches = _decisive_matches_cte(cutoff_time)

    statement = (
        select(
            decisive_matches.c.match_id,
            decisive_matches.c.event_time,
            decisive_matches.c.team1_id,
            decisive_matches.c.team2_id,
            decisive_matches.c.team1_maps_won,
            decisive_matches.c.team2_maps_won,
            decisive_matches.c.is_lan,
            decisive_matches.c.match_format,
            _map_player_stats.c.player_id,
            _map_player_stats.c.team_id,
            func.count(func.distinct(_maps.c.id)).label("maps_played"),
            func.sum(_map_player_stats.c.kills).label("kills"),
            func.sum(_map_player_stats.c.deaths).label("deaths"),
            func.avg(cast(_map_player_stats.c.adr, Float)).label("adr"),
            func.avg(cast(_map_player_stats.c.kast, Float)).label("kast"),
            func.avg(cast(_map_player_stats.c.rating, Float)).label("rating"),
            func.sum(cast(_map_player_stats.c.swing, Float)).label("swing"),
        )
        .select_from(
            decisive_matches.join(_maps, _maps.c.match_id == decisive_matches.c.match_id).join(
                _map_player_stats,
                _map_player_stats.c.map_id == _maps.c.id,
            )
        )
        .where(
            _map_player_stats.c.player_id.is_not(None),
            cast(_map_player_stats.c.side, String) == "BOTH",
            or_(
                _map_player_stats.c.team_id == decisive_matches.c.team1_id,
                _map_player_stats.c.team_id == decisive_matches.c.team2_id,
            ),
        )
        .group_by(
            decisive_matches.c.match_id,
            decisive_matches.c.event_time,
            decisive_matches.c.team1_id,
            decisive_matches.c.team2_id,
            decisive_matches.c.team1_maps_won,
            decisive_matches.c.team2_maps_won,
            decisive_matches.c.is_lan,
            decisive_matches.c.match_format,
            _map_player_stats.c.player_id,
            _map_player_stats.c.team_id,
        )
        .order_by(
            decisive_matches.c.event_time,
            decisive_matches.c.match_id,
            _map_player_stats.c.team_id,
            _map_player_stats.c.player_id,
        )
    )

    rows = session.execute(statement).mappings().all()

    grouped: dict[int, dict[str, Any]] = {}
    ordered_match_ids: list[int] = []

    for row in rows:
        match_id = int(row["match_id"])
        payload = grouped.get(match_id)
        if payload is None:
            event_time = row["event_time"]
            if not isinstance(event_time, datetime):
                raise ValueError(f"match_id={match_id} has invalid event_time={event_time!r}")
            team1_id = int(row["team1_id"])
            team2_id = int(row["team2_id"])
            team1_maps_won = int(row["team1_maps_won"])
            team2_maps_won = int(row["team2_maps_won"])
            payload = {
                "match_id": match_id,
                "event_time": event_time,
                "team1_id": team1_id,
                "team2_id": team2_id,
                "winner_id": team1_id if team1_maps_won > team2_maps_won else team2_id,
                "team1_maps_won": team1_maps_won,
                "team2_maps_won": team2_maps_won,
                "is_lan": bool(row["is_lan"]),
                "match_format": row["match_format"],
                "team1_players": [],
                "team2_players": [],
            }
            grouped[match_id] = payload
            ordered_match_ids.append(match_id)

        participant = PlayerMatchParticipant(
            player_id=int(row["player_id"]),
            team_id=int(row["team_id"]),
            maps_played=int(row["maps_played"]),
            kills=_optional_int(row["kills"]),
            deaths=_optional_int(row["deaths"]),
            adr=_optional_float(row["adr"]),
            kast=_optional_float(row["kast"]),
            rating=_optional_float(row["rating"]),
            swing=_optional_float(row["swing"]),
        )

        if participant.team_id == payload["team1_id"]:
            payload["team1_players"].append(participant)
        elif participant.team_id == payload["team2_id"]:
            payload["team2_players"].append(participant)

    match_results: list[PlayerMatchResult] = []
    for match_id in ordered_match_ids:
        payload = grouped[match_id]
        team1_players = tuple(payload["team1_players"])
        team2_players = tuple(payload["team2_players"])

        if not team1_players or not team2_players:
            continue

        match_results.append(
            PlayerMatchResult(
                match_id=payload["match_id"],
                event_time=payload["event_time"],
                team1_id=payload["team1_id"],
                team2_id=payload["team2_id"],
                winner_id=payload["winner_id"],
                team1_maps_won=payload["team1_maps_won"],
                team2_maps_won=payload["team2_maps_won"],
                team1_players=team1_players,
                team2_players=team2_players,
                is_lan=payload["is_lan"],
                match_format=payload["match_format"],
            )
        )

    return match_results
