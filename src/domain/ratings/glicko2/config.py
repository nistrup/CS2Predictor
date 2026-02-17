"""Load Glicko-2 system definitions from TOML files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib

from domain.ratings.glicko2.calculator import Glicko2Parameters


@dataclass(frozen=True)
class Glicko2SystemConfig:
    """Configuration for one Glicko-2 system rebuild."""

    file_path: Path
    name: str
    description: str | None
    lookback_days: int
    parameters: Glicko2Parameters

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
        }


def load_glicko2_system_configs(config_dir: Path) -> list[Glicko2SystemConfig]:
    """Load and validate all Glicko-2 TOML config files in a directory."""
    if not config_dir.exists():
        raise FileNotFoundError(f"Config directory not found: {config_dir}")
    if not config_dir.is_dir():
        raise NotADirectoryError(f"Config path is not a directory: {config_dir}")

    config_files = sorted(config_dir.glob("*.toml"))
    if not config_files:
        raise ValueError(f"No .toml config files found in: {config_dir}")

    systems: list[Glicko2SystemConfig] = []
    for file_path in config_files:
        systems.append(_load_single_config(file_path))

    names = [system.name for system in systems]
    if len(names) != len(set(names)):
        raise ValueError(f"Duplicate glicko2 system names found in {config_dir}: {names}")

    return systems


def _load_single_config(file_path: Path) -> Glicko2SystemConfig:
    with file_path.open("rb") as file:
        raw = tomllib.load(file)

    system_raw = raw.get("system", {})
    glicko2_raw = raw.get("glicko2", {})

    name = str(system_raw.get("name", "")).strip()
    if not name:
        raise ValueError(f"{file_path}: [system].name is required")

    description_value = system_raw.get("description")
    description = None if description_value is None else str(description_value)

    lookback_days = int(system_raw.get("lookback_days", 365))
    if lookback_days < 0:
        raise ValueError(f"{file_path}: [system].lookback_days must be >= 0")

    parameters = Glicko2Parameters(
        initial_rating=float(glicko2_raw.get("initial_rating", 1500.0)),
        initial_rd=float(glicko2_raw.get("initial_rd", 350.0)),
        initial_volatility=float(glicko2_raw.get("initial_volatility", 0.06)),
        tau=float(glicko2_raw.get("tau", 0.5)),
        rating_period_days=float(glicko2_raw.get("rating_period_days", 1.0)),
        min_rd=float(glicko2_raw.get("min_rd", 30.0)),
        max_rd=float(glicko2_raw.get("max_rd", 350.0)),
        epsilon=float(glicko2_raw.get("epsilon", 1e-6)),
    )
    _validate_parameters(file_path=file_path, parameters=parameters)

    return Glicko2SystemConfig(
        file_path=file_path,
        name=name,
        description=description,
        lookback_days=lookback_days,
        parameters=parameters,
    )


def _validate_parameters(*, file_path: Path, parameters: Glicko2Parameters) -> None:
    if parameters.initial_rating <= 0.0:
        raise ValueError(f"{file_path}: [glicko2].initial_rating must be > 0")
    if parameters.initial_rd <= 0.0:
        raise ValueError(f"{file_path}: [glicko2].initial_rd must be > 0")
    if parameters.initial_volatility <= 0.0:
        raise ValueError(f"{file_path}: [glicko2].initial_volatility must be > 0")
    if parameters.tau <= 0.0:
        raise ValueError(f"{file_path}: [glicko2].tau must be > 0")
    if parameters.rating_period_days <= 0.0:
        raise ValueError(f"{file_path}: [glicko2].rating_period_days must be > 0")
    if parameters.min_rd <= 0.0:
        raise ValueError(f"{file_path}: [glicko2].min_rd must be > 0")
    if parameters.max_rd <= 0.0:
        raise ValueError(f"{file_path}: [glicko2].max_rd must be > 0")
    if parameters.min_rd > parameters.max_rd:
        raise ValueError(f"{file_path}: [glicko2].min_rd must be <= max_rd")
    if parameters.initial_rd < parameters.min_rd or parameters.initial_rd > parameters.max_rd:
        raise ValueError(f"{file_path}: [glicko2].initial_rd must be between min_rd and max_rd")
    if parameters.epsilon <= 0.0:
        raise ValueError(f"{file_path}: [glicko2].epsilon must be > 0")
