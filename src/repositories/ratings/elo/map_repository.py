"""Persistence helpers for map-specific team Elo."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from domain.ratings.elo.map_specific_calculator import TeamMapEloEvent
from models.ratings.elo import EloSystem, TeamMapElo
from repositories.ratings.base import BaseRatingRepository
from repositories.ratings.common import fetch_map_results


def _team_map_elo_event_to_row(event: TeamMapEloEvent, elo_system_id: int) -> dict[str, Any]:
    return {
        "elo_system_id": elo_system_id,
        "team_id": event.team_id,
        "opponent_team_id": event.opponent_team_id,
        "match_id": event.match_id,
        "map_id": event.map_id,
        "map_number": event.map_number,
        "map_name": event.map_name,
        "event_time": event.event_time,
        "won": event.won,
        "actual_score": event.actual_score,
        "expected_score": event.expected_score,
        "pre_global_elo": event.pre_global_elo,
        "pre_map_elo": event.pre_map_elo,
        "pre_effective_elo": event.pre_effective_elo,
        "elo_delta": event.elo_delta,
        "post_global_elo": event.post_global_elo,
        "post_map_elo": event.post_map_elo,
        "post_effective_elo": event.post_effective_elo,
        "map_games_played_pre": event.map_games_played_pre,
        "map_blend_weight": event.map_blend_weight,
        "k_factor": event.k_factor,
        "scale_factor": event.scale_factor,
        "initial_elo": event.initial_elo,
        "map_prior_games": event.map_prior_games,
    }


TEAM_MAP_ELO_REPOSITORY = BaseRatingRepository[EloSystem, TeamMapElo, TeamMapEloEvent](
    system_model=EloSystem,
    event_model=TeamMapElo,
    system_id_column="elo_system_id",
    entity_id_column="team_id",
    event_to_row=_team_map_elo_event_to_row,
    reflect_tables=("teams", "matches", "maps", "team_map_elo", "elo_systems"),
)


def ensure_team_map_elo_schema(engine: Engine) -> None:
    """Create elo_systems/team_map_elo tables and indexes if needed."""
    TEAM_MAP_ELO_REPOSITORY.ensure_schema(engine)


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
        TEAM_MAP_ELO_REPOSITORY.upsert_system(
            session,
            name=name,
            description=description,
            config_json=config_json,
        ),
    )


def delete_team_map_elo_for_system(session: Session, elo_system_id: int) -> None:
    """Delete existing map-specific events for a single Elo system."""
    TEAM_MAP_ELO_REPOSITORY.delete_events_for_system(session, elo_system_id)


def insert_team_map_elo_events(
    session: Session,
    events: Sequence[TeamMapEloEvent],
    *,
    elo_system_id: int,
) -> None:
    """Bulk insert map-specific Elo events."""
    TEAM_MAP_ELO_REPOSITORY.insert_events(session, events, system_id=elo_system_id)


def count_tracked_map_teams(session: Session, *, elo_system_id: int | None = None) -> int:
    """Count teams with at least one map-specific Elo event."""
    return TEAM_MAP_ELO_REPOSITORY.count_tracked_entities(session, system_id=elo_system_id)
