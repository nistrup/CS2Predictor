"""Tests for TOML-based Glicko-2 system config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.glicko2.config import load_glicko2_system_configs


def test_load_glicko2_system_configs_from_directory(tmp_path: Path) -> None:
    config_path = tmp_path / "default.toml"
    config_path.write_text(
        """
[system]
name = "glicko2_a"
description = "A test Glicko-2 system"
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
""".strip()
    )

    configs = load_glicko2_system_configs(tmp_path)
    assert len(configs) == 1

    system = configs[0]
    assert system.name == "glicko2_a"
    assert system.description == "A test Glicko-2 system"
    assert system.lookback_days == 180
    assert system.parameters.initial_rating == pytest.approx(1520.0)
    assert system.parameters.initial_rd == pytest.approx(320.0)
    assert system.parameters.initial_volatility == pytest.approx(0.05)
    assert system.parameters.tau == pytest.approx(0.6)
    assert system.parameters.rating_period_days == pytest.approx(2.0)
    assert system.parameters.min_rd == pytest.approx(40.0)
    assert system.parameters.max_rd == pytest.approx(350.0)
    assert system.parameters.epsilon == pytest.approx(0.000001)


def test_duplicate_names_raise_error(tmp_path: Path) -> None:
    template = """
[system]
name = "dup"
lookback_days = 365

[glicko2]
""".strip()
    (tmp_path / "a.toml").write_text(template)
    (tmp_path / "b.toml").write_text(template)

    with pytest.raises(ValueError, match="Duplicate glicko2 system names"):
        load_glicko2_system_configs(tmp_path)


def test_all_glicko2_parameter_defaults_when_omitted(tmp_path: Path) -> None:
    config_path = tmp_path / "defaulted.toml"
    config_path.write_text(
        """
[system]
name = "glicko2_defaulted"
lookback_days = 365

[glicko2]
""".strip()
    )

    configs = load_glicko2_system_configs(tmp_path)
    system = configs[0]
    assert system.parameters.initial_rating == pytest.approx(1500.0)
    assert system.parameters.initial_rd == pytest.approx(350.0)
    assert system.parameters.initial_volatility == pytest.approx(0.06)
    assert system.parameters.tau == pytest.approx(0.5)
    assert system.parameters.rating_period_days == pytest.approx(1.0)
    assert system.parameters.min_rd == pytest.approx(30.0)
    assert system.parameters.max_rd == pytest.approx(350.0)
    assert system.parameters.epsilon == pytest.approx(1e-6)


def test_invalid_rating_period_days_raises_validation_error(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid.toml"
    config_path.write_text(
        """
[system]
name = "glicko2_invalid"
lookback_days = 365

[glicko2]
rating_period_days = 0.0
""".strip()
    )

    with pytest.raises(ValueError, match=r"rating_period_days must be > 0"):
        load_glicko2_system_configs(tmp_path)


def test_invalid_initial_rd_outside_bounds_raises_validation_error(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid_rd.toml"
    config_path.write_text(
        """
[system]
name = "glicko2_invalid_rd"
lookback_days = 365

[glicko2]
initial_rd = 400.0
min_rd = 30.0
max_rd = 350.0
""".strip()
    )

    with pytest.raises(ValueError, match=r"initial_rd must be between min_rd and max_rd"):
        load_glicko2_system_configs(tmp_path)
