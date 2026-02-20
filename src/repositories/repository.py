"""Unified persistence helpers for map-level team ratings."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, is_dataclass
from typing import Any, cast

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from models import RatingSystem, TeamRating
from repositories.base import BaseRatingRepository

_COMMON_EVENT_FIELDS = (
    "team_id",
    "opponent_team_id",
    "match_id",
    "map_id",
    "map_number",
    "event_time",
    "won",
    "actual_score",
    "expected_score",
)
_RANKING_FIELD_PAIRS = (
    ("pre_elo", "post_elo"),
    ("pre_rating", "post_rating"),
    ("pre_ordinal", "post_ordinal"),
)


def _to_event_payload(event: Any) -> dict[str, Any]:
    if is_dataclass(event):
        payload = asdict(event)
        if isinstance(payload, dict):
            return payload
    if hasattr(event, "__dict__"):
        return dict(vars(event))
    raise TypeError(f"Unsupported event payload type: {type(event)!r}")


def _extract_ranking(payload: dict[str, Any]) -> tuple[float, float]:
    for pre_key, post_key in _RANKING_FIELD_PAIRS:
        if pre_key in payload and post_key in payload:
            pre_value = payload.pop(pre_key)
            post_value = payload.pop(post_key)
            if pre_value is None or post_value is None:
                raise ValueError(
                    f"Ranking fields {pre_key}/{post_key} cannot be None for event payload."
                )
            return float(pre_value), float(post_value)
    available = ", ".join(sorted(payload.keys()))
    raise ValueError(
        "Could not identify ranking fields on event payload; "
        f"expected one of {_RANKING_FIELD_PAIRS}, got keys=[{available}]"
    )


def _event_to_row(event: Any, rating_system_id: int) -> dict[str, Any]:
    payload = _to_event_payload(event)

    missing_fields = [field for field in _COMMON_EVENT_FIELDS if field not in payload]
    if missing_fields:
        raise ValueError(f"Event payload missing required fields: {missing_fields}")

    row: dict[str, Any] = {
        "rating_system_id": rating_system_id,
        "team_id": payload.pop("team_id"),
        "opponent_team_id": payload.pop("opponent_team_id"),
        "match_id": payload.pop("match_id"),
        "map_id": payload.pop("map_id"),
        "map_number": payload.pop("map_number"),
        "event_time": payload.pop("event_time"),
        "won": payload.pop("won"),
        "actual_score": payload.pop("actual_score"),
        "expected_score": payload.pop("expected_score"),
    }
    pre_ranking, post_ranking = _extract_ranking(payload)
    row["pre_ranking"] = pre_ranking
    row["post_ranking"] = post_ranking
    row["details_json"] = payload
    return row


TEAM_RATING_REPOSITORY = BaseRatingRepository[RatingSystem, TeamRating, Any](
    system_model=RatingSystem,
    event_model=TeamRating,
    system_id_column="rating_system_id",
    entity_id_column="team_id",
    event_to_row=_event_to_row,
    reflect_tables=("teams", "matches", "maps", "team_ratings", "rating_systems"),
    system_match_fields=("algorithm", "granularity", "subject"),
)


def ensure_team_rating_schema(engine: Engine) -> None:
    """Create unified rating schema and indexes if they do not exist."""
    TEAM_RATING_REPOSITORY.ensure_schema(engine)


def upsert_rating_system(
    session: Session,
    *,
    algorithm: str,
    granularity: str,
    subject: str,
    name: str,
    description: str | None,
    config_json: dict[str, Any],
) -> RatingSystem:
    """Create or update one rating system definition."""
    return cast(
        RatingSystem,
        TEAM_RATING_REPOSITORY.upsert_system(
            session,
            name=name,
            description=description,
            config_json=config_json,
            system_fields={
                "algorithm": algorithm,
                "granularity": granularity,
                "subject": subject,
            },
        ),
    )


def delete_team_ratings_for_system(session: Session, rating_system_id: int) -> None:
    """Delete existing events for one rating system."""
    TEAM_RATING_REPOSITORY.delete_events_for_system(session, rating_system_id)


def insert_team_rating_events(
    session: Session,
    events: Sequence[Any],
    *,
    rating_system_id: int,
) -> None:
    """Bulk insert team rating events."""
    TEAM_RATING_REPOSITORY.insert_events(session, events, system_id=rating_system_id)


def count_tracked_teams(session: Session, *, rating_system_id: int | None = None) -> int:
    """Count teams with at least one rating event."""
    return TEAM_RATING_REPOSITORY.count_tracked_entities(session, system_id=rating_system_id)
