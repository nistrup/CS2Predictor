"""Tests for TOML-based map-specific Glicko-2 system config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.ratings.glicko2.map_specific_config import load_map_specific_glicko2_system_configs


def test_load_map_specific_glicko2_system_configs_from_directory(tmp_path: Path) -> None:
    config_path = tmp_path / "default.toml"
    config_path.write_text(
        """
[system]
name = "map_glicko2_a"
description = "A test map-specific Glicko-2 system"
lookback_days = 180

[glicko2]
initial_rating = 1520.0
initial_rd = 320.0
initial_volatility = 0.05
tau = 0.6
rating_period_days = 2.0
min_rd = 40.0
max_rd = 350.0
epsilon = 0.000001

[map_specific]
map_prior_games = 30.0
""".strip()
    )

    configs = load_map_specific_glicko2_system_configs(tmp_path)
    assert len(configs) == 1

    system = configs[0]
    assert system.name == "map_glicko2_a"
    assert system.description == "A test map-specific Glicko-2 system"
    assert system.lookback_days == 180
    assert system.parameters.tau == pytest.approx(0.6)
    assert system.parameters.map_prior_games == pytest.approx(30.0)


def test_map_specific_defaults_apply_when_section_omitted(tmp_path: Path) -> None:
    config_path = tmp_path / "default.toml"
    config_path.write_text(
        """
[system]
name = "map_glicko2_defaulted"
lookback_days = 365

[glicko2]
""".strip()
    )

    configs = load_map_specific_glicko2_system_configs(tmp_path)
    assert len(configs) == 1
    assert configs[0].parameters.map_prior_games == pytest.approx(20.0)


def test_invalid_map_prior_games_raises_validation_error(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid.toml"
    config_path.write_text(
        """
[system]
name = "map_glicko2_invalid"
lookback_days = 365

[glicko2]

[map_specific]
map_prior_games = 0.0
""".strip()
    )

    with pytest.raises(ValueError, match=r"map_prior_games must be > 0"):
        load_map_specific_glicko2_system_configs(tmp_path)
