"""Unit tests for team Glicko-2 calculations."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from domain.ratings.common import TeamMapResult
from domain.ratings.glicko2.calculator import (
    Glicko2OpponentResult,
    Glicko2Parameters,
    TeamGlicko2Calculator,
    calculate_expected_score,
    update_glicko2_player,
)


def test_glicko2_parameter_defaults_are_expected_constants() -> None:
    params = Glicko2Parameters()
    assert params.initial_rating == pytest.approx(1500.0)
    assert params.initial_rd == pytest.approx(350.0)
    assert params.initial_volatility == pytest.approx(0.06)
    assert params.tau == pytest.approx(0.5)
    assert params.rating_period_days == pytest.approx(1.0)
    assert params.min_rd == pytest.approx(30.0)
    assert params.max_rd == pytest.approx(350.0)
    assert params.epsilon == pytest.approx(1e-6)


def test_expected_score_equal_ratings_is_half() -> None:
    expected = calculate_expected_score(
        rating=1500.0,
        rd=200.0,
        opponent_rating=1500.0,
        opponent_rd=200.0,
    )
    assert expected == pytest.approx(0.5)


def test_single_map_win_increases_winner_and_decreases_loser() -> None:
    calculator = TeamGlicko2Calculator(Glicko2Parameters())

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

    assert team1_event.post_rating > team1_event.pre_rating
    assert team2_event.post_rating < team2_event.pre_rating
    assert team1_event.post_rd < team1_event.pre_rd
    assert team2_event.post_rd < team2_event.pre_rd
    assert team1_event.actual_score == pytest.approx(1.0)
    assert team2_event.actual_score == pytest.approx(0.0)


def test_inactivity_inflates_pre_match_rd() -> None:
    calculator = TeamGlicko2Calculator(Glicko2Parameters(rating_period_days=1.0))
    first_time = datetime(2026, 1, 1, 12, 0, 0)

    first_event, _ = calculator.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            event_time=first_time,
            team1_id=100,
            team2_id=200,
            winner_id=100,
        )
    )
    second_event, _ = calculator.process_map(
        TeamMapResult(
            match_id=2,
            map_id=2,
            map_number=1,
            event_time=first_time + timedelta(days=45),
            team1_id=100,
            team2_id=200,
            winner_id=100,
        )
    )

    assert second_event.pre_rd > first_event.post_rd


def test_glicko2_reference_example_matches_expected_values() -> None:
    rating, rd, volatility = update_glicko2_player(
        rating=1500.0,
        rd=200.0,
        volatility=0.06,
        results=[
            Glicko2OpponentResult(opponent_rating=1400.0, opponent_rd=30.0, score=1.0),
            Glicko2OpponentResult(opponent_rating=1550.0, opponent_rd=100.0, score=0.0),
            Glicko2OpponentResult(opponent_rating=1700.0, opponent_rd=300.0, score=0.0),
        ],
        tau=0.5,
        epsilon=1e-6,
    )

    assert rating == pytest.approx(1464.06, abs=0.1)
    assert rd == pytest.approx(151.52, abs=0.1)
    assert volatility == pytest.approx(0.05999, abs=1e-4)
