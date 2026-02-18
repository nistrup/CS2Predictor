"""Tests for TOML-based map-specific OpenSkill system config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.ratings.openskill.map_specific_config import load_map_specific_openskill_system_configs


def test_load_map_specific_openskill_system_configs_from_directory(tmp_path: Path) -> None:
    config_path = tmp_path / "default.toml"
    config_path.write_text(
        """
[system]
name = "map_openskill_a"
description = "A test map-specific OpenSkill system"
lookback_days = 180

[openskill]
initial_mu = 30.0
initial_sigma = 7.5
beta = 4.0
kappa = 0.0002
tau = 0.07
limit_sigma = true
balance = false
ordinal_z = 2.5

[map_specific]
map_prior_games = 30.0
""".strip()
    )

    configs = load_map_specific_openskill_system_configs(tmp_path)
    assert len(configs) == 1

    system = configs[0]
    assert system.name == "map_openskill_a"
    assert system.description == "A test map-specific OpenSkill system"
    assert system.lookback_days == 180
    assert system.parameters.tau == pytest.approx(0.07)
    assert system.parameters.map_prior_games == pytest.approx(30.0)


def test_map_specific_defaults_apply_when_section_omitted(tmp_path: Path) -> None:
    config_path = tmp_path / "default.toml"
    config_path.write_text(
        """
[system]
name = "map_openskill_defaulted"
lookback_days = 365

[openskill]
""".strip()
    )

    configs = load_map_specific_openskill_system_configs(tmp_path)
    assert len(configs) == 1
    assert configs[0].parameters.map_prior_games == pytest.approx(20.0)


def test_invalid_map_prior_games_raises_validation_error(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid.toml"
    config_path.write_text(
        """
[system]
name = "map_openskill_invalid"
lookback_days = 365

[openskill]

[map_specific]
map_prior_games = 0.0
""".strip()
    )

    with pytest.raises(ValueError, match=r"map_prior_games must be > 0"):
        load_map_specific_openskill_system_configs(tmp_path)
