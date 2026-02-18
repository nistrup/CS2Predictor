"""team_map_elo table model."""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.ratings.mixins import TeamMapSpecificEventMixin


class TeamMapElo(TeamMapSpecificEventMixin, Base):
    """Historical map-specific team Elo events (one row per team per map)."""

    __tablename__ = "team_map_elo"
    __table_args__ = (
        UniqueConstraint("elo_system_id", "team_id", "map_id", name="uq_team_map_elo_system_team_map"),
        CheckConstraint("actual_score IN (0.0, 1.0)", name="ck_team_map_elo_actual_score"),
        CheckConstraint(
            "expected_score >= 0.0 AND expected_score <= 1.0",
            name="ck_team_map_elo_expected_score",
        ),
        CheckConstraint("map_blend_weight >= 0.0 AND map_blend_weight <= 1.0", name="ck_team_map_elo_blend_weight"),
        CheckConstraint("map_games_played_pre >= 0", name="ck_team_map_elo_games_pre"),
        CheckConstraint("map_prior_games > 0.0", name="ck_team_map_elo_map_prior_games"),
        Index("idx_team_map_elo_system", "elo_system_id"),
        Index("idx_team_map_elo_system_team_event", "elo_system_id", "team_id", "event_time", "map_id"),
        Index("idx_team_map_elo_map_name", "elo_system_id", "map_name", "post_effective_elo"),
        Index("idx_team_map_elo_match", "match_id"),
        Index("idx_team_map_elo_map", "map_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    elo_system_id: Mapped[int] = mapped_column(ForeignKey("elo_systems.id"), nullable=False)
    pre_global_elo: Mapped[float] = mapped_column(Float, nullable=False)
    pre_map_elo: Mapped[float] = mapped_column(Float, nullable=False)
    pre_effective_elo: Mapped[float] = mapped_column(Float, nullable=False)
    elo_delta: Mapped[float] = mapped_column(Float, nullable=False)
    post_global_elo: Mapped[float] = mapped_column(Float, nullable=False)
    post_map_elo: Mapped[float] = mapped_column(Float, nullable=False)
    post_effective_elo: Mapped[float] = mapped_column(Float, nullable=False)
    k_factor: Mapped[float] = mapped_column(Float, nullable=False)
    scale_factor: Mapped[float] = mapped_column(Float, nullable=False)
    initial_elo: Mapped[float] = mapped_column(Float, nullable=False)
