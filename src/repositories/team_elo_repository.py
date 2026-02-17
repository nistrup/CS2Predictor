"""Persistence helpers for map-level team Elo using SQLAlchemy."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    func,
    insert,
    or_,
    select,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from elo.team_elo import TeamEloEvent, TeamMapResult
from models import Base, TeamElo

_metadata = MetaData()

_matches = Table(
    "matches",
    _metadata,
    Column("id", Integer),
    Column("team1_id", Integer),
    Column("team2_id", Integer),
    Column("status", String),
    Column("date", DateTime(timezone=False)),
    Column("updated_at", DateTime(timezone=False)),
    Column("created_at", DateTime(timezone=False)),
)

_maps = Table(
    "maps",
    _metadata,
    Column("id", Integer),
    Column("match_id", Integer),
    Column("map_number", Integer),
    Column("winner_id", Integer),
)


def ensure_team_elo_schema(engine: Engine) -> None:
    """Create the team_elo table and its indexes if they do not exist."""
    Base.metadata.create_all(bind=engine, tables=[TeamElo.__table__])


def fetch_map_results(session: Session) -> list[TeamMapResult]:
    """Fetch map outcomes in deterministic chronological order."""
    event_time_expr = func.coalesce(
        _matches.c.date,
        _matches.c.updated_at,
        _matches.c.created_at,
    ).label("event_time")

    statement = (
        select(
            _matches.c.id.label("match_id"),
            _maps.c.id.label("map_id"),
            _maps.c.map_number.label("map_number"),
            event_time_expr,
            _matches.c.team1_id.label("team1_id"),
            _matches.c.team2_id.label("team2_id"),
            _maps.c.winner_id.label("winner_id"),
        )
        .select_from(_maps.join(_matches, _maps.c.match_id == _matches.c.id))
        .where(
            _matches.c.status == "FINISHED",
            _maps.c.winner_id.is_not(None),
            or_(
                _maps.c.winner_id == _matches.c.team1_id,
                _maps.c.winner_id == _matches.c.team2_id,
            ),
        )
        .order_by(
            event_time_expr,
            _matches.c.id,
            _maps.c.map_number,
            _maps.c.id,
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
                map_number=row["map_number"],
                event_time=event_time,
                team1_id=row["team1_id"],
                team2_id=row["team2_id"],
                winner_id=row["winner_id"],
            )
        )

    return map_results


def truncate_team_elo(session: Session) -> None:
    """Hard-reset table contents before a full deterministic rebuild."""
    session.execute(text("TRUNCATE TABLE team_elo RESTART IDENTITY"))


def insert_team_elo_events(session: Session, events: Sequence[TeamEloEvent]) -> None:
    """Bulk insert Elo events."""
    if not events:
        return

    payload = [
        {
            "team_id": event.team_id,
            "opponent_team_id": event.opponent_team_id,
            "match_id": event.match_id,
            "map_id": event.map_id,
            "map_number": event.map_number,
            "event_time": event.event_time,
            "won": event.won,
            "actual_score": event.actual_score,
            "expected_score": event.expected_score,
            "pre_elo": event.pre_elo,
            "elo_delta": event.elo_delta,
            "post_elo": event.post_elo,
            "k_factor": event.k_factor,
            "scale_factor": event.scale_factor,
            "initial_elo": event.initial_elo,
        }
        for event in events
    ]
    session.execute(insert(TeamElo), payload)


def count_tracked_teams(session: Session) -> int:
    """Count teams with at least one Elo event."""
    statement = select(func.count(func.distinct(TeamElo.team_id)))
    result = session.scalar(statement)
    return int(result or 0)
