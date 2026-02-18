"""Unit tests for match-level team Glicko-2 calculations."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from domain.ratings.common import TeamMatchResult
from domain.ratings.glicko2.calculator import Glicko2Parameters
from domain.ratings.glicko2.match_calculator import TeamMatchGlicko2Calculator


def test_match_win_increases_winner_rating() -> None:
    calculator = TeamMatchGlicko2Calculator(Glicko2Parameters())

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

    assert winner_event.post_rating > winner_event.pre_rating
    assert loser_event.post_rating < loser_event.pre_rating
    assert winner_event.post_rd < winner_event.pre_rd
    assert loser_event.post_rd < loser_event.pre_rd


def test_inactivity_inflates_pre_match_rd() -> None:
    calculator = TeamMatchGlicko2Calculator(Glicko2Parameters(rating_period_days=1.0))
    first_time = datetime(2026, 1, 1, 12, 0, 0)

    first_event, _ = calculator.process_match(
        TeamMatchResult(
            match_id=1,
            event_time=first_time,
            team1_id=100,
            team2_id=200,
            winner_id=100,
            team1_maps_won=2,
            team2_maps_won=1,
        )
    )
    second_event, _ = calculator.process_match(
        TeamMatchResult(
            match_id=2,
            event_time=first_time + timedelta(days=30),
            team1_id=100,
            team2_id=200,
            winner_id=100,
            team1_maps_won=2,
            team2_maps_won=0,
        )
    )

    assert second_event.pre_rd > first_event.post_rd


def test_invalid_match_winner_raises() -> None:
    calculator = TeamMatchGlicko2Calculator(Glicko2Parameters())
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
