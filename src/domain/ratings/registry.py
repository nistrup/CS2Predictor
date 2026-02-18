"""Registry of available rating system implementations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Type

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from domain.ratings.config_base import BaseSystemConfig
from domain.ratings.elo.calculator import TeamEloCalculator
from domain.ratings.elo.config import load_elo_system_configs
from domain.ratings.elo.map_specific_calculator import TeamMapSpecificEloCalculator
from domain.ratings.elo.map_specific_config import load_map_specific_elo_system_configs
from domain.ratings.elo.match_calculator import TeamMatchEloCalculator
from domain.ratings.elo.player_calculator import PlayerEloCalculator
from domain.ratings.elo.player_map_specific_calculator import PlayerMapSpecificEloCalculator
from domain.ratings.elo.player_match_calculator import PlayerMatchEloCalculator
from domain.ratings.glicko2.calculator import TeamGlicko2Calculator
from domain.ratings.glicko2.config import load_glicko2_system_configs
from domain.ratings.glicko2.map_specific_calculator import TeamMapSpecificGlicko2Calculator
from domain.ratings.glicko2.map_specific_config import load_map_specific_glicko2_system_configs
from domain.ratings.glicko2.match_calculator import TeamMatchGlicko2Calculator
from domain.ratings.glicko2.player_calculator import PlayerGlicko2Calculator
from domain.ratings.glicko2.player_map_specific_calculator import PlayerMapSpecificGlicko2Calculator
from domain.ratings.glicko2.player_match_calculator import PlayerMatchGlicko2Calculator
from domain.ratings.openskill.calculator import TeamOpenSkillCalculator
from domain.ratings.openskill.config import load_openskill_system_configs
from domain.ratings.openskill.map_specific_calculator import TeamMapSpecificOpenSkillCalculator
from domain.ratings.openskill.map_specific_config import load_map_specific_openskill_system_configs
from domain.ratings.openskill.match_calculator import TeamMatchOpenSkillCalculator
from domain.ratings.openskill.player_calculator import PlayerOpenSkillCalculator
from domain.ratings.openskill.player_map_specific_calculator import PlayerMapSpecificOpenSkillCalculator
from domain.ratings.openskill.player_match_calculator import PlayerMatchOpenSkillCalculator
from domain.ratings.protocol import Granularity, Subject
from repositories.ratings.base import BaseRatingRepository
from repositories.ratings.common import (
    fetch_map_results,
    fetch_match_results,
    fetch_player_map_results,
    fetch_player_match_results,
)
from repositories.ratings.definitions import (
    PLAYER_ELO_REPOSITORY,
    PLAYER_MAP_ELO_REPOSITORY,
    PLAYER_MATCH_ELO_REPOSITORY,
    PLAYER_GLICKO2_REPOSITORY,
    PLAYER_MAP_GLICKO2_REPOSITORY,
    PLAYER_MATCH_GLICKO2_REPOSITORY,
    PLAYER_MAP_OPENSKILL_REPOSITORY,
    PLAYER_MATCH_OPENSKILL_REPOSITORY,
    PLAYER_OPENSKILL_REPOSITORY,
    TEAM_ELO_REPOSITORY,
    TEAM_MAP_ELO_REPOSITORY,
    TEAM_MATCH_ELO_REPOSITORY,
    TEAM_GLICKO2_REPOSITORY,
    TEAM_MAP_GLICKO2_REPOSITORY,
    TEAM_MATCH_GLICKO2_REPOSITORY,
    TEAM_MAP_OPENSKILL_REPOSITORY,
    TEAM_MATCH_OPENSKILL_REPOSITORY,
    TEAM_OPENSKILL_REPOSITORY,
)

ROOT_DIR = Path(__file__).resolve().parents[3]

LoadConfigsFn = Callable[[Path], list[BaseSystemConfig]]
CreateCalculatorFn = Callable[[BaseSystemConfig], Any]
FetchResultsFn = Callable[[Session, int | None], list[Any]]


@dataclass(frozen=True)
class RatingSystemDescriptor:
    """Everything required to rebuild one rating system variant."""

    algorithm: str
    granularity: Granularity
    subject: Subject
    config_dir: Path
    load_configs: LoadConfigsFn
    create_calculator: CreateCalculatorFn
    fetch_results: FetchResultsFn
    repository: BaseRatingRepository[Any, Any, Any]
    ensure_schema: Callable[[Engine], None]
    process_method: str


_REGISTRY: dict[tuple[str, Granularity, Subject], RatingSystemDescriptor] = {}


def register(descriptor: RatingSystemDescriptor) -> None:
    """Register one rating-system descriptor."""
    key = (descriptor.algorithm.lower(), descriptor.granularity, descriptor.subject)
    if key in _REGISTRY:
        raise ValueError(f"Duplicate rating descriptor registration for key={key}")
    _REGISTRY[key] = descriptor


def get_all() -> list[RatingSystemDescriptor]:
    """Return all registered descriptors in deterministic order."""
    return [
        _REGISTRY[key]
        for key in sorted(
            _REGISTRY.keys(),
            key=lambda item: (item[0], item[1].value, item[2].value),
        )
    ]


def get(algorithm: str, granularity: Granularity, subject: Subject) -> RatingSystemDescriptor:
    """Get one registered descriptor by three-axis key."""
    key = (algorithm.lower(), granularity, subject)
    try:
        return _REGISTRY[key]
    except KeyError as exc:
        available = ", ".join(
            f"{algo}/{gran.value}/{subj.value}"
            for algo, gran, subj in sorted(
                _REGISTRY.keys(),
                key=lambda item: (item[0], item[1].value, item[2].value),
            )
        )
        raise KeyError(
            f"No rating descriptor registered for {algorithm}/{granularity.value}/{subject.value}. "
            f"Available: {available}"
        ) from exc


def _make_creator(
    calculator_class: Type[Any],
    needs_lookback: bool = False,
) -> CreateCalculatorFn:
    def creator(config: BaseSystemConfig) -> Any:
        kwargs: dict[str, Any] = {"params": config.parameters}
        if needs_lookback:
            kwargs["lookback_days"] = (
                None if config.lookback_days == 0 else config.lookback_days
            )
            kwargs["as_of_time"] = datetime.now(UTC).replace(tzinfo=None)
        return calculator_class(**kwargs)

    return creator


def _fetch_map(session: Session, lookback_days: int | None) -> list[Any]:
    return fetch_map_results(session, lookback_days=lookback_days)


def _fetch_match(session: Session, lookback_days: int | None) -> list[Any]:
    return fetch_match_results(session, lookback_days=lookback_days)


def _fetch_player_map(session: Session, lookback_days: int | None) -> list[Any]:
    return fetch_player_map_results(session, lookback_days=lookback_days)


def _fetch_player_match(session: Session, lookback_days: int | None) -> list[Any]:
    return fetch_player_match_results(session, lookback_days=lookback_days)


# (algorithm, granularity, subject, config_subdir, load_configs, calculator_class, needs_lookback, repo, process_method, fetch_fn)
_SYSTEMS: list[tuple[str, Granularity, Subject, str, LoadConfigsFn, Type[Any], bool, BaseRatingRepository[Any, Any, Any], str, FetchResultsFn]] = [
    ("elo", Granularity.MAP, Subject.TEAM, "elo", load_elo_system_configs, TeamEloCalculator, True, TEAM_ELO_REPOSITORY, "process_map", _fetch_map),
    ("elo", Granularity.MATCH, Subject.TEAM, "elo_match", load_elo_system_configs, TeamMatchEloCalculator, True, TEAM_MATCH_ELO_REPOSITORY, "process_match", _fetch_match),
    ("elo", Granularity.MAP_SPECIFIC, Subject.TEAM, "elo_map", load_map_specific_elo_system_configs, TeamMapSpecificEloCalculator, True, TEAM_MAP_ELO_REPOSITORY, "process_map", _fetch_map),
    ("elo", Granularity.MAP, Subject.PLAYER, "elo_player", load_elo_system_configs, PlayerEloCalculator, True, PLAYER_ELO_REPOSITORY, "process_map", _fetch_player_map),
    ("elo", Granularity.MATCH, Subject.PLAYER, "elo_player_match", load_elo_system_configs, PlayerMatchEloCalculator, True, PLAYER_MATCH_ELO_REPOSITORY, "process_match", _fetch_player_match),
    ("elo", Granularity.MAP_SPECIFIC, Subject.PLAYER, "elo_player_map", load_map_specific_elo_system_configs, PlayerMapSpecificEloCalculator, True, PLAYER_MAP_ELO_REPOSITORY, "process_map", _fetch_player_map),
    ("glicko2", Granularity.MAP, Subject.TEAM, "glicko2", load_glicko2_system_configs, TeamGlicko2Calculator, False, TEAM_GLICKO2_REPOSITORY, "process_map", _fetch_map),
    ("glicko2", Granularity.MATCH, Subject.TEAM, "glicko2_match", load_glicko2_system_configs, TeamMatchGlicko2Calculator, False, TEAM_MATCH_GLICKO2_REPOSITORY, "process_match", _fetch_match),
    ("glicko2", Granularity.MAP_SPECIFIC, Subject.TEAM, "glicko2_map", load_map_specific_glicko2_system_configs, TeamMapSpecificGlicko2Calculator, False, TEAM_MAP_GLICKO2_REPOSITORY, "process_map", _fetch_map),
    ("glicko2", Granularity.MAP, Subject.PLAYER, "glicko2_player", load_glicko2_system_configs, PlayerGlicko2Calculator, False, PLAYER_GLICKO2_REPOSITORY, "process_map", _fetch_player_map),
    ("glicko2", Granularity.MATCH, Subject.PLAYER, "glicko2_player_match", load_glicko2_system_configs, PlayerMatchGlicko2Calculator, False, PLAYER_MATCH_GLICKO2_REPOSITORY, "process_match", _fetch_player_match),
    ("glicko2", Granularity.MAP_SPECIFIC, Subject.PLAYER, "glicko2_player_map", load_map_specific_glicko2_system_configs, PlayerMapSpecificGlicko2Calculator, False, PLAYER_MAP_GLICKO2_REPOSITORY, "process_map", _fetch_player_map),
    ("openskill", Granularity.MAP, Subject.TEAM, "openskill", load_openskill_system_configs, TeamOpenSkillCalculator, False, TEAM_OPENSKILL_REPOSITORY, "process_map", _fetch_map),
    ("openskill", Granularity.MATCH, Subject.TEAM, "openskill_match", load_openskill_system_configs, TeamMatchOpenSkillCalculator, False, TEAM_MATCH_OPENSKILL_REPOSITORY, "process_match", _fetch_match),
    ("openskill", Granularity.MAP_SPECIFIC, Subject.TEAM, "openskill_map", load_map_specific_openskill_system_configs, TeamMapSpecificOpenSkillCalculator, False, TEAM_MAP_OPENSKILL_REPOSITORY, "process_map", _fetch_map),
    ("openskill", Granularity.MAP, Subject.PLAYER, "openskill_player", load_openskill_system_configs, PlayerOpenSkillCalculator, False, PLAYER_OPENSKILL_REPOSITORY, "process_map", _fetch_player_map),
    ("openskill", Granularity.MATCH, Subject.PLAYER, "openskill_player_match", load_openskill_system_configs, PlayerMatchOpenSkillCalculator, False, PLAYER_MATCH_OPENSKILL_REPOSITORY, "process_match", _fetch_player_match),
    ("openskill", Granularity.MAP_SPECIFIC, Subject.PLAYER, "openskill_player_map", load_map_specific_openskill_system_configs, PlayerMapSpecificOpenSkillCalculator, False, PLAYER_MAP_OPENSKILL_REPOSITORY, "process_map", _fetch_player_map),
]


def _register_defaults() -> None:
    if _REGISTRY:
        return
    for (
        algorithm,
        granularity,
        subject,
        config_subdir,
        load_configs,
        calculator_class,
        needs_lookback,
        repository,
        process_method,
        fetch_results,
    ) in _SYSTEMS:
        register(
            RatingSystemDescriptor(
                algorithm=algorithm,
                granularity=granularity,
                subject=subject,
                config_dir=ROOT_DIR / "configs" / "ratings" / config_subdir,
                load_configs=load_configs,
                create_calculator=_make_creator(calculator_class, needs_lookback=needs_lookback),
                fetch_results=fetch_results,
                repository=repository,
                ensure_schema=repository.ensure_schema,
                process_method=process_method,
            )
        )


_register_defaults()

__all__ = [
    "RatingSystemDescriptor",
    "get",
    "get_all",
    "register",
]
