"""Load match-level Elo system definitions from TOML files."""

from __future__ import annotations

from pathlib import Path

from domain.ratings.elo.config import EloSystemConfig, load_elo_system_configs

MatchEloSystemConfig = EloSystemConfig


def load_match_elo_system_configs(config_dir: Path) -> list[MatchEloSystemConfig]:
    """Load and validate match-level Elo TOML config files in a directory."""
    return load_elo_system_configs(config_dir)
