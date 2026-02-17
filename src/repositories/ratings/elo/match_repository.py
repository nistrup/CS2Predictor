"""Persistence helpers for match-level team Elo."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from domain.ratings.elo.match_calculator import TeamMatchEloEvent
from models.ratings.elo import EloSystem, TeamMatchElo
from repositories.ratings.base import BaseRatingRepository
from repositories.ratings.common import fetch_match_results


def _team_match_elo_event_to_row(event: TeamMatchEloEvent, elo_system_id: int) -> dict[str, Any]:
    return {
        "elo_system_id": elo_system_id,
        "team_id": event.team_id,
        "opponent_team_id": event.opponent_team_id,
        "match_id": event.match_id,
        "event_time": event.event_time,
        "won": event.won,
        "actual_score": event.actual_score,
        "expected_score": event.expected_score,
        "pre_elo": event.pre_elo,
        "elo_delta": event.elo_delta,
        "post_elo": event.post_elo,
        "team_maps_won": event.team_maps_won,
        "opponent_maps_won": event.opponent_maps_won,
        "k_factor": event.k_factor,
        "scale_factor": event.scale_factor,
        "initial_elo": event.initial_elo,
    }


TEAM_MATCH_ELO_REPOSITORY = BaseRatingRepository[EloSystem, TeamMatchElo, TeamMatchEloEvent](
    system_model=EloSystem,
    event_model=TeamMatchElo,
    system_id_column="elo_system_id",
    entity_id_column="team_id",
    event_to_row=_team_match_elo_event_to_row,
    reflect_tables=("teams", "matches", "team_match_elo", "elo_systems"),
)


def ensure_team_match_elo_schema(engine: Engine) -> None:
    """Create elo_systems/team_match_elo tables and indexes if needed."""
    TEAM_MATCH_ELO_REPOSITORY.ensure_schema(engine)


def upsert_elo_system(
    session: Session,
    *,
    name: str,
    description: str | None,
    config_json: dict[str, Any],
) -> EloSystem:
    """Create or update an Elo system definition."""
    return cast(
        EloSystem,
        TEAM_MATCH_ELO_REPOSITORY.upsert_system(
            session,
            name=name,
            description=description,
            config_json=config_json,
        ),
    )


def delete_team_match_elo_for_system(session: Session, elo_system_id: int) -> None:
    """Delete existing match-level events for a single Elo system."""
    TEAM_MATCH_ELO_REPOSITORY.delete_events_for_system(session, elo_system_id)


def insert_team_match_elo_events(
    session: Session,
    events: Sequence[TeamMatchEloEvent],
    *,
    elo_system_id: int,
) -> None:
    """Bulk insert match-level Elo events."""
    TEAM_MATCH_ELO_REPOSITORY.insert_events(session, events, system_id=elo_system_id)


def count_tracked_match_teams(session: Session, *, elo_system_id: int | None = None) -> int:
    """Count teams with at least one match-level Elo event."""
    return TEAM_MATCH_ELO_REPOSITORY.count_tracked_entities(session, system_id=elo_system_id)
