"""Load map-specific Glicko-2 system definitions from TOML files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib

from domain.ratings.config_base import BaseSystemConfig
from domain.ratings.glicko2.config import load_glicko2_system_configs
from domain.ratings.glicko2.map_specific_calculator import MapSpecificGlicko2Parameters


@dataclass(frozen=True)
class MapSpecificGlicko2SystemConfig(BaseSystemConfig):
    """Configuration for one map-specific Glicko-2 system rebuild."""

    parameters: MapSpecificGlicko2Parameters

    def as_config_json(self) -> dict[str, Any]:
        return {
            "initial_rating": self.parameters.initial_rating,
            "initial_rd": self.parameters.initial_rd,
            "initial_volatility": self.parameters.initial_volatility,
            "tau": self.parameters.tau,
            "rating_period_days": self.parameters.rating_period_days,
            "min_rd": self.parameters.min_rd,
            "max_rd": self.parameters.max_rd,
            "epsilon": self.parameters.epsilon,
            "lookback_days": self.lookback_days,
            "map_prior_games": self.parameters.map_prior_games,
        }


def load_map_specific_glicko2_system_configs(config_dir: Path) -> list[MapSpecificGlicko2SystemConfig]:
    """Load and validate all map-specific Glicko-2 TOML config files in a directory."""
    base_configs = load_glicko2_system_configs(config_dir)
    systems: list[MapSpecificGlicko2SystemConfig] = []

    for base in base_configs:
        with base.file_path.open("rb") as file:
            raw = tomllib.load(file)

        map_specific_raw = raw.get("map_specific", {})
        map_prior_games = float(map_specific_raw.get("map_prior_games", 20.0))
        if map_prior_games <= 0.0:
            raise ValueError(f"{base.file_path}: [map_specific].map_prior_games must be > 0")

        params = base.parameters
        map_params = MapSpecificGlicko2Parameters(
            initial_rating=params.initial_rating,
            initial_rd=params.initial_rd,
            initial_volatility=params.initial_volatility,
            tau=params.tau,
            rating_period_days=params.rating_period_days,
            min_rd=params.min_rd,
            max_rd=params.max_rd,
            epsilon=params.epsilon,
            map_prior_games=map_prior_games,
        )
        systems.append(
            MapSpecificGlicko2SystemConfig(
                name=base.name,
                description=base.description,
                file_path=base.file_path,
                lookback_days=base.lookback_days,
                parameters=map_params,
            )
        )

    return systems
