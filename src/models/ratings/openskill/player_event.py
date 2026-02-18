"""player_openskill table model."""

from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.ratings.mixins import PlayerMapEventMixin


class PlayerOpenSkill(PlayerMapEventMixin, Base):
    """Historical player OpenSkill events (one row per player per map)."""

    __tablename__ = "player_openskill"
    __table_args__ = (
        UniqueConstraint(
            "openskill_system_id",
            "player_id",
            "map_id",
            name="uq_player_openskill_system_player_map",
        ),
        CheckConstraint("actual_score IN (0.0, 1.0)", name="ck_player_openskill_actual_score"),
        CheckConstraint(
            "expected_score >= 0.0 AND expected_score <= 1.0",
            name="ck_player_openskill_expected_score",
        ),
        CheckConstraint("pre_sigma > 0.0", name="ck_player_openskill_pre_sigma"),
        CheckConstraint("post_sigma > 0.0", name="ck_player_openskill_post_sigma"),
        Index("idx_player_openskill_system", "openskill_system_id"),
        Index(
            "idx_player_openskill_system_player_event",
            "openskill_system_id",
            "player_id",
            "event_time",
            "map_id",
        ),
        Index("idx_player_openskill_match", "match_id"),
        Index("idx_player_openskill_map", "map_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    openskill_system_id: Mapped[int] = mapped_column(ForeignKey("openskill_systems.id"), nullable=False)
    pre_mu: Mapped[float] = mapped_column(Float, nullable=False)
    pre_sigma: Mapped[float] = mapped_column(Float, nullable=False)
    pre_ordinal: Mapped[float] = mapped_column(Float, nullable=False)
    mu_delta: Mapped[float] = mapped_column(Float, nullable=False)
    sigma_delta: Mapped[float] = mapped_column(Float, nullable=False)
    ordinal_delta: Mapped[float] = mapped_column(Float, nullable=False)
    post_mu: Mapped[float] = mapped_column(Float, nullable=False)
    post_sigma: Mapped[float] = mapped_column(Float, nullable=False)
    post_ordinal: Mapped[float] = mapped_column(Float, nullable=False)
    beta: Mapped[float] = mapped_column(Float, nullable=False)
    kappa: Mapped[float] = mapped_column(Float, nullable=False)
    tau: Mapped[float] = mapped_column(Float, nullable=False)
    limit_sigma: Mapped[bool] = mapped_column(Boolean, nullable=False)
    balance: Mapped[bool] = mapped_column(Boolean, nullable=False)
    ordinal_z: Mapped[float] = mapped_column(Float, nullable=False)
    initial_mu: Mapped[float] = mapped_column(Float, nullable=False)
    initial_sigma: Mapped[float] = mapped_column(Float, nullable=False)
