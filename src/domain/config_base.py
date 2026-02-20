"""Shared config-loading utilities for rating systems."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar
import tomllib


@dataclass(frozen=True)
class BaseSystemConfig:
    """Minimal metadata shared across all rating-system configs."""

    name: str
    description: str | None
    file_path: Path
    lookback_days: int

    def as_config_json(self) -> dict[str, Any]:
        raise NotImplementedError


T = TypeVar("T", bound=BaseSystemConfig)


def load_system_configs(
    config_dir: Path,
    parser: Callable[[dict[str, Any], Path], T],
    *,
    duplicate_name_label: str = "rating",
) -> list[T]:
    """Load all TOML files in a directory with duplicate-name validation."""
    if not config_dir.exists():
        raise FileNotFoundError(f"Config directory not found: {config_dir}")
    if not config_dir.is_dir():
        raise NotADirectoryError(f"Config path is not a directory: {config_dir}")

    config_files = sorted(config_dir.glob("*.toml"))
    if not config_files:
        raise ValueError(f"No .toml config files found in: {config_dir}")

    systems: list[T] = []
    for file_path in config_files:
        with file_path.open("rb") as file:
            raw = tomllib.load(file)
        systems.append(parser(raw, file_path))

    names = [system.name for system in systems]
    if len(names) != len(set(names)):
        raise ValueError(
            f"Duplicate {duplicate_name_label} system names found in {config_dir}: {names}"
        )

    return systems


__all__ = ["BaseSystemConfig", "load_system_configs"]
