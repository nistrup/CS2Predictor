"""Unit tests for player-level Elo calculations."""

from __future__ import annotations

from datetime import datetime

import pytest

from domain.ratings.common import (
    PlayerMapParticipant,
    PlayerMapResult,
    PlayerMatchParticipant,
    PlayerMatchResult,
)
from domain.ratings.elo.calculator import EloParameters
from domain.ratings.elo.player_calculator import PlayerEloCalculator
from domain.ratings.elo.player_map_specific_calculator import (
    MapSpecificEloParameters,
    PlayerMapSpecificEloCalculator,
)
from domain.ratings.elo.player_match_calculator import PlayerMatchEloCalculator


def _map_result(*, winner_id: int, map_name: str | None = "Mirage") -> PlayerMapResult:
    return PlayerMapResult(
        match_id=1,
        map_id=1,
        map_number=1,
        map_name=map_name,
        event_time=datetime(2026, 1, 1, 12, 0, 0),
        team1_id=100,
        team2_id=200,
        winner_id=winner_id,
        team1_players=(
            PlayerMapParticipant(player_id=1, team_id=100),
            PlayerMapParticipant(player_id=2, team_id=100),
        ),
        team2_players=(
            PlayerMapParticipant(player_id=3, team_id=200),
            PlayerMapParticipant(player_id=4, team_id=200),
        ),
    )


def _match_result(*, winner_id: int) -> PlayerMatchResult:
    return PlayerMatchResult(
        match_id=1,
        event_time=datetime(2026, 1, 1, 12, 0, 0),
        team1_id=100,
        team2_id=200,
        winner_id=winner_id,
        team1_maps_won=2 if winner_id == 100 else 1,
        team2_maps_won=1 if winner_id == 100 else 2,
        team1_players=(
            PlayerMatchParticipant(player_id=1, team_id=100, maps_played=2),
            PlayerMatchParticipant(player_id=2, team_id=100, maps_played=2),
        ),
        team2_players=(
            PlayerMatchParticipant(player_id=3, team_id=200, maps_played=2),
            PlayerMatchParticipant(player_id=4, team_id=200, maps_played=2),
        ),
    )


def test_map_win_updates_player_elos_by_team_outcome() -> None:
    calculator = PlayerEloCalculator(EloParameters())
    events = calculator.process_map(_map_result(winner_id=100))

    assert len(events) == 4
    winners = [event for event in events if event.team_id == 100]
    losers = [event for event in events if event.team_id == 200]
    assert all(event.post_elo > event.pre_elo for event in winners)
    assert all(event.post_elo < event.pre_elo for event in losers)


def test_match_win_updates_player_elos_by_team_outcome() -> None:
    calculator = PlayerMatchEloCalculator(EloParameters())
    events = calculator.process_match(_match_result(winner_id=100))

    assert len(events) == 4
    winners = [event for event in events if event.team_id == 100]
    losers = [event for event in events if event.team_id == 200]
    assert all(event.post_elo > event.pre_elo for event in winners)
    assert all(event.post_elo < event.pre_elo for event in losers)


def test_map_specific_blend_weight_increases_after_history() -> None:
    calculator = PlayerMapSpecificEloCalculator(MapSpecificEloParameters(map_prior_games=20.0))

    first_events = calculator.process_map(_map_result(winner_id=100, map_name="Mirage"))
    second_events = calculator.process_map(
        PlayerMapResult(
            match_id=2,
            map_id=2,
            map_number=1,
            map_name="Mirage",
            event_time=datetime(2026, 1, 2, 12, 0, 0),
            team1_id=100,
            team2_id=300,
            winner_id=100,
            team1_players=(
                PlayerMapParticipant(player_id=1, team_id=100),
                PlayerMapParticipant(player_id=2, team_id=100),
            ),
            team2_players=(
                PlayerMapParticipant(player_id=5, team_id=300),
                PlayerMapParticipant(player_id=6, team_id=300),
            ),
        )
    )

    first_event = next(event for event in first_events if event.player_id == 1)
    second_event = next(event for event in second_events if event.player_id == 1)

    assert first_event.map_games_played_pre == 0
    assert second_event.map_games_played_pre == 1
    assert first_event.map_blend_weight < second_event.map_blend_weight


def test_invalid_map_winner_raises() -> None:
    calculator = PlayerEloCalculator(EloParameters())
    with pytest.raises(ValueError, match=r"winner_id=999 does not belong to map teams"):
        calculator.process_map(_map_result(winner_id=999))
