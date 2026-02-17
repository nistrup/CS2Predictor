"""Persistence helpers for map-level team OpenSkill using SQLAlchemy."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, insert, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from models.base import Base
from models.ratings.openskill import OpenSkillSystem, TeamOpenSkill
from domain.ratings.openskill.calculator import TeamOpenSkillEvent
from repositories.ratings.common import fetch_map_results

TEAM_OPENSKILL_COPY_SQL = """
    COPY team_openskill (
        openskill_system_id,
        team_id,
        opponent_team_id,
        match_id,
        map_id,
        map_number,
        event_time,
        won,
        actual_score,
        expected_score,
        pre_mu,
        pre_sigma,
        pre_ordinal,
        mu_delta,
        sigma_delta,
        ordinal_delta,
        post_mu,
        post_sigma,
        post_ordinal,
        beta,
        kappa,
        tau,
        limit_sigma,
        balance,
        ordinal_z,
        initial_mu,
        initial_sigma
    ) FROM STDIN
"""


def ensure_team_openskill_schema(engine: Engine) -> None:
    """Create openskill_systems/team_openskill tables and indexes if needed."""
    with engine.begin() as connection:
        inspector = inspect(connection)
        existing_tables = set(inspector.get_table_names())
        reflect_only = [
            table_name
            for table_name in ["teams", "matches", "maps", "team_openskill", "openskill_systems"]
            if table_name in existing_tables
        ]
        Base.metadata.reflect(
            bind=connection,
            only=reflect_only,
        )
        OpenSkillSystem.__table__.create(bind=connection, checkfirst=True)
        TeamOpenSkill.__table__.create(bind=connection, checkfirst=True)


def upsert_openskill_system(
    session: Session,
    *,
    name: str,
    description: str | None,
    config_json: dict[str, Any],
) -> OpenSkillSystem:
    """Create or update an OpenSkill system definition."""
    system = session.execute(select(OpenSkillSystem).where(OpenSkillSystem.name == name)).scalar_one_or_none()
    if system is None:
        system = OpenSkillSystem(
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


def delete_team_openskill_for_system(session: Session, openskill_system_id: int) -> None:
    """Delete existing events for a single OpenSkill system."""
    session.execute(delete(TeamOpenSkill).where(TeamOpenSkill.openskill_system_id == openskill_system_id))


def insert_team_openskill_events(
    session: Session,
    events: Sequence[TeamOpenSkillEvent],
    *,
    openskill_system_id: int,
) -> None:
    """Bulk insert OpenSkill events."""
    if not events:
        return

    supports_copy = session.info.get("_team_openskill_supports_copy")
    if supports_copy is None:
        supports_copy = _supports_copy_bulk_insert(session)
        session.info["_team_openskill_supports_copy"] = supports_copy

    if supports_copy:
        _copy_team_openskill_events(session, events, openskill_system_id=openskill_system_id)
        return

    payload = [
        {
            "openskill_system_id": openskill_system_id,
            "team_id": event.team_id,
            "opponent_team_id": event.opponent_team_id,
            "match_id": event.match_id,
            "map_id": event.map_id,
            "map_number": event.map_number,
            "event_time": event.event_time,
            "won": event.won,
            "actual_score": event.actual_score,
            "expected_score": event.expected_score,
            "pre_mu": event.pre_mu,
            "pre_sigma": event.pre_sigma,
            "pre_ordinal": event.pre_ordinal,
            "mu_delta": event.mu_delta,
            "sigma_delta": event.sigma_delta,
            "ordinal_delta": event.ordinal_delta,
            "post_mu": event.post_mu,
            "post_sigma": event.post_sigma,
            "post_ordinal": event.post_ordinal,
            "beta": event.beta,
            "kappa": event.kappa,
            "tau": event.tau,
            "limit_sigma": event.limit_sigma,
            "balance": event.balance,
            "ordinal_z": event.ordinal_z,
            "initial_mu": event.initial_mu,
            "initial_sigma": event.initial_sigma,
        }
        for event in events
    ]
    session.execute(insert(TeamOpenSkill), payload)


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


def _copy_team_openskill_events(
    session: Session,
    events: Sequence[TeamOpenSkillEvent],
    *,
    openskill_system_id: int,
) -> None:
    raw_connection = session.connection().connection.driver_connection
    with raw_connection.cursor() as cursor:
        with cursor.copy(TEAM_OPENSKILL_COPY_SQL) as copy:
            for event in events:
                copy.write_row(
                    (
                        openskill_system_id,
                        event.team_id,
                        event.opponent_team_id,
                        event.match_id,
                        event.map_id,
                        event.map_number,
                        event.event_time,
                        event.won,
                        event.actual_score,
                        event.expected_score,
                        event.pre_mu,
                        event.pre_sigma,
                        event.pre_ordinal,
                        event.mu_delta,
                        event.sigma_delta,
                        event.ordinal_delta,
                        event.post_mu,
                        event.post_sigma,
                        event.post_ordinal,
                        event.beta,
                        event.kappa,
                        event.tau,
                        event.limit_sigma,
                        event.balance,
                        event.ordinal_z,
                        event.initial_mu,
                        event.initial_sigma,
                    )
                )


def count_tracked_teams(session: Session, *, openskill_system_id: int | None = None) -> int:
    """Count teams with at least one OpenSkill event."""
    statement = select(func.count(func.distinct(TeamOpenSkill.team_id)))
    if openskill_system_id is not None:
        statement = statement.where(TeamOpenSkill.openskill_system_id == openskill_system_id)
    result = session.scalar(statement)
    return int(result or 0)
