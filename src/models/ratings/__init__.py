"""Rating-system ORM models."""

from models.ratings.elo import (
    EloSystem,
    PlayerElo,
    PlayerMapElo,
    PlayerMatchElo,
    TeamElo,
    TeamMapElo,
    TeamMatchElo,
)
from models.ratings.glicko2 import (
    Glicko2System,
    PlayerGlicko2,
    PlayerMapGlicko2,
    PlayerMatchGlicko2,
    TeamGlicko2,
    TeamMapGlicko2,
    TeamMatchGlicko2,
)
from models.ratings.openskill import (
    OpenSkillSystem,
    PlayerMapOpenSkill,
    PlayerMatchOpenSkill,
    PlayerOpenSkill,
    TeamMapOpenSkill,
    TeamMatchOpenSkill,
    TeamOpenSkill,
)

__all__ = [
    "EloSystem",
    "Glicko2System",
    "OpenSkillSystem",
    "PlayerElo",
    "PlayerMapElo",
    "PlayerMatchElo",
    "PlayerGlicko2",
    "PlayerMapGlicko2",
    "PlayerMatchGlicko2",
    "PlayerOpenSkill",
    "PlayerMapOpenSkill",
    "PlayerMatchOpenSkill",
    "TeamElo",
    "TeamMapElo",
    "TeamMatchElo",
    "TeamGlicko2",
    "TeamMapGlicko2",
    "TeamMatchGlicko2",
    "TeamOpenSkill",
    "TeamMapOpenSkill",
    "TeamMatchOpenSkill",
]
