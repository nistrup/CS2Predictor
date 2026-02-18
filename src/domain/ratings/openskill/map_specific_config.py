"""Load map-specific OpenSkill system definitions from TOML files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib

from domain.ratings.config_base import BaseSystemConfig
from domain.ratings.openskill.config import load_openskill_system_configs
from domain.ratings.openskill.map_specific_calculator import MapSpecificOpenSkillParameters


@dataclass(frozen=True)
class MapSpecificOpenSkillSystemConfig(BaseSystemConfig):
    """Configuration for one map-specific OpenSkill system rebuild."""

    parameters: MapSpecificOpenSkillParameters

    def as_config_json(self) -> dict[str, Any]:
        return {
            "initial_mu": self.parameters.initial_mu,
            "initial_sigma": self.parameters.initial_sigma,
            "beta": self.parameters.beta,
            "kappa": self.parameters.kappa,
            "tau": self.parameters.tau,
            "limit_sigma": self.parameters.limit_sigma,
            "balance": self.parameters.balance,
            "ordinal_z": self.parameters.ordinal_z,
            "lookback_days": self.lookback_days,
            "map_prior_games": self.parameters.map_prior_games,
        }


def load_map_specific_openskill_system_configs(config_dir: Path) -> list[MapSpecificOpenSkillSystemConfig]:
    """Load and validate all map-specific OpenSkill TOML config files in a directory."""
    base_configs = load_openskill_system_configs(config_dir)
    systems: list[MapSpecificOpenSkillSystemConfig] = []

    for base in base_configs:
        with base.file_path.open("rb") as file:
            raw = tomllib.load(file)

        map_specific_raw = raw.get("map_specific", {})
        map_prior_games = float(map_specific_raw.get("map_prior_games", 20.0))
        if map_prior_games <= 0.0:
            raise ValueError(f"{base.file_path}: [map_specific].map_prior_games must be > 0")

        params = base.parameters
        map_params = MapSpecificOpenSkillParameters(
            initial_mu=params.initial_mu,
            initial_sigma=params.initial_sigma,
            beta=params.beta,
            kappa=params.kappa,
            tau=params.tau,
            limit_sigma=params.limit_sigma,
            balance=params.balance,
            ordinal_z=params.ordinal_z,
            map_prior_games=map_prior_games,
        )
        systems.append(
            MapSpecificOpenSkillSystemConfig(
                name=base.name,
                description=base.description,
                file_path=base.file_path,
                lookback_days=base.lookback_days,
                parameters=map_params,
            )
        )

    return systems
