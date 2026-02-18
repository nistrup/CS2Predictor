"""team_match_glicko2 table model."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.ratings.mixins import TeamMatchEventMixin


class TeamMatchGlicko2(TeamMatchEventMixin, Base):
    """Historical team Glicko-2 events (one row per team per match)."""

    __tablename__ = "team_match_glicko2"
    __table_args__ = (
        UniqueConstraint(
            "glicko2_system_id",
            "team_id",
            "match_id",
            name="uq_team_match_glicko2_system_team_match",
        ),
        CheckConstraint("actual_score IN (0.0, 1.0)", name="ck_team_match_glicko2_actual_score"),
        CheckConstraint(
            "expected_score >= 0.0 AND expected_score <= 1.0",
            name="ck_team_match_glicko2_expected_score",
        ),
        CheckConstraint("pre_rd > 0.0", name="ck_team_match_glicko2_pre_rd"),
        CheckConstraint("post_rd > 0.0", name="ck_team_match_glicko2_post_rd"),
        CheckConstraint("pre_volatility > 0.0", name="ck_team_match_glicko2_pre_volatility"),
        CheckConstraint("post_volatility > 0.0", name="ck_team_match_glicko2_post_volatility"),
        Index("idx_team_match_glicko2_system", "glicko2_system_id"),
        Index(
            "idx_team_match_glicko2_system_team_event",
            "glicko2_system_id",
            "team_id",
            "event_time",
            "match_id",
        ),
        Index("idx_team_match_glicko2_match", "match_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    glicko2_system_id: Mapped[int] = mapped_column(ForeignKey("glicko2_systems.id"), nullable=False)
    pre_rating: Mapped[float] = mapped_column(Float, nullable=False)
    pre_rd: Mapped[float] = mapped_column(Float, nullable=False)
    pre_volatility: Mapped[float] = mapped_column(Float, nullable=False)
    rating_delta: Mapped[float] = mapped_column(Float, nullable=False)
    rd_delta: Mapped[float] = mapped_column(Float, nullable=False)
    volatility_delta: Mapped[float] = mapped_column(Float, nullable=False)
    post_rating: Mapped[float] = mapped_column(Float, nullable=False)
    post_rd: Mapped[float] = mapped_column(Float, nullable=False)
    post_volatility: Mapped[float] = mapped_column(Float, nullable=False)
    tau: Mapped[float] = mapped_column(Float, nullable=False)
    rating_period_days: Mapped[float] = mapped_column(Float, nullable=False)
    initial_rating: Mapped[float] = mapped_column(Float, nullable=False)
    initial_rd: Mapped[float] = mapped_column(Float, nullable=False)
    initial_volatility: Mapped[float] = mapped_column(Float, nullable=False)
