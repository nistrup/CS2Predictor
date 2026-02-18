"""openskill_systems table model."""

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base
from models.ratings.mixins import RatingSystemMixin


class OpenSkillSystem(RatingSystemMixin, Base):
    """Configuration metadata for a specific OpenSkill system implementation."""

    __tablename__ = "openskill_systems"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
