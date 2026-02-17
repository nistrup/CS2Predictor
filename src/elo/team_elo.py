"""Team-level Elo logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EloParameters:
    initial_elo: float = 1500.0
    k_factor: float = 20.0
    scale_factor: float = 400.0


@dataclass(frozen=True)
class TeamMapResult:
    match_id: int
    map_id: int
    map_number: int
    event_time: datetime
    team1_id: int
    team2_id: int
    winner_id: int


@dataclass(frozen=True)
class TeamEloEvent:
    team_id: int
    opponent_team_id: int
    match_id: int
    map_id: int
    map_number: int
    event_time: datetime
    won: bool
    actual_score: float
    expected_score: float
    pre_elo: float
    elo_delta: float
    post_elo: float
    k_factor: float
    scale_factor: float
    initial_elo: float


def calculate_expected_score(rating: float, opponent_rating: float, scale_factor: float) -> float:
    """Compute the Elo expected score for one side."""
    return 1.0 / (1.0 + 10.0 ** ((opponent_rating - rating) / scale_factor))


class TeamEloCalculator:
    """Stateful map-by-map team Elo calculator."""

    def __init__(self, params: EloParameters) -> None:
        self.params = params
        self._ratings: dict[int, float] = {}

    def get_rating(self, team_id: int) -> float:
        return self._ratings.get(team_id, self.params.initial_elo)

    def tracked_team_count(self) -> int:
        return len(self._ratings)

    def process_map(self, map_result: TeamMapResult) -> tuple[TeamEloEvent, TeamEloEvent]:
        if map_result.team1_id == map_result.team2_id:
            raise ValueError(
                f"map_id={map_result.map_id} has identical teams ({map_result.team1_id})"
            )

        if map_result.winner_id not in (map_result.team1_id, map_result.team2_id):
            raise ValueError(
                f"winner_id={map_result.winner_id} does not belong to map teams "
                f"{map_result.team1_id}/{map_result.team2_id} for map_id={map_result.map_id}"
            )

        team1_pre = self.get_rating(map_result.team1_id)
        team2_pre = self.get_rating(map_result.team2_id)

        team1_expected = calculate_expected_score(
            rating=team1_pre,
            opponent_rating=team2_pre,
            scale_factor=self.params.scale_factor,
        )
        team2_expected = 1.0 - team1_expected

        team1_actual = 1.0 if map_result.winner_id == map_result.team1_id else 0.0
        team2_actual = 1.0 - team1_actual

        team1_delta = self.params.k_factor * (team1_actual - team1_expected)
        team2_delta = -team1_delta

        team1_post = team1_pre + team1_delta
        team2_post = team2_pre + team2_delta

        self._ratings[map_result.team1_id] = team1_post
        self._ratings[map_result.team2_id] = team2_post

        team1_event = TeamEloEvent(
            team_id=map_result.team1_id,
            opponent_team_id=map_result.team2_id,
            match_id=map_result.match_id,
            map_id=map_result.map_id,
            map_number=map_result.map_number,
            event_time=map_result.event_time,
            won=bool(team1_actual),
            actual_score=team1_actual,
            expected_score=team1_expected,
            pre_elo=team1_pre,
            elo_delta=team1_delta,
            post_elo=team1_post,
            k_factor=self.params.k_factor,
            scale_factor=self.params.scale_factor,
            initial_elo=self.params.initial_elo,
        )
        team2_event = TeamEloEvent(
            team_id=map_result.team2_id,
            opponent_team_id=map_result.team1_id,
            match_id=map_result.match_id,
            map_id=map_result.map_id,
            map_number=map_result.map_number,
            event_time=map_result.event_time,
            won=bool(team2_actual),
            actual_score=team2_actual,
            expected_score=team2_expected,
            pre_elo=team2_pre,
            elo_delta=team2_delta,
            post_elo=team2_post,
            k_factor=self.params.k_factor,
            scale_factor=self.params.scale_factor,
            initial_elo=self.params.initial_elo,
        )
        return team1_event, team2_event
