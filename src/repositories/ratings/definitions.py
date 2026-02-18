"""Central repository definitions: all 18 rating repositories via from_models()."""

from __future__ import annotations

from domain.ratings.elo.calculator import TeamEloEvent
from domain.ratings.elo.map_specific_calculator import TeamMapEloEvent
from domain.ratings.elo.match_calculator import TeamMatchEloEvent
from domain.ratings.elo.player_calculator import PlayerEloEvent
from domain.ratings.elo.player_map_specific_calculator import PlayerMapEloEvent
from domain.ratings.elo.player_match_calculator import PlayerMatchEloEvent
from domain.ratings.glicko2.calculator import TeamGlicko2Event
from domain.ratings.glicko2.map_specific_calculator import TeamMapGlicko2Event
from domain.ratings.glicko2.match_calculator import TeamMatchGlicko2Event
from domain.ratings.glicko2.player_calculator import PlayerGlicko2Event
from domain.ratings.glicko2.player_map_specific_calculator import PlayerMapGlicko2Event
from domain.ratings.glicko2.player_match_calculator import PlayerMatchGlicko2Event
from domain.ratings.openskill.calculator import TeamOpenSkillEvent
from domain.ratings.openskill.map_specific_calculator import TeamMapOpenSkillEvent
from domain.ratings.openskill.match_calculator import TeamMatchOpenSkillEvent
from domain.ratings.openskill.player_calculator import PlayerOpenSkillEvent
from domain.ratings.openskill.player_map_specific_calculator import PlayerMapOpenSkillEvent
from domain.ratings.openskill.player_match_calculator import PlayerMatchOpenSkillEvent
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
    PlayerOpenSkill,
    PlayerMapOpenSkill,
    PlayerMatchOpenSkill,
    TeamOpenSkill,
    TeamMapOpenSkill,
    TeamMatchOpenSkill,
)
from repositories.ratings.base import BaseRatingRepository
from repositories.ratings.elo_legacy_migration import migrate_legacy_team_elo_schema

# Elo team
TEAM_ELO_REPOSITORY = BaseRatingRepository.from_models(
    system_model=EloSystem,
    event_model=TeamElo,
    domain_event_class=TeamEloEvent,
    system_id_column="elo_system_id",
    entity_id_column="team_id",
    reflect_tables=("teams", "matches", "maps", "team_elo", "elo_systems"),
    schema_migration=migrate_legacy_team_elo_schema,
    enable_copy=True,
)
ensure_team_elo_schema = TEAM_ELO_REPOSITORY.ensure_schema

TEAM_MATCH_ELO_REPOSITORY = BaseRatingRepository.from_models(
    system_model=EloSystem,
    event_model=TeamMatchElo,
    domain_event_class=TeamMatchEloEvent,
    system_id_column="elo_system_id",
    entity_id_column="team_id",
    reflect_tables=("teams", "matches", "team_match_elo", "elo_systems"),
    enable_copy=False,
)
ensure_team_match_elo_schema = TEAM_MATCH_ELO_REPOSITORY.ensure_schema

TEAM_MAP_ELO_REPOSITORY = BaseRatingRepository.from_models(
    system_model=EloSystem,
    event_model=TeamMapElo,
    domain_event_class=TeamMapEloEvent,
    system_id_column="elo_system_id",
    entity_id_column="team_id",
    reflect_tables=("teams", "matches", "maps", "team_map_elo", "elo_systems"),
    enable_copy=False,
)
ensure_team_map_elo_schema = TEAM_MAP_ELO_REPOSITORY.ensure_schema

# Elo player
PLAYER_ELO_REPOSITORY = BaseRatingRepository.from_models(
    system_model=EloSystem,
    event_model=PlayerElo,
    domain_event_class=PlayerEloEvent,
    system_id_column="elo_system_id",
    entity_id_column="player_id",
    reflect_tables=("players", "teams", "matches", "maps", "player_elo", "elo_systems"),
    enable_copy=True,
)
ensure_player_elo_schema = PLAYER_ELO_REPOSITORY.ensure_schema

PLAYER_MATCH_ELO_REPOSITORY = BaseRatingRepository.from_models(
    system_model=EloSystem,
    event_model=PlayerMatchElo,
    domain_event_class=PlayerMatchEloEvent,
    system_id_column="elo_system_id",
    entity_id_column="player_id",
    reflect_tables=("players", "teams", "matches", "player_match_elo", "elo_systems"),
    enable_copy=False,
)
ensure_player_match_elo_schema = PLAYER_MATCH_ELO_REPOSITORY.ensure_schema

PLAYER_MAP_ELO_REPOSITORY = BaseRatingRepository.from_models(
    system_model=EloSystem,
    event_model=PlayerMapElo,
    domain_event_class=PlayerMapEloEvent,
    system_id_column="elo_system_id",
    entity_id_column="player_id",
    reflect_tables=("players", "teams", "matches", "maps", "player_map_elo", "elo_systems"),
    enable_copy=False,
)
ensure_player_map_elo_schema = PLAYER_MAP_ELO_REPOSITORY.ensure_schema

# Glicko-2 team
TEAM_GLICKO2_REPOSITORY = BaseRatingRepository.from_models(
    system_model=Glicko2System,
    event_model=TeamGlicko2,
    domain_event_class=TeamGlicko2Event,
    system_id_column="glicko2_system_id",
    entity_id_column="team_id",
    reflect_tables=("teams", "matches", "maps", "team_glicko2", "glicko2_systems"),
    enable_copy=True,
)
ensure_team_glicko2_schema = TEAM_GLICKO2_REPOSITORY.ensure_schema

TEAM_MATCH_GLICKO2_REPOSITORY = BaseRatingRepository.from_models(
    system_model=Glicko2System,
    event_model=TeamMatchGlicko2,
    domain_event_class=TeamMatchGlicko2Event,
    system_id_column="glicko2_system_id",
    entity_id_column="team_id",
    reflect_tables=("teams", "matches", "team_match_glicko2", "glicko2_systems"),
    enable_copy=False,
)
ensure_team_match_glicko2_schema = TEAM_MATCH_GLICKO2_REPOSITORY.ensure_schema

TEAM_MAP_GLICKO2_REPOSITORY = BaseRatingRepository.from_models(
    system_model=Glicko2System,
    event_model=TeamMapGlicko2,
    domain_event_class=TeamMapGlicko2Event,
    system_id_column="glicko2_system_id",
    entity_id_column="team_id",
    reflect_tables=("teams", "matches", "maps", "team_map_glicko2", "glicko2_systems"),
    enable_copy=False,
)
ensure_team_map_glicko2_schema = TEAM_MAP_GLICKO2_REPOSITORY.ensure_schema

# Glicko-2 player
PLAYER_GLICKO2_REPOSITORY = BaseRatingRepository.from_models(
    system_model=Glicko2System,
    event_model=PlayerGlicko2,
    domain_event_class=PlayerGlicko2Event,
    system_id_column="glicko2_system_id",
    entity_id_column="player_id",
    reflect_tables=("players", "teams", "matches", "maps", "player_glicko2", "glicko2_systems"),
    enable_copy=True,
)
ensure_player_glicko2_schema = PLAYER_GLICKO2_REPOSITORY.ensure_schema

PLAYER_MATCH_GLICKO2_REPOSITORY = BaseRatingRepository.from_models(
    system_model=Glicko2System,
    event_model=PlayerMatchGlicko2,
    domain_event_class=PlayerMatchGlicko2Event,
    system_id_column="glicko2_system_id",
    entity_id_column="player_id",
    reflect_tables=("players", "teams", "matches", "player_match_glicko2", "glicko2_systems"),
    enable_copy=False,
)
ensure_player_match_glicko2_schema = PLAYER_MATCH_GLICKO2_REPOSITORY.ensure_schema

PLAYER_MAP_GLICKO2_REPOSITORY = BaseRatingRepository.from_models(
    system_model=Glicko2System,
    event_model=PlayerMapGlicko2,
    domain_event_class=PlayerMapGlicko2Event,
    system_id_column="glicko2_system_id",
    entity_id_column="player_id",
    reflect_tables=("players", "teams", "matches", "maps", "player_map_glicko2", "glicko2_systems"),
    enable_copy=False,
)
ensure_player_map_glicko2_schema = PLAYER_MAP_GLICKO2_REPOSITORY.ensure_schema

# OpenSkill team
TEAM_OPENSKILL_REPOSITORY = BaseRatingRepository.from_models(
    system_model=OpenSkillSystem,
    event_model=TeamOpenSkill,
    domain_event_class=TeamOpenSkillEvent,
    system_id_column="openskill_system_id",
    entity_id_column="team_id",
    reflect_tables=("teams", "matches", "maps", "team_openskill", "openskill_systems"),
    enable_copy=True,
)
ensure_team_openskill_schema = TEAM_OPENSKILL_REPOSITORY.ensure_schema

TEAM_MATCH_OPENSKILL_REPOSITORY = BaseRatingRepository.from_models(
    system_model=OpenSkillSystem,
    event_model=TeamMatchOpenSkill,
    domain_event_class=TeamMatchOpenSkillEvent,
    system_id_column="openskill_system_id",
    entity_id_column="team_id",
    reflect_tables=("teams", "matches", "team_match_openskill", "openskill_systems"),
    enable_copy=False,
)
ensure_team_match_openskill_schema = TEAM_MATCH_OPENSKILL_REPOSITORY.ensure_schema

TEAM_MAP_OPENSKILL_REPOSITORY = BaseRatingRepository.from_models(
    system_model=OpenSkillSystem,
    event_model=TeamMapOpenSkill,
    domain_event_class=TeamMapOpenSkillEvent,
    system_id_column="openskill_system_id",
    entity_id_column="team_id",
    reflect_tables=("teams", "matches", "maps", "team_map_openskill", "openskill_systems"),
    enable_copy=False,
)
ensure_team_map_openskill_schema = TEAM_MAP_OPENSKILL_REPOSITORY.ensure_schema

# OpenSkill player
PLAYER_OPENSKILL_REPOSITORY = BaseRatingRepository.from_models(
    system_model=OpenSkillSystem,
    event_model=PlayerOpenSkill,
    domain_event_class=PlayerOpenSkillEvent,
    system_id_column="openskill_system_id",
    entity_id_column="player_id",
    reflect_tables=("players", "teams", "matches", "maps", "player_openskill", "openskill_systems"),
    enable_copy=True,
)
ensure_player_openskill_schema = PLAYER_OPENSKILL_REPOSITORY.ensure_schema

PLAYER_MATCH_OPENSKILL_REPOSITORY = BaseRatingRepository.from_models(
    system_model=OpenSkillSystem,
    event_model=PlayerMatchOpenSkill,
    domain_event_class=PlayerMatchOpenSkillEvent,
    system_id_column="openskill_system_id",
    entity_id_column="player_id",
    reflect_tables=("players", "teams", "matches", "player_match_openskill", "openskill_systems"),
    enable_copy=False,
)
ensure_player_match_openskill_schema = PLAYER_MATCH_OPENSKILL_REPOSITORY.ensure_schema

PLAYER_MAP_OPENSKILL_REPOSITORY = BaseRatingRepository.from_models(
    system_model=OpenSkillSystem,
    event_model=PlayerMapOpenSkill,
    domain_event_class=PlayerMapOpenSkillEvent,
    system_id_column="openskill_system_id",
    entity_id_column="player_id",
    reflect_tables=("players", "teams", "matches", "maps", "player_map_openskill", "openskill_systems"),
    enable_copy=False,
)
ensure_player_map_openskill_schema = PLAYER_MAP_OPENSKILL_REPOSITORY.ensure_schema
