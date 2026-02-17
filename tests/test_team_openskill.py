"""Unit tests for team OpenSkill calculations."""

from __future__ import annotations

from datetime import datetime

import pytest

from domain.ratings.common import TeamMapResult
from domain.ratings.openskill.calculator import OpenSkillParameters, TeamOpenSkillCalculator


def test_openskill_parameter_defaults_are_expected_constants() -> None:
    params = OpenSkillParameters()
    assert params.initial_mu == pytest.approx(25.0)
    assert params.initial_sigma == pytest.approx(25.0 / 3.0)
    assert params.beta == pytest.approx(25.0 / 6.0)
    assert params.kappa == pytest.approx(0.0001)
    assert params.tau == pytest.approx(25.0 / 300.0)
    assert params.limit_sigma is False
    assert params.balance is False
    assert params.ordinal_z == pytest.approx(3.0)


def test_equal_default_teams_have_half_expected_score() -> None:
    calculator = TeamOpenSkillCalculator(OpenSkillParameters())
    event_a, event_b = calculator.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
        )
    )

    assert event_a.expected_score == pytest.approx(0.5, abs=1e-6)
    assert event_b.expected_score == pytest.approx(0.5, abs=1e-6)


def test_single_map_win_increases_winner_mu_and_decreases_loser_mu() -> None:
    calculator = TeamOpenSkillCalculator(OpenSkillParameters())
    winner_event, loser_event = calculator.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
        )
    )

    assert winner_event.post_mu > winner_event.pre_mu
    assert loser_event.post_mu < loser_event.pre_mu
    assert winner_event.post_ordinal > winner_event.pre_ordinal
    assert loser_event.post_ordinal < loser_event.pre_ordinal


def test_ordinal_z_changes_conservative_rank_value() -> None:
    base = TeamOpenSkillCalculator(OpenSkillParameters(ordinal_z=3.0))
    aggressive = TeamOpenSkillCalculator(OpenSkillParameters(ordinal_z=5.0))

    base_event, _ = base.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
        )
    )
    aggressive_event, _ = aggressive.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
        )
    )

    assert aggressive_event.post_ordinal < base_event.post_ordinal


def test_invalid_map_with_same_teams_raises_error() -> None:
    calculator = TeamOpenSkillCalculator(OpenSkillParameters())

    with pytest.raises(ValueError, match="identical teams"):
        calculator.process_map(
            TeamMapResult(
                match_id=1,
                map_id=1,
                map_number=1,
                event_time=datetime(2026, 1, 1, 12, 0, 0),
                team1_id=100,
                team2_id=100,
                winner_id=100,
            )
        )
