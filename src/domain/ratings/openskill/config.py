"""Load OpenSkill system definitions from TOML files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from domain.ratings.config_base import BaseSystemConfig, load_system_configs
from domain.ratings.openskill.calculator import OpenSkillParameters


@dataclass(frozen=True)
class OpenSkillSystemConfig(BaseSystemConfig):
    """Configuration for one OpenSkill system rebuild."""

    parameters: OpenSkillParameters

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
        }


def load_openskill_system_configs(config_dir: Path) -> list[OpenSkillSystemConfig]:
    """Load and validate all OpenSkill TOML config files in a directory."""
    return load_system_configs(
        config_dir,
        _parse_openskill_system_config,
        duplicate_name_label="openskill",
    )


def _parse_bool(value: Any, *, file_path: Path, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("true", "1", "yes", "on"):
            return True
        if normalized in ("false", "0", "no", "off"):
            return False
    raise ValueError(f"{file_path}: [openskill].{key} must be a boolean")


def _parse_openskill_system_config(raw: dict[str, Any], file_path: Path) -> OpenSkillSystemConfig:
    system_raw = raw.get("system", {})
    openskill_raw = raw.get("openskill", {})

    name = str(system_raw.get("name", "")).strip()
    if not name:
        raise ValueError(f"{file_path}: [system].name is required")

    description_value = system_raw.get("description")
    description = None if description_value is None else str(description_value)

    lookback_days = int(system_raw.get("lookback_days", 365))
    if lookback_days < 0:
        raise ValueError(f"{file_path}: [system].lookback_days must be >= 0")

    limit_sigma_raw = openskill_raw.get("limit_sigma", False)
    balance_raw = openskill_raw.get("balance", False)

    parameters = OpenSkillParameters(
        initial_mu=float(openskill_raw.get("initial_mu", 25.0)),
        initial_sigma=float(openskill_raw.get("initial_sigma", 25.0 / 3.0)),
        beta=float(openskill_raw.get("beta", 25.0 / 6.0)),
        kappa=float(openskill_raw.get("kappa", 0.0001)),
        tau=float(openskill_raw.get("tau", 25.0 / 300.0)),
        limit_sigma=_parse_bool(limit_sigma_raw, file_path=file_path, key="limit_sigma"),
        balance=_parse_bool(balance_raw, file_path=file_path, key="balance"),
        ordinal_z=float(openskill_raw.get("ordinal_z", 3.0)),
    )
    _validate_parameters(file_path=file_path, parameters=parameters)

    return OpenSkillSystemConfig(
        name=name,
        description=description,
        file_path=file_path,
        lookback_days=lookback_days,
        parameters=parameters,
    )


def _validate_parameters(*, file_path: Path, parameters: OpenSkillParameters) -> None:
    if parameters.initial_mu <= 0.0:
        raise ValueError(f"{file_path}: [openskill].initial_mu must be > 0")
    if parameters.initial_sigma <= 0.0:
        raise ValueError(f"{file_path}: [openskill].initial_sigma must be > 0")
    if parameters.beta <= 0.0:
        raise ValueError(f"{file_path}: [openskill].beta must be > 0")
    if parameters.kappa <= 0.0:
        raise ValueError(f"{file_path}: [openskill].kappa must be > 0")
    if parameters.tau <= 0.0:
        raise ValueError(f"{file_path}: [openskill].tau must be > 0")
    if parameters.ordinal_z <= 0.0:
        raise ValueError(f"{file_path}: [openskill].ordinal_z must be > 0")
