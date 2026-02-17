"""Rating-system domain modules."""

from domain.ratings.common import TeamMapResult, TeamMatchResult
from domain.ratings.protocol import Granularity, Subject

__all__ = ["Granularity", "Subject", "TeamMapResult", "TeamMatchResult"]
