"""Unit tests for match-level team OpenSkill calculations."""

from __future__ import annotations

from datetime import datetime

import pytest

from domain.ratings.common import TeamMatchResult
from domain.ratings.openskill.calculator import OpenSkillParameters
from domain.ratings.openskill.match_calculator import TeamMatchOpenSkillCalculator


def test_match_win_increases_winner_mu_and_decreases_loser_mu() -> None:
    calculator = TeamMatchOpenSkillCalculator(OpenSkillParameters())
    winner_event, loser_event = calculator.process_match(
        TeamMatchResult(
            match_id=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            team1_maps_won=2,
            team2_maps_won=0,
        )
    )

    assert winner_event.post_mu > winner_event.pre_mu
    assert loser_event.post_mu < loser_event.pre_mu
    assert winner_event.post_ordinal > winner_event.pre_ordinal
    assert loser_event.post_ordinal < loser_event.pre_ordinal


def test_match_has_half_expected_score_for_equal_teams() -> None:
    calculator = TeamMatchOpenSkillCalculator(OpenSkillParameters())
    team1_event, team2_event = calculator.process_match(
        TeamMatchResult(
            match_id=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            team1_maps_won=2,
            team2_maps_won=1,
        )
    )

    assert team1_event.expected_score == pytest.approx(0.5, abs=1e-6)
    assert team2_event.expected_score == pytest.approx(0.5, abs=1e-6)


def test_invalid_match_winner_raises() -> None:
    calculator = TeamMatchOpenSkillCalculator(OpenSkillParameters())
    with pytest.raises(ValueError, match=r"winner_id=300 does not belong to match teams"):
        calculator.process_match(
            TeamMatchResult(
                match_id=1,
                event_time=datetime(2026, 1, 1, 12, 0, 0),
                team1_id=100,
                team2_id=200,
                winner_id=300,
                team1_maps_won=2,
                team2_maps_won=1,
            )
        )
