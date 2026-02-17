"""Persistence helpers for map-level team OpenSkill."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from domain.ratings.openskill.calculator import TeamOpenSkillEvent
from models.ratings.openskill import OpenSkillSystem, TeamOpenSkill
from repositories.ratings.base import BaseRatingRepository
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


def _team_openskill_event_to_row(event: TeamOpenSkillEvent, openskill_system_id: int) -> dict[str, Any]:
    return {
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


def _team_openskill_event_to_copy_row(
    event: TeamOpenSkillEvent,
    openskill_system_id: int,
) -> tuple[Any, ...]:
    return (
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


TEAM_OPENSKILL_REPOSITORY = BaseRatingRepository[OpenSkillSystem, TeamOpenSkill, TeamOpenSkillEvent](
    system_model=OpenSkillSystem,
    event_model=TeamOpenSkill,
    system_id_column="openskill_system_id",
    entity_id_column="team_id",
    event_to_row=_team_openskill_event_to_row,
    copy_sql=TEAM_OPENSKILL_COPY_SQL,
    event_to_copy_row=_team_openskill_event_to_copy_row,
    reflect_tables=("teams", "matches", "maps", "team_openskill", "openskill_systems"),
)


def ensure_team_openskill_schema(engine: Engine) -> None:
    """Create openskill_systems/team_openskill tables and indexes if needed."""
    TEAM_OPENSKILL_REPOSITORY.ensure_schema(engine)


def upsert_openskill_system(
    session: Session,
    *,
    name: str,
    description: str | None,
    config_json: dict[str, Any],
) -> OpenSkillSystem:
    """Create or update an OpenSkill system definition."""
    return cast(
        OpenSkillSystem,
        TEAM_OPENSKILL_REPOSITORY.upsert_system(
            session,
            name=name,
            description=description,
            config_json=config_json,
        ),
    )


def delete_team_openskill_for_system(session: Session, openskill_system_id: int) -> None:
    """Delete existing events for a single OpenSkill system."""
    TEAM_OPENSKILL_REPOSITORY.delete_events_for_system(session, openskill_system_id)


def insert_team_openskill_events(
    session: Session,
    events: Sequence[TeamOpenSkillEvent],
    *,
    openskill_system_id: int,
) -> None:
    """Bulk insert OpenSkill events."""
    TEAM_OPENSKILL_REPOSITORY.insert_events(session, events, system_id=openskill_system_id)


def count_tracked_teams(session: Session, *, openskill_system_id: int | None = None) -> int:
    """Count teams with at least one OpenSkill event."""
    return TEAM_OPENSKILL_REPOSITORY.count_tracked_entities(session, system_id=openskill_system_id)
