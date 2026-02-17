"""Tests for TOML-based map-specific Elo system config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.ratings.elo.map_specific_config import load_map_specific_elo_system_configs


def test_load_map_specific_elo_system_configs_from_directory(tmp_path: Path) -> None:
    config_path = tmp_path / "default.toml"
    config_path.write_text(
        """
[system]
name = "map_elo_a"
description = "A test map-specific Elo system"
lookback_days = 180

[elo]
initial_elo = 1550.0
k_factor = 24.0
scale_factor = 420.0
even_multiplier = 1.05
favored_multiplier = 0.95
unfavored_multiplier = 1.2
opponent_strength_weight = 1.15
lan_multiplier = 1.15
round_domination_multiplier = 1.1
kd_ratio_domination_multiplier = 1.2
recency_min_multiplier = 0.3
inactivity_half_life_days = 45.0
bo1_match_multiplier = 0.95
bo3_match_multiplier = 1.1
bo5_match_multiplier = 1.2

[map_specific]
map_prior_games = 30.0
""".strip()
    )

    configs = load_map_specific_elo_system_configs(tmp_path)
    assert len(configs) == 1

    system = configs[0]
    assert system.name == "map_elo_a"
    assert system.description == "A test map-specific Elo system"
    assert system.lookback_days == 180
    assert system.parameters.k_factor == pytest.approx(24.0)
    assert system.parameters.map_prior_games == pytest.approx(30.0)


def test_map_specific_defaults_apply_when_section_omitted(tmp_path: Path) -> None:
    config_path = tmp_path / "default.toml"
    config_path.write_text(
        """
[system]
name = "map_elo_defaulted"
lookback_days = 365

[elo]
""".strip()
    )

    configs = load_map_specific_elo_system_configs(tmp_path)
    assert len(configs) == 1
    assert configs[0].parameters.map_prior_games == pytest.approx(20.0)


def test_invalid_map_prior_games_raises_validation_error(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid.toml"
    config_path.write_text(
        """
[system]
name = "map_elo_invalid"
lookback_days = 365

[elo]

[map_specific]
map_prior_games = 0.0
""".strip()
    )

    with pytest.raises(ValueError, match=r"map_prior_games must be > 0"):
        load_map_specific_elo_system_configs(tmp_path)
