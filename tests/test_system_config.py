"""Tests for TOML-based Elo system config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.ratings.elo.config import load_elo_system_configs


def test_load_elo_system_configs_from_directory(tmp_path: Path) -> None:
    config_path = tmp_path / "default.toml"
    config_path.write_text(
        """
[system]
name = "system_a"
description = "A test system"
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
""".strip()
    )

    configs = load_elo_system_configs(tmp_path)
    assert len(configs) == 1

    system = configs[0]
    assert system.name == "system_a"
    assert system.description == "A test system"
    assert system.lookback_days == 180
    assert system.parameters.initial_elo == pytest.approx(1550.0)
    assert system.parameters.k_factor == pytest.approx(24.0)
    assert system.parameters.scale_factor == pytest.approx(420.0)
    assert system.parameters.even_multiplier == pytest.approx(1.05)
    assert system.parameters.favored_multiplier == pytest.approx(0.95)
    assert system.parameters.unfavored_multiplier == pytest.approx(1.2)
    assert system.parameters.opponent_strength_weight == pytest.approx(1.15)
    assert system.parameters.lan_multiplier == pytest.approx(1.15)
    assert system.parameters.round_domination_multiplier == pytest.approx(1.1)
    assert system.parameters.kd_ratio_domination_multiplier == pytest.approx(1.2)
    assert system.parameters.recency_min_multiplier == pytest.approx(0.3)
    assert system.parameters.inactivity_half_life_days == pytest.approx(45.0)
    assert system.parameters.bo1_match_multiplier == pytest.approx(0.95)
    assert system.parameters.bo3_match_multiplier == pytest.approx(1.1)
    assert system.parameters.bo5_match_multiplier == pytest.approx(1.2)


def test_duplicate_names_raise_error(tmp_path: Path) -> None:
    template = """
[system]
name = "dup"
lookback_days = 365

[elo]
initial_elo = 1500.0
k_factor = 20.0
scale_factor = 400.0
even_multiplier = 1.0
favored_multiplier = 1.0
unfavored_multiplier = 1.0
opponent_strength_weight = 1.0
lan_multiplier = 1.0
round_domination_multiplier = 1.0
kd_ratio_domination_multiplier = 1.0
recency_min_multiplier = 1.0
inactivity_half_life_days = 0.0
bo1_match_multiplier = 1.0
bo3_match_multiplier = 1.1
bo5_match_multiplier = 1.2
""".strip()
    (tmp_path / "a.toml").write_text(template)
    (tmp_path / "b.toml").write_text(template)

    with pytest.raises(ValueError, match="Duplicate elo system names"):
        load_elo_system_configs(tmp_path)


def test_all_elo_parameter_defaults_when_omitted(tmp_path: Path) -> None:
    config_path = tmp_path / "defaulted.toml"
    config_path.write_text(
        """
[system]
name = "system_defaulted"
lookback_days = 365

[elo]
""".strip()
    )

    configs = load_elo_system_configs(tmp_path)
    system = configs[0]
    assert system.parameters.initial_elo == pytest.approx(1500.0)
    assert system.parameters.k_factor == pytest.approx(20.0)
    assert system.parameters.scale_factor == pytest.approx(400.0)
    assert system.parameters.even_multiplier == pytest.approx(1.0)
    assert system.parameters.favored_multiplier == pytest.approx(1.0)
    assert system.parameters.unfavored_multiplier == pytest.approx(1.0)
    assert system.parameters.opponent_strength_weight == pytest.approx(1.0)
    assert system.parameters.lan_multiplier == pytest.approx(1.0)
    assert system.parameters.round_domination_multiplier == pytest.approx(1.0)
    assert system.parameters.kd_ratio_domination_multiplier == pytest.approx(1.0)
    assert system.parameters.recency_min_multiplier == pytest.approx(1.0)
    assert system.parameters.inactivity_half_life_days == pytest.approx(0.0)
    assert system.parameters.bo1_match_multiplier == pytest.approx(1.0)
    assert system.parameters.bo3_match_multiplier == pytest.approx(1.0)
    assert system.parameters.bo5_match_multiplier == pytest.approx(1.0)


def test_invalid_opponent_strength_weight_raises_validation_error(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid.toml"
    config_path.write_text(
        """
[system]
name = "system_invalid"
lookback_days = 365

[elo]
opponent_strength_weight = 0.0
""".strip()
    )

    with pytest.raises(ValueError, match=r"opponent_strength_weight must be > 0"):
        load_elo_system_configs(tmp_path)


def test_invalid_inactivity_half_life_days_raises_validation_error(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid_inactivity.toml"
    config_path.write_text(
        """
[system]
name = "system_invalid_inactivity"
lookback_days = 365

[elo]
inactivity_half_life_days = -1.0
""".strip()
    )

    with pytest.raises(ValueError, match=r"inactivity_half_life_days must be >= 0"):
        load_elo_system_configs(tmp_path)
