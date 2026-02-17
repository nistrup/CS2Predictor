"""Unit tests for match-level team Elo calculations."""

from __future__ import annotations

from datetime import datetime

import pytest

from domain.ratings.common import TeamMatchResult
from domain.ratings.elo.calculator import EloParameters
from domain.ratings.elo.match_calculator import TeamMatchEloCalculator


def test_match_update_is_zero_sum() -> None:
    calculator = TeamMatchEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
    team1_event, team2_event = calculator.process_match(
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

    assert team1_event.elo_delta + team2_event.elo_delta == pytest.approx(0.0)
    assert team1_event.post_elo + team2_event.post_elo == pytest.approx(3000.0)


def test_match_win_increases_winner_rating() -> None:
    calculator = TeamMatchEloCalculator(EloParameters(initial_elo=1500.0, k_factor=20.0))
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

    assert team1_event.post_elo > team1_event.pre_elo
    assert team2_event.post_elo < team2_event.pre_elo


def test_match_format_multiplier_affects_delta() -> None:
    calculator = TeamMatchEloCalculator(
        EloParameters(initial_elo=1500.0, k_factor=20.0, bo3_match_multiplier=1.5)
    )
    bo1_event, _ = calculator.process_match(
        TeamMatchResult(
            match_id=1,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            team1_maps_won=1,
            team2_maps_won=0,
            match_format="BO1",
        )
    )
    bo3_event, _ = calculator.process_match(
        TeamMatchResult(
            match_id=2,
            event_time=datetime(2026, 1, 2, 12, 0, 0),
            team1_id=300,
            team2_id=400,
            winner_id=300,
            team1_maps_won=2,
            team2_maps_won=0,
            match_format="BO3",
        )
    )

    assert bo3_event.k_factor > bo1_event.k_factor


def test_invalid_match_winner_raises() -> None:
    calculator = TeamMatchEloCalculator(EloParameters())
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
