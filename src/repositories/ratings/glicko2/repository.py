"""Persistence helpers for map-level team Glicko-2 using SQLAlchemy."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, insert, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from models.base import Base
from models.ratings.glicko2 import Glicko2System, TeamGlicko2
from domain.ratings.glicko2.calculator import TeamGlicko2Event
from repositories.ratings.common import fetch_map_results

TEAM_GLICKO2_COPY_SQL = """
    COPY team_glicko2 (
        glicko2_system_id,
        team_id,
        opponent_team_id,
        match_id,
        map_id,
        map_number,
        event_time,
        won,
        actual_score,
        expected_score,
        pre_rating,
        pre_rd,
        pre_volatility,
        rating_delta,
        rd_delta,
        volatility_delta,
        post_rating,
        post_rd,
        post_volatility,
        tau,
        rating_period_days,
        initial_rating,
        initial_rd,
        initial_volatility
    ) FROM STDIN
"""


def ensure_team_glicko2_schema(engine: Engine) -> None:
    """Create glicko2_systems/team_glicko2 tables and indexes if needed."""
    with engine.begin() as connection:
        inspector = inspect(connection)
        existing_tables = set(inspector.get_table_names())
        reflect_only = [
            table_name
            for table_name in ["teams", "matches", "maps", "team_glicko2", "glicko2_systems"]
            if table_name in existing_tables
        ]
        Base.metadata.reflect(
            bind=connection,
            only=reflect_only,
        )
        Glicko2System.__table__.create(bind=connection, checkfirst=True)
        TeamGlicko2.__table__.create(bind=connection, checkfirst=True)


def upsert_glicko2_system(
    session: Session,
    *,
    name: str,
    description: str | None,
    config_json: dict[str, Any],
) -> Glicko2System:
    """Create or update a Glicko-2 system definition."""
    system = session.execute(select(Glicko2System).where(Glicko2System.name == name)).scalar_one_or_none()
    if system is None:
        system = Glicko2System(
            name=name,
            description=description,
            config_json=config_json,
        )
        session.add(system)
    else:
        system.description = description
        system.config_json = config_json
        system.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.flush()
    return system


def delete_team_glicko2_for_system(session: Session, glicko2_system_id: int) -> None:
    """Delete existing events for a single Glicko-2 system."""
    session.execute(delete(TeamGlicko2).where(TeamGlicko2.glicko2_system_id == glicko2_system_id))


def insert_team_glicko2_events(
    session: Session,
    events: Sequence[TeamGlicko2Event],
    *,
    glicko2_system_id: int,
) -> None:
    """Bulk insert Glicko-2 events."""
    if not events:
        return

    supports_copy = session.info.get("_team_glicko2_supports_copy")
    if supports_copy is None:
        supports_copy = _supports_copy_bulk_insert(session)
        session.info["_team_glicko2_supports_copy"] = supports_copy

    if supports_copy:
        _copy_team_glicko2_events(session, events, glicko2_system_id=glicko2_system_id)
        return

    payload = [
        {
            "glicko2_system_id": glicko2_system_id,
            "team_id": event.team_id,
            "opponent_team_id": event.opponent_team_id,
            "match_id": event.match_id,
            "map_id": event.map_id,
            "map_number": event.map_number,
            "event_time": event.event_time,
            "won": event.won,
            "actual_score": event.actual_score,
            "expected_score": event.expected_score,
            "pre_rating": event.pre_rating,
            "pre_rd": event.pre_rd,
            "pre_volatility": event.pre_volatility,
            "rating_delta": event.rating_delta,
            "rd_delta": event.rd_delta,
            "volatility_delta": event.volatility_delta,
            "post_rating": event.post_rating,
            "post_rd": event.post_rd,
            "post_volatility": event.post_volatility,
            "tau": event.tau,
            "rating_period_days": event.rating_period_days,
            "initial_rating": event.initial_rating,
            "initial_rd": event.initial_rd,
            "initial_volatility": event.initial_volatility,
        }
        for event in events
    ]
    session.execute(insert(TeamGlicko2), payload)


def _supports_copy_bulk_insert(session: Session) -> bool:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return False

    try:
        raw_connection = session.connection().connection.driver_connection
    except Exception:
        return False

    try:
        with raw_connection.cursor() as cursor:
            return hasattr(cursor, "copy")
    except Exception:
        return False


def _copy_team_glicko2_events(
    session: Session,
    events: Sequence[TeamGlicko2Event],
    *,
    glicko2_system_id: int,
) -> None:
    raw_connection = session.connection().connection.driver_connection
    with raw_connection.cursor() as cursor:
        with cursor.copy(TEAM_GLICKO2_COPY_SQL) as copy:
            for event in events:
                copy.write_row(
                    (
                        glicko2_system_id,
                        event.team_id,
                        event.opponent_team_id,
                        event.match_id,
                        event.map_id,
                        event.map_number,
                        event.event_time,
                        event.won,
                        event.actual_score,
                        event.expected_score,
                        event.pre_rating,
                        event.pre_rd,
                        event.pre_volatility,
                        event.rating_delta,
                        event.rd_delta,
                        event.volatility_delta,
                        event.post_rating,
                        event.post_rd,
                        event.post_volatility,
                        event.tau,
                        event.rating_period_days,
                        event.initial_rating,
                        event.initial_rd,
                        event.initial_volatility,
                    )
                )


def count_tracked_teams(session: Session, *, glicko2_system_id: int | None = None) -> int:
    """Count teams with at least one Glicko-2 event."""
    statement = select(func.count(func.distinct(TeamGlicko2.team_id)))
    if glicko2_system_id is not None:
        statement = statement.where(TeamGlicko2.glicko2_system_id == glicko2_system_id)
    result = session.scalar(statement)
    return int(result or 0)
