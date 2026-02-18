"""SQLAlchemy mixins for common rating event and system table columns."""

from __future__ import annotations

from datetime import datetime

from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column


class RatingSystemMixin:
    """Common columns for rating system metadata tables (Elo, Glicko-2, OpenSkill)."""

    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )


class TeamMapEventMixin:
    """Common columns for team map-level events (no system_id; add in concrete class)."""

    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    opponent_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    map_id: Mapped[int] = mapped_column(ForeignKey("maps.id"), nullable=False)
    map_number: Mapped[int] = mapped_column(Integer, nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    won: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actual_score: Mapped[float] = mapped_column(Float, nullable=False)
    expected_score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )


class TeamMatchEventMixin:
    """Common columns for team match-level events (no map_id/map_number; has team_maps_won/opponent_maps_won)."""

    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    opponent_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    won: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actual_score: Mapped[float] = mapped_column(Float, nullable=False)
    expected_score: Mapped[float] = mapped_column(Float, nullable=False)
    team_maps_won: Mapped[int] = mapped_column(Integer, nullable=False)
    opponent_maps_won: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )


class TeamMapSpecificEventMixin(TeamMapEventMixin):
    """Team map-level plus map-specific columns (map_name, blend, prior games)."""

    map_name: Mapped[str] = mapped_column(String(64), nullable=False)
    map_games_played_pre: Mapped[int] = mapped_column(Integer, nullable=False)
    map_blend_weight: Mapped[float] = mapped_column(Float, nullable=False)
    map_prior_games: Mapped[float] = mapped_column(Float, nullable=False)


class PlayerMapEventMixin:
    """Common columns for player map-level events."""

    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    opponent_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    map_id: Mapped[int] = mapped_column(ForeignKey("maps.id"), nullable=False)
    map_number: Mapped[int] = mapped_column(Integer, nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    won: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actual_score: Mapped[float] = mapped_column(Float, nullable=False)
    expected_score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )


class PlayerMatchEventMixin:
    """Common columns for player match-level events."""

    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    opponent_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    won: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actual_score: Mapped[float] = mapped_column(Float, nullable=False)
    expected_score: Mapped[float] = mapped_column(Float, nullable=False)
    team_maps_won: Mapped[int] = mapped_column(Integer, nullable=False)
    opponent_maps_won: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )


class PlayerMapSpecificEventMixin(PlayerMapEventMixin):
    """Player map-level plus map-specific columns."""

    map_name: Mapped[str] = mapped_column(String(64), nullable=False)
    map_games_played_pre: Mapped[int] = mapped_column(Integer, nullable=False)
    map_blend_weight: Mapped[float] = mapped_column(Float, nullable=False)
    map_prior_games: Mapped[float] = mapped_column(Float, nullable=False)
