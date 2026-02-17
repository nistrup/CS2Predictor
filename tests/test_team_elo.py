"""Unit tests for team Elo calculations."""

from __future__ import annotations

from datetime import datetime

import pytest

from elo.team_elo import (
    EloParameters,
    TeamEloCalculator,
    TeamMapResult,
    calculate_expected_score,
)


def test_expected_score_equal_ratings_is_half() -> None:
    expected = calculate_expected_score(1500.0, 1500.0, 400.0)
    assert expected == pytest.approx(0.5)


def test_expected_scores_sum_to_one() -> None:
    expected_a = calculate_expected_score(1600.0, 1500.0, 400.0)
    expected_b = calculate_expected_score(1500.0, 1600.0, 400.0)
    assert expected_a + expected_b == pytest.approx(1.0)


def test_map_update_is_zero_sum() -> None:
    calculator = TeamEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
    team1_event, team2_event = calculator.process_map(
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
    assert team1_event.elo_delta + team2_event.elo_delta == pytest.approx(0.0)
    assert team1_event.post_elo + team2_event.post_elo == pytest.approx(3000.0)
