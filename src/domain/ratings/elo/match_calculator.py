"""Match-level team Elo logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.ratings.common import TeamMatchResult
from domain.ratings.elo.calculator import EloParameters, TeamEloCalculator, calculate_expected_score
from domain.ratings.match_adapter import MatchAdapterMixin


@dataclass(frozen=True)
class TeamMatchEloEvent:
    team_id: int
    opponent_team_id: int
    match_id: int
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
    team_maps_won: int
    opponent_maps_won: int


class TeamMatchEloCalculator(MatchAdapterMixin, TeamEloCalculator):
    """Stateful match-by-match team Elo calculator."""

    def __init__(
        self,
        params: EloParameters,
        *,
        lookback_days: int | None = None,
        as_of_time: datetime | None = None,
    ) -> None:
        super().__init__(
            params=params,
            lookback_days=lookback_days,
            as_of_time=as_of_time,
        )

    def process_match(self, match_result: TeamMatchResult) -> tuple[TeamMatchEloEvent, TeamMatchEloEvent]:
        self._validate_team_match(match_result)

        team1_pre = self._apply_inactivity_decay(
            team_id=match_result.team1_id,
            event_time=match_result.event_time,
        )
        team2_pre = self._apply_inactivity_decay(
            team_id=match_result.team2_id,
            event_time=match_result.event_time,
        )

        team1_expected = calculate_expected_score(
            rating=team1_pre,
            opponent_rating=team2_pre,
            scale_factor=self.params.scale_factor,
        )
        team2_expected = 1.0 - team1_expected

        team1_actual, team2_actual, team1_maps_won, team2_maps_won = self._match_outcome(match_result)

        winner_pre_elo = team1_pre if team1_actual == 1.0 else team2_pre
        loser_pre_elo = team2_pre if team1_actual == 1.0 else team1_pre
        winner_expected_score = team1_expected if team1_actual == 1.0 else team2_expected

        effective_k = (
            self.params.k_factor
            * self._format_multiplier(match_result.match_format)
            * self._winner_outcome_multiplier(
                winner_pre_elo=winner_pre_elo,
                loser_pre_elo=loser_pre_elo,
            )
            * self._opponent_strength_multiplier(winner_expected_score=winner_expected_score)
            * (self.params.lan_multiplier if match_result.is_lan else 1.0)
            * self._recency_multiplier(match_result.event_time)
        )

        team1_delta = effective_k * (team1_actual - team1_expected)
        team2_delta = -team1_delta
        team1_post = team1_pre + team1_delta
        team2_post = team2_pre + team2_delta

        self._ratings[match_result.team1_id] = team1_post
        self._ratings[match_result.team2_id] = team2_post
        self._last_event_times[match_result.team1_id] = match_result.event_time
        self._last_event_times[match_result.team2_id] = match_result.event_time

        team1_event = TeamMatchEloEvent(
            team_id=match_result.team1_id,
            opponent_team_id=match_result.team2_id,
            match_id=match_result.match_id,
            event_time=match_result.event_time,
            won=bool(team1_actual),
            actual_score=team1_actual,
            expected_score=team1_expected,
            pre_elo=team1_pre,
            elo_delta=team1_delta,
            post_elo=team1_post,
            k_factor=effective_k,
            scale_factor=self.params.scale_factor,
            initial_elo=self.params.initial_elo,
            team_maps_won=team1_maps_won,
            opponent_maps_won=team2_maps_won,
        )
        team2_event = TeamMatchEloEvent(
            team_id=match_result.team2_id,
            opponent_team_id=match_result.team1_id,
            match_id=match_result.match_id,
            event_time=match_result.event_time,
            won=bool(team2_actual),
            actual_score=team2_actual,
            expected_score=team2_expected,
            pre_elo=team2_pre,
            elo_delta=team2_delta,
            post_elo=team2_post,
            k_factor=effective_k,
            scale_factor=self.params.scale_factor,
            initial_elo=self.params.initial_elo,
            team_maps_won=team2_maps_won,
            opponent_maps_won=team1_maps_won,
        )
        return team1_event, team2_event
