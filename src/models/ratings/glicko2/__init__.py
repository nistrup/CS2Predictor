"""Glicko-2 ORM models."""

from models.ratings.glicko2.event import TeamGlicko2
from models.ratings.glicko2.system import Glicko2System

__all__ = ["Glicko2System", "TeamGlicko2"]
