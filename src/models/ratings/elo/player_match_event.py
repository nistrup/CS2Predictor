"""player_match_elo table model."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.ratings.mixins import PlayerMatchEventMixin


class PlayerMatchElo(PlayerMatchEventMixin, Base):
    """Historical player Elo events (one row per player per match)."""

    __tablename__ = "player_match_elo"
    __table_args__ = (
        UniqueConstraint(
            "elo_system_id",
            "player_id",
            "match_id",
            name="uq_player_match_elo_system_player_match",
        ),
        CheckConstraint("actual_score IN (0.0, 1.0)", name="ck_player_match_elo_actual_score"),
        CheckConstraint(
            "expected_score >= 0.0 AND expected_score <= 1.0",
            name="ck_player_match_elo_expected_score",
        ),
        Index("idx_player_match_elo_system", "elo_system_id"),
        Index(
            "idx_player_match_elo_system_player_event",
            "elo_system_id",
            "player_id",
            "event_time",
            "match_id",
        ),
        Index("idx_player_match_elo_match", "match_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    elo_system_id: Mapped[int] = mapped_column(ForeignKey("elo_systems.id"), nullable=False)
    pre_elo: Mapped[float] = mapped_column(Float, nullable=False)
    elo_delta: Mapped[float] = mapped_column(Float, nullable=False)
    post_elo: Mapped[float] = mapped_column(Float, nullable=False)
    k_factor: Mapped[float] = mapped_column(Float, nullable=False)
    scale_factor: Mapped[float] = mapped_column(Float, nullable=False)
    initial_elo: Mapped[float] = mapped_column(Float, nullable=False)
