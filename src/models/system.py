"""rating_systems table model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class RatingSystem(Base):
    """Configuration metadata for one algorithm/granularity/subject rating system."""

    __tablename__ = "rating_systems"
    __table_args__ = (
        UniqueConstraint(
            "algorithm",
            "granularity",
            "subject",
            "name",
            name="uq_rating_system_identity",
        ),
        Index(
            "idx_rating_system_lookup",
            "algorithm",
            "granularity",
            "subject",
            "name",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    algorithm: Mapped[str] = mapped_column(
        Enum(
            "elo",
            "glicko2",
            "openskill",
            name="rating_algorithm",
            native_enum=False,
        ),
        nullable=False,
    )
    granularity: Mapped[str] = mapped_column(String(32), nullable=False)
    subject: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
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
