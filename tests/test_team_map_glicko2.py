"""Unit tests for map-specific team Glicko-2 calculations."""

from __future__ import annotations

from datetime import datetime

import pytest

from domain.ratings.common import TeamMapResult
from domain.ratings.glicko2.map_specific_calculator import (
    MapSpecificGlicko2Parameters,
    TeamMapSpecificGlicko2Calculator,
)


def test_map_specific_parameter_defaults_include_prior_games() -> None:
    params = MapSpecificGlicko2Parameters()
    assert params.initial_rating == pytest.approx(1500.0)
    assert params.map_prior_games == pytest.approx(20.0)


def test_first_map_uses_global_baseline_and_zero_blend_weight() -> None:
    calculator = TeamMapSpecificGlicko2Calculator(MapSpecificGlicko2Parameters())
    team1_event, team2_event = calculator.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            map_name="mirage",
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
        )
    )

    assert team1_event.pre_global_rating == pytest.approx(1500.0)
    assert team1_event.pre_map_rating == pytest.approx(1500.0)
    assert team1_event.pre_effective_rating == pytest.approx(1500.0)
    assert team1_event.map_blend_weight == pytest.approx(0.0)
    assert team2_event.map_blend_weight == pytest.approx(0.0)


def test_blend_weight_increases_after_map_history_exists() -> None:
    calculator = TeamMapSpecificGlicko2Calculator(MapSpecificGlicko2Parameters(map_prior_games=20.0))

    first_event, _ = calculator.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            map_name="Mirage",
            event_time=datetime(2026, 1, 1, 12, 0, 0),
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
            map_name="Mirage",
            event_time=datetime(2026, 1, 2, 12, 0, 0),
            team1_id=100,
            team2_id=300,
            winner_id=100,
        )
    )

    assert first_event.map_games_played_pre == 0
    assert second_event.map_games_played_pre == 1
    assert first_event.map_blend_weight < second_event.map_blend_weight


def test_missing_map_name_uses_unknown_bucket() -> None:
    calculator = TeamMapSpecificGlicko2Calculator(MapSpecificGlicko2Parameters())
    team1_event, _ = calculator.process_map(
        TeamMapResult(
            match_id=1,
            map_id=1,
            map_number=1,
            map_name=None,
            event_time=datetime(2026, 1, 1, 12, 0, 0),
            team1_id=100,
            team2_id=200,
            winner_id=100,
        )
    )

    assert team1_event.map_name == "UNKNOWN"


def test_invalid_winner_raises() -> None:
    calculator = TeamMapSpecificGlicko2Calculator(MapSpecificGlicko2Parameters())
    with pytest.raises(ValueError, match=r"winner_id=300 does not belong to map teams"):
        calculator.process_map(
            TeamMapResult(
                match_id=1,
                map_id=1,
                map_number=1,
                map_name="Inferno",
                event_time=datetime(2026, 1, 1, 12, 0, 0),
                team1_id=100,
                team2_id=200,
                winner_id=300,
            )
        )
