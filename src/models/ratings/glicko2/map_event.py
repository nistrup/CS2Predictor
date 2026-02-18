"""team_map_glicko2 table model."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.ratings.mixins import TeamMapSpecificEventMixin


class TeamMapGlicko2(TeamMapSpecificEventMixin, Base):
    """Historical map-specific team Glicko-2 events (one row per team per map)."""

    __tablename__ = "team_map_glicko2"
    __table_args__ = (
        UniqueConstraint("glicko2_system_id", "team_id", "map_id", name="uq_team_map_glicko2_system_team_map"),
        CheckConstraint("actual_score IN (0.0, 1.0)", name="ck_team_map_glicko2_actual_score"),
        CheckConstraint(
            "expected_score >= 0.0 AND expected_score <= 1.0",
            name="ck_team_map_glicko2_expected_score",
        ),
        CheckConstraint("map_blend_weight >= 0.0 AND map_blend_weight <= 1.0", name="ck_team_map_glicko2_blend_weight"),
        CheckConstraint("map_games_played_pre >= 0", name="ck_team_map_glicko2_games_pre"),
        CheckConstraint("map_prior_games > 0.0", name="ck_team_map_glicko2_map_prior_games"),
        CheckConstraint("pre_global_rd > 0.0", name="ck_team_map_glicko2_pre_global_rd"),
        CheckConstraint("pre_map_rd > 0.0", name="ck_team_map_glicko2_pre_map_rd"),
        CheckConstraint("pre_effective_rd > 0.0", name="ck_team_map_glicko2_pre_effective_rd"),
        CheckConstraint("post_global_rd > 0.0", name="ck_team_map_glicko2_post_global_rd"),
        CheckConstraint("post_map_rd > 0.0", name="ck_team_map_glicko2_post_map_rd"),
        CheckConstraint("post_effective_rd > 0.0", name="ck_team_map_glicko2_post_effective_rd"),
        CheckConstraint("pre_global_volatility > 0.0", name="ck_team_map_glicko2_pre_global_vol"),
        CheckConstraint("pre_map_volatility > 0.0", name="ck_team_map_glicko2_pre_map_vol"),
        CheckConstraint("pre_effective_volatility > 0.0", name="ck_team_map_glicko2_pre_effective_vol"),
        CheckConstraint("post_global_volatility > 0.0", name="ck_team_map_glicko2_post_global_vol"),
        CheckConstraint("post_map_volatility > 0.0", name="ck_team_map_glicko2_post_map_vol"),
        CheckConstraint("post_effective_volatility > 0.0", name="ck_team_map_glicko2_post_effective_vol"),
        Index("idx_team_map_glicko2_system", "glicko2_system_id"),
        Index(
            "idx_team_map_glicko2_system_team_event",
            "glicko2_system_id",
            "team_id",
            "event_time",
            "map_id",
        ),
        Index("idx_team_map_glicko2_map_name", "glicko2_system_id", "map_name", "post_effective_rating"),
        Index("idx_team_map_glicko2_match", "match_id"),
        Index("idx_team_map_glicko2_map", "map_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    glicko2_system_id: Mapped[int] = mapped_column(ForeignKey("glicko2_systems.id"), nullable=False)
    pre_global_rating: Mapped[float] = mapped_column(Float, nullable=False)
    pre_map_rating: Mapped[float] = mapped_column(Float, nullable=False)
    pre_effective_rating: Mapped[float] = mapped_column(Float, nullable=False)
    pre_global_rd: Mapped[float] = mapped_column(Float, nullable=False)
    pre_map_rd: Mapped[float] = mapped_column(Float, nullable=False)
    pre_effective_rd: Mapped[float] = mapped_column(Float, nullable=False)
    pre_global_volatility: Mapped[float] = mapped_column(Float, nullable=False)
    pre_map_volatility: Mapped[float] = mapped_column(Float, nullable=False)
    pre_effective_volatility: Mapped[float] = mapped_column(Float, nullable=False)
    rating_delta: Mapped[float] = mapped_column(Float, nullable=False)
    rd_delta: Mapped[float] = mapped_column(Float, nullable=False)
    volatility_delta: Mapped[float] = mapped_column(Float, nullable=False)
    post_global_rating: Mapped[float] = mapped_column(Float, nullable=False)
    post_map_rating: Mapped[float] = mapped_column(Float, nullable=False)
    post_effective_rating: Mapped[float] = mapped_column(Float, nullable=False)
    post_global_rd: Mapped[float] = mapped_column(Float, nullable=False)
    post_map_rd: Mapped[float] = mapped_column(Float, nullable=False)
    post_effective_rd: Mapped[float] = mapped_column(Float, nullable=False)
    post_global_volatility: Mapped[float] = mapped_column(Float, nullable=False)
    post_map_volatility: Mapped[float] = mapped_column(Float, nullable=False)
    post_effective_volatility: Mapped[float] = mapped_column(Float, nullable=False)
    tau: Mapped[float] = mapped_column(Float, nullable=False)
    rating_period_days: Mapped[float] = mapped_column(Float, nullable=False)
    initial_rating: Mapped[float] = mapped_column(Float, nullable=False)
    initial_rd: Mapped[float] = mapped_column(Float, nullable=False)
    initial_volatility: Mapped[float] = mapped_column(Float, nullable=False)
