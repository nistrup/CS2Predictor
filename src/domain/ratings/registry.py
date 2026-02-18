"""Registry of available rating system implementations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from domain.ratings.config_base import BaseSystemConfig
from domain.ratings.elo.calculator import TeamEloCalculator
from domain.ratings.elo.config import load_elo_system_configs
from domain.ratings.glicko2.calculator import TeamGlicko2Calculator
from domain.ratings.glicko2.config import load_glicko2_system_configs
from domain.ratings.openskill.calculator import TeamOpenSkillCalculator
from domain.ratings.openskill.config import load_openskill_system_configs
from domain.ratings.protocol import Granularity, Subject
from repositories.ratings.base import BaseRatingRepository
from repositories.ratings.common import fetch_map_results
from repositories.ratings.elo.repository import TEAM_ELO_REPOSITORY, ensure_team_elo_schema
from repositories.ratings.glicko2.repository import TEAM_GLICKO2_REPOSITORY, ensure_team_glicko2_schema
from repositories.ratings.openskill.repository import TEAM_OPENSKILL_REPOSITORY, ensure_team_openskill_schema

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


def _create_team_elo_calculator(system_config: BaseSystemConfig) -> TeamEloCalculator:
    lookback_days = None if system_config.lookback_days == 0 else system_config.lookback_days
    return TeamEloCalculator(
        params=system_config.parameters,
        lookback_days=lookback_days,
        as_of_time=datetime.now(UTC).replace(tzinfo=None),
    )


def _create_team_glicko2_calculator(system_config: BaseSystemConfig) -> TeamGlicko2Calculator:
    return TeamGlicko2Calculator(params=system_config.parameters)


def _create_team_openskill_calculator(system_config: BaseSystemConfig) -> TeamOpenSkillCalculator:
    return TeamOpenSkillCalculator(params=system_config.parameters)


def _fetch_map_results(session: Session, lookback_days: int | None) -> list[Any]:
    return fetch_map_results(session, lookback_days=lookback_days)


def _register_defaults() -> None:
    if _REGISTRY:
        return

    register(
        RatingSystemDescriptor(
            algorithm="elo",
            granularity=Granularity.MAP,
            subject=Subject.TEAM,
            config_dir=ROOT_DIR / "configs" / "ratings" / "elo",
            load_configs=load_elo_system_configs,
            create_calculator=_create_team_elo_calculator,
            fetch_results=_fetch_map_results,
            repository=TEAM_ELO_REPOSITORY,
            ensure_schema=ensure_team_elo_schema,
            process_method="process_map",
        )
    )
    register(
        RatingSystemDescriptor(
            algorithm="glicko2",
            granularity=Granularity.MAP,
            subject=Subject.TEAM,
            config_dir=ROOT_DIR / "configs" / "ratings" / "glicko2",
            load_configs=load_glicko2_system_configs,
            create_calculator=_create_team_glicko2_calculator,
            fetch_results=_fetch_map_results,
            repository=TEAM_GLICKO2_REPOSITORY,
            ensure_schema=ensure_team_glicko2_schema,
            process_method="process_map",
        )
    )
    register(
        RatingSystemDescriptor(
            algorithm="openskill",
            granularity=Granularity.MAP,
            subject=Subject.TEAM,
            config_dir=ROOT_DIR / "configs" / "ratings" / "openskill",
            load_configs=load_openskill_system_configs,
            create_calculator=_create_team_openskill_calculator,
            fetch_results=_fetch_map_results,
            repository=TEAM_OPENSKILL_REPOSITORY,
            ensure_schema=ensure_team_openskill_schema,
            process_method="process_map",
        )
    )


_register_defaults()

__all__ = [
    "RatingSystemDescriptor",
    "get",
    "get_all",
    "register",
]
