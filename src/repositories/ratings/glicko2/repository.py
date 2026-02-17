"""Persistence helpers for map-level team Glicko-2."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from domain.ratings.glicko2.calculator import TeamGlicko2Event
from models.ratings.glicko2 import Glicko2System, TeamGlicko2
from repositories.ratings.base import BaseRatingRepository
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


def _team_glicko2_event_to_row(event: TeamGlicko2Event, glicko2_system_id: int) -> dict[str, Any]:
    return {
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


def _team_glicko2_event_to_copy_row(
    event: TeamGlicko2Event,
    glicko2_system_id: int,
) -> tuple[Any, ...]:
    return (
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


TEAM_GLICKO2_REPOSITORY = BaseRatingRepository[Glicko2System, TeamGlicko2, TeamGlicko2Event](
    system_model=Glicko2System,
    event_model=TeamGlicko2,
    system_id_column="glicko2_system_id",
    entity_id_column="team_id",
    event_to_row=_team_glicko2_event_to_row,
    copy_sql=TEAM_GLICKO2_COPY_SQL,
    event_to_copy_row=_team_glicko2_event_to_copy_row,
    reflect_tables=("teams", "matches", "maps", "team_glicko2", "glicko2_systems"),
)


def ensure_team_glicko2_schema(engine: Engine) -> None:
    """Create glicko2_systems/team_glicko2 tables and indexes if needed."""
    TEAM_GLICKO2_REPOSITORY.ensure_schema(engine)


def upsert_glicko2_system(
    session: Session,
    *,
    name: str,
    description: str | None,
    config_json: dict[str, Any],
) -> Glicko2System:
    """Create or update a Glicko-2 system definition."""
    return cast(
        Glicko2System,
        TEAM_GLICKO2_REPOSITORY.upsert_system(
            session,
            name=name,
            description=description,
            config_json=config_json,
        ),
    )


def delete_team_glicko2_for_system(session: Session, glicko2_system_id: int) -> None:
    """Delete existing events for a single Glicko-2 system."""
    TEAM_GLICKO2_REPOSITORY.delete_events_for_system(session, glicko2_system_id)


def insert_team_glicko2_events(
    session: Session,
    events: Sequence[TeamGlicko2Event],
    *,
    glicko2_system_id: int,
) -> None:
    """Bulk insert Glicko-2 events."""
    TEAM_GLICKO2_REPOSITORY.insert_events(session, events, system_id=glicko2_system_id)


def count_tracked_teams(session: Session, *, glicko2_system_id: int | None = None) -> int:
    """Count teams with at least one Glicko-2 event."""
    return TEAM_GLICKO2_REPOSITORY.count_tracked_entities(session, system_id=glicko2_system_id)
