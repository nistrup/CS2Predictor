"""team_ratings table model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class TeamRating(Base):
    """Historical team rating events across Elo, Glicko-2, and OpenSkill."""

    __tablename__ = "team_ratings"
    __table_args__ = (
        UniqueConstraint(
            "rating_system_id",
            "team_id",
            "map_id",
            name="uq_team_ratings_system_team_map",
        ),
        CheckConstraint("actual_score IN (0.0, 1.0)", name="ck_team_ratings_actual_score"),
        CheckConstraint(
            "expected_score >= 0.0 AND expected_score <= 1.0",
            name="ck_team_ratings_expected_score",
        ),
        Index("idx_team_ratings_system", "rating_system_id"),
        Index(
            "idx_team_ratings_system_team_event",
            "rating_system_id",
            "team_id",
            "event_time",
            "map_id",
        ),
        Index("idx_team_ratings_match", "match_id"),
        Index("idx_team_ratings_map", "map_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rating_system_id: Mapped[int] = mapped_column(ForeignKey("rating_systems.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    opponent_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), nullable=False)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    map_id: Mapped[int] = mapped_column(ForeignKey("maps.id"), nullable=False)
    map_number: Mapped[int] = mapped_column(Integer, nullable=False)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    won: Mapped[bool] = mapped_column(Boolean, nullable=False)
    actual_score: Mapped[float] = mapped_column(Float, nullable=False)
    expected_score: Mapped[float] = mapped_column(Float, nullable=False)
    pre_ranking: Mapped[float] = mapped_column(Float, nullable=False)
    post_ranking: Mapped[float] = mapped_column(Float, nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False),
        nullable=False,
        server_default=func.now(),
    )
