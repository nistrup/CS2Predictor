"""Match-level team Glicko-2 logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.ratings.common import TeamMatchResult
from domain.ratings.glicko2.calculator import (
    Glicko2OpponentResult,
    Glicko2Parameters,
    TeamGlicko2Calculator,
    _TeamGlicko2State,
    calculate_expected_score,
    update_glicko2_player,
)
from domain.ratings.match_adapter import MatchAdapterMixin


@dataclass(frozen=True)
class TeamMatchGlicko2Event:
    team_id: int
    opponent_team_id: int
    match_id: int
    event_time: datetime
    won: bool
    actual_score: float
    expected_score: float
    pre_rating: float
    pre_rd: float
    pre_volatility: float
    rating_delta: float
    rd_delta: float
    volatility_delta: float
    post_rating: float
    post_rd: float
    post_volatility: float
    tau: float
    rating_period_days: float
    initial_rating: float
    initial_rd: float
    initial_volatility: float
    team_maps_won: int
    opponent_maps_won: int


class TeamMatchGlicko2Calculator(MatchAdapterMixin, TeamGlicko2Calculator):
    """Stateful match-by-match team Glicko-2 calculator."""

    def __init__(self, params: Glicko2Parameters) -> None:
        super().__init__(params=params)

    def process_match(
        self,
        match_result: TeamMatchResult,
    ) -> tuple[TeamMatchGlicko2Event, TeamMatchGlicko2Event]:
        self._validate_team_match(match_result)

        team1_state = self._get_or_create_state(match_result.team1_id)
        team2_state = self._get_or_create_state(match_result.team2_id)

        team1_pre_rating = team1_state.rating
        team2_pre_rating = team2_state.rating
        team1_pre_vol = team1_state.volatility
        team2_pre_vol = team2_state.volatility
        team1_pre_rd = self._inflate_rd_for_inactivity(
            team_id=match_result.team1_id,
            rd=team1_state.rd,
            volatility=team1_state.volatility,
            event_time=match_result.event_time,
        )
        team2_pre_rd = self._inflate_rd_for_inactivity(
            team_id=match_result.team2_id,
            rd=team2_state.rd,
            volatility=team2_state.volatility,
            event_time=match_result.event_time,
        )

        team1_actual, team2_actual, team1_maps_won, team2_maps_won = self._match_outcome(match_result)

        team1_expected = calculate_expected_score(
            rating=team1_pre_rating,
            rd=team1_pre_rd,
            opponent_rating=team2_pre_rating,
            opponent_rd=team2_pre_rd,
        )
        team2_expected = calculate_expected_score(
            rating=team2_pre_rating,
            rd=team2_pre_rd,
            opponent_rating=team1_pre_rating,
            opponent_rd=team1_pre_rd,
        )

        team1_post_rating, team1_post_rd, team1_post_vol = update_glicko2_player(
            rating=team1_pre_rating,
            rd=team1_pre_rd,
            volatility=team1_pre_vol,
            results=[
                Glicko2OpponentResult(
                    opponent_rating=team2_pre_rating,
                    opponent_rd=team2_pre_rd,
                    score=team1_actual,
                )
            ],
            tau=self.params.tau,
            epsilon=self.params.epsilon,
        )
        team2_post_rating, team2_post_rd, team2_post_vol = update_glicko2_player(
            rating=team2_pre_rating,
            rd=team2_pre_rd,
            volatility=team2_pre_vol,
            results=[
                Glicko2OpponentResult(
                    opponent_rating=team1_pre_rating,
                    opponent_rd=team1_pre_rd,
                    score=team2_actual,
                )
            ],
            tau=self.params.tau,
            epsilon=self.params.epsilon,
        )

        team1_post_rd = self._clamp_rd(team1_post_rd)
        team2_post_rd = self._clamp_rd(team2_post_rd)

        self._states[match_result.team1_id] = _TeamGlicko2State(
            rating=team1_post_rating,
            rd=team1_post_rd,
            volatility=team1_post_vol,
        )
        self._states[match_result.team2_id] = _TeamGlicko2State(
            rating=team2_post_rating,
            rd=team2_post_rd,
            volatility=team2_post_vol,
        )
        self._last_event_times[match_result.team1_id] = match_result.event_time
        self._last_event_times[match_result.team2_id] = match_result.event_time

        team1_event = TeamMatchGlicko2Event(
            team_id=match_result.team1_id,
            opponent_team_id=match_result.team2_id,
            match_id=match_result.match_id,
            event_time=match_result.event_time,
            won=bool(team1_actual),
            actual_score=team1_actual,
            expected_score=team1_expected,
            pre_rating=team1_pre_rating,
            pre_rd=team1_pre_rd,
            pre_volatility=team1_pre_vol,
            rating_delta=team1_post_rating - team1_pre_rating,
            rd_delta=team1_post_rd - team1_pre_rd,
            volatility_delta=team1_post_vol - team1_pre_vol,
            post_rating=team1_post_rating,
            post_rd=team1_post_rd,
            post_volatility=team1_post_vol,
            tau=self.params.tau,
            rating_period_days=self.params.rating_period_days,
            initial_rating=self.params.initial_rating,
            initial_rd=self.params.initial_rd,
            initial_volatility=self.params.initial_volatility,
            team_maps_won=team1_maps_won,
            opponent_maps_won=team2_maps_won,
        )
        team2_event = TeamMatchGlicko2Event(
            team_id=match_result.team2_id,
            opponent_team_id=match_result.team1_id,
            match_id=match_result.match_id,
            event_time=match_result.event_time,
            won=bool(team2_actual),
            actual_score=team2_actual,
            expected_score=team2_expected,
            pre_rating=team2_pre_rating,
            pre_rd=team2_pre_rd,
            pre_volatility=team2_pre_vol,
            rating_delta=team2_post_rating - team2_pre_rating,
            rd_delta=team2_post_rd - team2_pre_rd,
            volatility_delta=team2_post_vol - team2_pre_vol,
            post_rating=team2_post_rating,
            post_rd=team2_post_rd,
            post_volatility=team2_post_vol,
            tau=self.params.tau,
            rating_period_days=self.params.rating_period_days,
            initial_rating=self.params.initial_rating,
            initial_rd=self.params.initial_rd,
            initial_volatility=self.params.initial_volatility,
            team_maps_won=team2_maps_won,
            opponent_maps_won=team1_maps_won,
        )
        return team1_event, team2_event
