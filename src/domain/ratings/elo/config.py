"""Load Elo system definitions from TOML files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from domain.ratings.config_base import BaseSystemConfig, load_system_configs
from domain.ratings.elo.calculator import EloParameters


@dataclass(frozen=True)
class EloSystemConfig(BaseSystemConfig):
    """Configuration for one Elo system rebuild."""

    parameters: EloParameters

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
        }


def load_elo_system_configs(config_dir: Path) -> list[EloSystemConfig]:
    """Load and validate all Elo system TOML config files in a directory."""
    return load_system_configs(
        config_dir,
        _parse_elo_system_config,
        duplicate_name_label="elo",
    )


def _parse_elo_system_config(raw: dict[str, Any], file_path: Path) -> EloSystemConfig:
    system_raw = raw.get("system", {})
    elo_raw = raw.get("elo", {})

    name = str(system_raw.get("name", "")).strip()
    if not name:
        raise ValueError(f"{file_path}: [system].name is required")

    description_value = system_raw.get("description")
    description = None if description_value is None else str(description_value)

    lookback_days = int(system_raw.get("lookback_days", 365))
    if lookback_days < 0:
        raise ValueError(f"{file_path}: [system].lookback_days must be >= 0")

    parameters = EloParameters(
        initial_elo=float(elo_raw.get("initial_elo", 1500.0)),
        k_factor=float(elo_raw.get("k_factor", 20.0)),
        scale_factor=float(elo_raw.get("scale_factor", 400.0)),
        even_multiplier=float(elo_raw.get("even_multiplier", 1.0)),
        favored_multiplier=float(elo_raw.get("favored_multiplier", 1.0)),
        unfavored_multiplier=float(elo_raw.get("unfavored_multiplier", 1.0)),
        opponent_strength_weight=float(elo_raw.get("opponent_strength_weight", 1.0)),
        lan_multiplier=float(elo_raw.get("lan_multiplier", 1.0)),
        round_domination_multiplier=float(
            elo_raw.get("round_domination_multiplier", elo_raw.get("domination_multiplier", 1.0))
        ),
        kd_ratio_domination_multiplier=float(elo_raw.get("kd_ratio_domination_multiplier", 1.0)),
        recency_min_multiplier=float(elo_raw.get("recency_min_multiplier", 1.0)),
        inactivity_half_life_days=float(elo_raw.get("inactivity_half_life_days", 0.0)),
        bo1_match_multiplier=float(elo_raw.get("bo1_match_multiplier", 1.0)),
        bo3_match_multiplier=float(elo_raw.get("bo3_match_multiplier", 1.0)),
        bo5_match_multiplier=float(elo_raw.get("bo5_match_multiplier", 1.0)),
    )
    _validate_parameters(file_path=file_path, parameters=parameters)

    return EloSystemConfig(
        name=name,
        description=description,
        file_path=file_path,
        lookback_days=lookback_days,
        parameters=parameters,
    )


def _validate_parameters(*, file_path: Path, parameters: EloParameters) -> None:
    if parameters.initial_elo <= 0.0:
        raise ValueError(f"{file_path}: [elo].initial_elo must be > 0")
    if parameters.k_factor <= 0.0:
        raise ValueError(f"{file_path}: [elo].k_factor must be > 0")
    if parameters.scale_factor <= 0.0:
        raise ValueError(f"{file_path}: [elo].scale_factor must be > 0")
    if parameters.even_multiplier <= 0.0:
        raise ValueError(f"{file_path}: [elo].even_multiplier must be > 0")
    if parameters.favored_multiplier <= 0.0:
        raise ValueError(f"{file_path}: [elo].favored_multiplier must be > 0")
    if parameters.unfavored_multiplier <= 0.0:
        raise ValueError(f"{file_path}: [elo].unfavored_multiplier must be > 0")
    if parameters.opponent_strength_weight <= 0.0:
        raise ValueError(f"{file_path}: [elo].opponent_strength_weight must be > 0")
    if parameters.lan_multiplier <= 0.0:
        raise ValueError(f"{file_path}: [elo].lan_multiplier must be > 0")
    if parameters.round_domination_multiplier <= 0.0:
        raise ValueError(f"{file_path}: [elo].round_domination_multiplier must be > 0")
    if parameters.kd_ratio_domination_multiplier <= 0.0:
        raise ValueError(f"{file_path}: [elo].kd_ratio_domination_multiplier must be > 0")
    if parameters.recency_min_multiplier < 0.0 or parameters.recency_min_multiplier > 1.0:
        raise ValueError(f"{file_path}: [elo].recency_min_multiplier must be between 0 and 1")
    if parameters.inactivity_half_life_days < 0.0:
        raise ValueError(f"{file_path}: [elo].inactivity_half_life_days must be >= 0")
    if parameters.bo1_match_multiplier <= 0.0:
        raise ValueError(f"{file_path}: [elo].bo1_match_multiplier must be > 0")
    if parameters.bo3_match_multiplier <= 0.0:
        raise ValueError(f"{file_path}: [elo].bo3_match_multiplier must be > 0")
    if parameters.bo5_match_multiplier <= 0.0:
        raise ValueError(f"{file_path}: [elo].bo5_match_multiplier must be > 0")
