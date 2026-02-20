"""Tests for TOML-based OpenSkill system config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from domain.openskill.config import load_openskill_system_configs


def test_load_openskill_system_configs_from_directory(tmp_path: Path) -> None:
    config_path = tmp_path / "default.toml"
    config_path.write_text(
        """
[system]
name = "openskill_a"
description = "A test OpenSkill system"
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
""".strip()
    )

    configs = load_openskill_system_configs(tmp_path)
    assert len(configs) == 1

    system = configs[0]
    assert system.name == "openskill_a"
    assert system.description == "A test OpenSkill system"
    assert system.lookback_days == 180
    assert system.parameters.initial_mu == pytest.approx(30.0)
    assert system.parameters.initial_sigma == pytest.approx(7.5)
    assert system.parameters.beta == pytest.approx(4.0)
    assert system.parameters.kappa == pytest.approx(0.0002)
    assert system.parameters.tau == pytest.approx(0.07)
    assert system.parameters.limit_sigma is True
    assert system.parameters.balance is False
    assert system.parameters.ordinal_z == pytest.approx(2.5)


def test_duplicate_names_raise_error(tmp_path: Path) -> None:
    template = """
[system]
name = "dup"
lookback_days = 365

[openskill]
""".strip()
    (tmp_path / "a.toml").write_text(template)
    (tmp_path / "b.toml").write_text(template)

    with pytest.raises(ValueError, match="Duplicate openskill system names"):
        load_openskill_system_configs(tmp_path)


def test_all_openskill_parameter_defaults_when_omitted(tmp_path: Path) -> None:
    config_path = tmp_path / "defaulted.toml"
    config_path.write_text(
        """
[system]
name = "openskill_defaulted"
lookback_days = 365

[openskill]
""".strip()
    )

    configs = load_openskill_system_configs(tmp_path)
    system = configs[0]
    assert system.parameters.initial_mu == pytest.approx(25.0)
    assert system.parameters.initial_sigma == pytest.approx(25.0 / 3.0)
    assert system.parameters.beta == pytest.approx(25.0 / 6.0)
    assert system.parameters.kappa == pytest.approx(0.0001)
    assert system.parameters.tau == pytest.approx(25.0 / 300.0)
    assert system.parameters.limit_sigma is False
    assert system.parameters.balance is False
    assert system.parameters.ordinal_z == pytest.approx(3.0)


def test_boolean_strings_are_parsed() -> None:
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as dir_path:
        config_path = Path(dir_path) / "s.toml"
        config_path.write_text(
            """
[system]
name = "openskill_bool_parse"
lookback_days = 365

[openskill]
limit_sigma = "true"
balance = "no"
""".strip()
        )
        system = load_openskill_system_configs(Path(dir_path))[0]
        assert system.parameters.limit_sigma is True
        assert system.parameters.balance is False


def test_invalid_boolean_raises_validation_error(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid_bool.toml"
    config_path.write_text(
        """
[system]
name = "openskill_invalid_bool"
lookback_days = 365

[openskill]
limit_sigma = "maybe"
""".strip()
    )

    with pytest.raises(ValueError, match=r"limit_sigma must be a boolean"):
        load_openskill_system_configs(tmp_path)


def test_invalid_tau_raises_validation_error(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid_tau.toml"
    config_path.write_text(
        """
[system]
name = "openskill_invalid_tau"
lookback_days = 365

[openskill]
tau = 0.0
""".strip()
    )

    with pytest.raises(ValueError, match=r"tau must be > 0"):
        load_openskill_system_configs(tmp_path)
