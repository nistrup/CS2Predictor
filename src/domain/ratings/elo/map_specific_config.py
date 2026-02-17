"""Load map-specific Elo system definitions from TOML files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib

from domain.ratings.config_base import BaseSystemConfig
from domain.ratings.elo.config import load_elo_system_configs
from domain.ratings.elo.map_specific_calculator import MapSpecificEloParameters


@dataclass(frozen=True)
class MapSpecificEloSystemConfig(BaseSystemConfig):
    """Configuration for one map-specific Elo system rebuild."""

    parameters: MapSpecificEloParameters

    def as_config_json(self) -> dict[str, Any]:
        return {
            "initial_elo": self.parameters.initial_elo,
            "k_factor": self.parameters.k_factor,
            "scale_factor": self.parameters.scale_factor,
            "lookback_days": self.lookback_days,
            "even_multiplier": self.parameters.even_multiplier,
            "favored_multiplier": self.parameters.favored_multiplier,
            "unfavored_multiplier": self.parameters.unfavored_multiplier,
            "opponent_strength_weight": self.parameters.opponent_strength_weight,
            "lan_multiplier": self.parameters.lan_multiplier,
            "round_domination_multiplier": self.parameters.round_domination_multiplier,
            "kd_ratio_domination_multiplier": self.parameters.kd_ratio_domination_multiplier,
            "recency_min_multiplier": self.parameters.recency_min_multiplier,
            "inactivity_half_life_days": self.parameters.inactivity_half_life_days,
            "bo1_match_multiplier": self.parameters.bo1_match_multiplier,
            "bo3_match_multiplier": self.parameters.bo3_match_multiplier,
            "bo5_match_multiplier": self.parameters.bo5_match_multiplier,
            "map_prior_games": self.parameters.map_prior_games,
        }


def load_map_specific_elo_system_configs(config_dir: Path) -> list[MapSpecificEloSystemConfig]:
    """Load and validate all map-specific Elo TOML config files in a directory."""
    base_configs = load_elo_system_configs(config_dir)
    systems: list[MapSpecificEloSystemConfig] = []
    for base in base_configs:
        with base.file_path.open("rb") as file:
            raw = tomllib.load(file)

        map_specific_raw = raw.get("map_specific", {})
        map_prior_games = float(map_specific_raw.get("map_prior_games", 20.0))
        if map_prior_games <= 0.0:
            raise ValueError(f"{base.file_path}: [map_specific].map_prior_games must be > 0")

        params = base.parameters
        map_params = MapSpecificEloParameters(
            initial_elo=params.initial_elo,
            k_factor=params.k_factor,
            scale_factor=params.scale_factor,
            even_multiplier=params.even_multiplier,
            favored_multiplier=params.favored_multiplier,
            unfavored_multiplier=params.unfavored_multiplier,
            opponent_strength_weight=params.opponent_strength_weight,
            lan_multiplier=params.lan_multiplier,
            round_domination_multiplier=params.round_domination_multiplier,
            kd_ratio_domination_multiplier=params.kd_ratio_domination_multiplier,
            recency_min_multiplier=params.recency_min_multiplier,
            inactivity_half_life_days=params.inactivity_half_life_days,
            bo1_match_multiplier=params.bo1_match_multiplier,
            bo3_match_multiplier=params.bo3_match_multiplier,
            bo5_match_multiplier=params.bo5_match_multiplier,
            map_prior_games=map_prior_games,
        )

        systems.append(
            MapSpecificEloSystemConfig(
                name=base.name,
                description=base.description,
                file_path=base.file_path,
                lookback_days=base.lookback_days,
                parameters=map_params,
            )
        )

    return systems
