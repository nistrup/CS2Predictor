"""Map-specific team Glicko-2 logic with global-rating shrinkage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.ratings.common import TeamMapResult
from domain.ratings.glicko2.calculator import (
    GLICKO2_SCALE,
    Glicko2OpponentResult,
    Glicko2Parameters,
    TeamGlicko2Calculator,
    _TeamGlicko2State,
    calculate_expected_score,
    update_glicko2_player,
)
from domain.ratings.map_specific_mixin import MapSpecificMixin


@dataclass(frozen=True)
class MapSpecificGlicko2Parameters(Glicko2Parameters):
    """Glicko-2 parameters plus map-specific shrinkage control."""

    map_prior_games: float = 20.0


@dataclass(frozen=True)
class TeamMapGlicko2Event:
    team_id: int
    opponent_team_id: int
    match_id: int
    map_id: int
    map_number: int
    map_name: str
    event_time: datetime
    won: bool
    actual_score: float
    expected_score: float
    pre_global_rating: float
    pre_map_rating: float
    pre_effective_rating: float
    pre_global_rd: float
    pre_map_rd: float
    pre_effective_rd: float
    pre_global_volatility: float
    pre_map_volatility: float
    pre_effective_volatility: float
    rating_delta: float
    rd_delta: float
    volatility_delta: float
    post_global_rating: float
    post_map_rating: float
    post_effective_rating: float
    post_global_rd: float
    post_map_rd: float
    post_effective_rd: float
    post_global_volatility: float
    post_map_volatility: float
    post_effective_volatility: float
    map_games_played_pre: int
    map_blend_weight: float
    tau: float
    rating_period_days: float
    initial_rating: float
    initial_rd: float
    initial_volatility: float
    map_prior_games: float


class TeamMapSpecificGlicko2Calculator(MapSpecificMixin, TeamGlicko2Calculator):
    """Stateful map-by-map calculator blending map-specific and global Glicko-2 state."""

    def __init__(self, params: MapSpecificGlicko2Parameters) -> None:
        super().__init__(params=params)
        self.params = params
        self._map_states: dict[tuple[int, str], _TeamGlicko2State] = {}
        self._map_games_played = {}
        self._map_last_event_times = {}

    def _get_or_create_map_state(self, *, team_id: int, map_name: str) -> _TeamGlicko2State:
        key = self._map_key(team_id=team_id, map_name=map_name)
        existing = self._map_states.get(key)
        if existing is not None:
            return existing

        state = _TeamGlicko2State(
            rating=self.params.initial_rating,
            rd=self._clamp_rd(self.params.initial_rd),
            volatility=self.params.initial_volatility,
        )
        self._map_states[key] = state
        return state

    def _inflate_map_rd_for_inactivity(
        self,
        *,
        team_id: int,
        map_name: str,
        rd: float,
        volatility: float,
        event_time: datetime,
    ) -> float:
        key = self._map_key(team_id=team_id, map_name=map_name)
        last_event_time = self._map_last_event_times.get(key)
        if last_event_time is None:
            return self._clamp_rd(rd)

        inactive_days = (event_time - last_event_time).total_seconds() / 86_400.0
        if inactive_days <= 0.0:
            return self._clamp_rd(rd)

        inactive_periods = inactive_days / self.params.rating_period_days
        if inactive_periods <= 0.0:
            return self._clamp_rd(rd)

        # Keep the same inactivity model as the global calculator.
        inflated_rd = (
            ((rd / GLICKO2_SCALE) ** 2 + ((volatility**2) * inactive_periods)) ** 0.5
            * GLICKO2_SCALE
        )
        return self._clamp_rd(inflated_rd)

    def _clamp_volatility(self, volatility: float) -> float:
        return max(volatility, 1e-9)

    def process_map(self, map_result: TeamMapResult) -> tuple[TeamMapGlicko2Event, TeamMapGlicko2Event]:
        if map_result.team1_id == map_result.team2_id:
            raise ValueError(
                f"map_id={map_result.map_id} has identical teams ({map_result.team1_id})"
            )
        if map_result.winner_id not in (map_result.team1_id, map_result.team2_id):
            raise ValueError(
                f"winner_id={map_result.winner_id} does not belong to map teams "
                f"{map_result.team1_id}/{map_result.team2_id} for map_id={map_result.map_id}"
            )

        map_name = self._normalize_map_name(map_result.map_name)

        team1_global_state = self._get_or_create_state(map_result.team1_id)
        team2_global_state = self._get_or_create_state(map_result.team2_id)
        team1_map_state = self._get_or_create_map_state(team_id=map_result.team1_id, map_name=map_name)
        team2_map_state = self._get_or_create_map_state(team_id=map_result.team2_id, map_name=map_name)

        team1_global_pre_rating = team1_global_state.rating
        team2_global_pre_rating = team2_global_state.rating
        team1_global_pre_vol = team1_global_state.volatility
        team2_global_pre_vol = team2_global_state.volatility
        team1_global_pre_rd = self._inflate_rd_for_inactivity(
            team_id=map_result.team1_id,
            rd=team1_global_state.rd,
            volatility=team1_global_state.volatility,
            event_time=map_result.event_time,
        )
        team2_global_pre_rd = self._inflate_rd_for_inactivity(
            team_id=map_result.team2_id,
            rd=team2_global_state.rd,
            volatility=team2_global_state.volatility,
            event_time=map_result.event_time,
        )

        team1_map_pre_rating = team1_map_state.rating
        team2_map_pre_rating = team2_map_state.rating
        team1_map_pre_vol = team1_map_state.volatility
        team2_map_pre_vol = team2_map_state.volatility
        team1_map_pre_rd = self._inflate_map_rd_for_inactivity(
            team_id=map_result.team1_id,
            map_name=map_name,
            rd=team1_map_state.rd,
            volatility=team1_map_state.volatility,
            event_time=map_result.event_time,
        )
        team2_map_pre_rd = self._inflate_map_rd_for_inactivity(
            team_id=map_result.team2_id,
            map_name=map_name,
            rd=team2_map_state.rd,
            volatility=team2_map_state.volatility,
            event_time=map_result.event_time,
        )

        team1_map_games_pre = self._get_map_games_played(team_id=map_result.team1_id, map_name=map_name)
        team2_map_games_pre = self._get_map_games_played(team_id=map_result.team2_id, map_name=map_name)
        team1_blend_weight = self._map_blend_weight(map_games_played=team1_map_games_pre)
        team2_blend_weight = self._map_blend_weight(map_games_played=team2_map_games_pre)

        team1_effective_pre_rating = (
            (team1_blend_weight * team1_map_pre_rating)
            + ((1.0 - team1_blend_weight) * team1_global_pre_rating)
        )
        team2_effective_pre_rating = (
            (team2_blend_weight * team2_map_pre_rating)
            + ((1.0 - team2_blend_weight) * team2_global_pre_rating)
        )
        team1_effective_pre_rd = (
            (team1_blend_weight * team1_map_pre_rd)
            + ((1.0 - team1_blend_weight) * team1_global_pre_rd)
        )
        team2_effective_pre_rd = (
            (team2_blend_weight * team2_map_pre_rd)
            + ((1.0 - team2_blend_weight) * team2_global_pre_rd)
        )
        team1_effective_pre_vol = (
            (team1_blend_weight * team1_map_pre_vol)
            + ((1.0 - team1_blend_weight) * team1_global_pre_vol)
        )
        team2_effective_pre_vol = (
            (team2_blend_weight * team2_map_pre_vol)
            + ((1.0 - team2_blend_weight) * team2_global_pre_vol)
        )

        team1_actual = 1.0 if map_result.winner_id == map_result.team1_id else 0.0
        team2_actual = 1.0 - team1_actual

        team1_expected = calculate_expected_score(
            rating=team1_effective_pre_rating,
            rd=team1_effective_pre_rd,
            opponent_rating=team2_effective_pre_rating,
            opponent_rd=team2_effective_pre_rd,
        )
        team2_expected = calculate_expected_score(
            rating=team2_effective_pre_rating,
            rd=team2_effective_pre_rd,
            opponent_rating=team1_effective_pre_rating,
            opponent_rd=team1_effective_pre_rd,
        )

        team1_effective_post_rating, team1_effective_post_rd, team1_effective_post_vol = update_glicko2_player(
            rating=team1_effective_pre_rating,
            rd=team1_effective_pre_rd,
            volatility=team1_effective_pre_vol,
            results=[
                Glicko2OpponentResult(
                    opponent_rating=team2_effective_pre_rating,
                    opponent_rd=team2_effective_pre_rd,
                    score=team1_actual,
                )
            ],
            tau=self.params.tau,
            epsilon=self.params.epsilon,
        )
        team2_effective_post_rating, team2_effective_post_rd, team2_effective_post_vol = update_glicko2_player(
            rating=team2_effective_pre_rating,
            rd=team2_effective_pre_rd,
            volatility=team2_effective_pre_vol,
            results=[
                Glicko2OpponentResult(
                    opponent_rating=team1_effective_pre_rating,
                    opponent_rd=team1_effective_pre_rd,
                    score=team2_actual,
                )
            ],
            tau=self.params.tau,
            epsilon=self.params.epsilon,
        )

        team1_effective_post_rd = self._clamp_rd(team1_effective_post_rd)
        team2_effective_post_rd = self._clamp_rd(team2_effective_post_rd)

        team1_rating_delta = team1_effective_post_rating - team1_effective_pre_rating
        team2_rating_delta = team2_effective_post_rating - team2_effective_pre_rating
        team1_rd_delta = team1_effective_post_rd - team1_effective_pre_rd
        team2_rd_delta = team2_effective_post_rd - team2_effective_pre_rd
        team1_vol_delta = team1_effective_post_vol - team1_effective_pre_vol
        team2_vol_delta = team2_effective_post_vol - team2_effective_pre_vol

        team1_global_post_rating = team1_global_pre_rating + team1_rating_delta
        team2_global_post_rating = team2_global_pre_rating + team2_rating_delta
        team1_map_post_rating = team1_map_pre_rating + team1_rating_delta
        team2_map_post_rating = team2_map_pre_rating + team2_rating_delta

        team1_global_post_rd = self._clamp_rd(team1_global_pre_rd + team1_rd_delta)
        team2_global_post_rd = self._clamp_rd(team2_global_pre_rd + team2_rd_delta)
        team1_map_post_rd = self._clamp_rd(team1_map_pre_rd + team1_rd_delta)
        team2_map_post_rd = self._clamp_rd(team2_map_pre_rd + team2_rd_delta)

        team1_global_post_vol = self._clamp_volatility(team1_global_pre_vol + team1_vol_delta)
        team2_global_post_vol = self._clamp_volatility(team2_global_pre_vol + team2_vol_delta)
        team1_map_post_vol = self._clamp_volatility(team1_map_pre_vol + team1_vol_delta)
        team2_map_post_vol = self._clamp_volatility(team2_map_pre_vol + team2_vol_delta)

        self._states[map_result.team1_id] = _TeamGlicko2State(
            rating=team1_global_post_rating,
            rd=team1_global_post_rd,
            volatility=team1_global_post_vol,
        )
        self._states[map_result.team2_id] = _TeamGlicko2State(
            rating=team2_global_post_rating,
            rd=team2_global_post_rd,
            volatility=team2_global_post_vol,
        )

        key1 = self._map_key(team_id=map_result.team1_id, map_name=map_name)
        key2 = self._map_key(team_id=map_result.team2_id, map_name=map_name)
        self._map_states[key1] = _TeamGlicko2State(
            rating=team1_map_post_rating,
            rd=team1_map_post_rd,
            volatility=team1_map_post_vol,
        )
        self._map_states[key2] = _TeamGlicko2State(
            rating=team2_map_post_rating,
            rd=team2_map_post_rd,
            volatility=team2_map_post_vol,
        )
        self._last_event_times[map_result.team1_id] = map_result.event_time
        self._last_event_times[map_result.team2_id] = map_result.event_time
        self._record_map_games_played(
            team1_id=map_result.team1_id,
            team2_id=map_result.team2_id,
            map_name=map_name,
            team1_games_pre=team1_map_games_pre,
            team2_games_pre=team2_map_games_pre,
            event_time=map_result.event_time,
        )

        team1_effective_post_rating = (
            (team1_blend_weight * team1_map_post_rating)
            + ((1.0 - team1_blend_weight) * team1_global_post_rating)
        )
        team2_effective_post_rating = (
            (team2_blend_weight * team2_map_post_rating)
            + ((1.0 - team2_blend_weight) * team2_global_post_rating)
        )
        team1_effective_post_rd = (
            (team1_blend_weight * team1_map_post_rd)
            + ((1.0 - team1_blend_weight) * team1_global_post_rd)
        )
        team2_effective_post_rd = (
            (team2_blend_weight * team2_map_post_rd)
            + ((1.0 - team2_blend_weight) * team2_global_post_rd)
        )
        team1_effective_post_vol = (
            (team1_blend_weight * team1_map_post_vol)
            + ((1.0 - team1_blend_weight) * team1_global_post_vol)
        )
        team2_effective_post_vol = (
            (team2_blend_weight * team2_map_post_vol)
            + ((1.0 - team2_blend_weight) * team2_global_post_vol)
        )

        team1_event = TeamMapGlicko2Event(
            team_id=map_result.team1_id,
            opponent_team_id=map_result.team2_id,
            match_id=map_result.match_id,
            map_id=map_result.map_id,
            map_number=map_result.map_number,
            map_name=map_name,
            event_time=map_result.event_time,
            won=bool(team1_actual),
            actual_score=team1_actual,
            expected_score=team1_expected,
            pre_global_rating=team1_global_pre_rating,
            pre_map_rating=team1_map_pre_rating,
            pre_effective_rating=team1_effective_pre_rating,
            pre_global_rd=team1_global_pre_rd,
            pre_map_rd=team1_map_pre_rd,
            pre_effective_rd=team1_effective_pre_rd,
            pre_global_volatility=team1_global_pre_vol,
            pre_map_volatility=team1_map_pre_vol,
            pre_effective_volatility=team1_effective_pre_vol,
            rating_delta=team1_rating_delta,
            rd_delta=team1_rd_delta,
            volatility_delta=team1_vol_delta,
            post_global_rating=team1_global_post_rating,
            post_map_rating=team1_map_post_rating,
            post_effective_rating=team1_effective_post_rating,
            post_global_rd=team1_global_post_rd,
            post_map_rd=team1_map_post_rd,
            post_effective_rd=team1_effective_post_rd,
            post_global_volatility=team1_global_post_vol,
            post_map_volatility=team1_map_post_vol,
            post_effective_volatility=team1_effective_post_vol,
            map_games_played_pre=team1_map_games_pre,
            map_blend_weight=team1_blend_weight,
            tau=self.params.tau,
            rating_period_days=self.params.rating_period_days,
            initial_rating=self.params.initial_rating,
            initial_rd=self.params.initial_rd,
            initial_volatility=self.params.initial_volatility,
            map_prior_games=self.params.map_prior_games,
        )
        team2_event = TeamMapGlicko2Event(
            team_id=map_result.team2_id,
            opponent_team_id=map_result.team1_id,
            match_id=map_result.match_id,
            map_id=map_result.map_id,
            map_number=map_result.map_number,
            map_name=map_name,
            event_time=map_result.event_time,
            won=bool(team2_actual),
            actual_score=team2_actual,
            expected_score=team2_expected,
            pre_global_rating=team2_global_pre_rating,
            pre_map_rating=team2_map_pre_rating,
            pre_effective_rating=team2_effective_pre_rating,
            pre_global_rd=team2_global_pre_rd,
            pre_map_rd=team2_map_pre_rd,
            pre_effective_rd=team2_effective_pre_rd,
            pre_global_volatility=team2_global_pre_vol,
            pre_map_volatility=team2_map_pre_vol,
            pre_effective_volatility=team2_effective_pre_vol,
            rating_delta=team2_rating_delta,
            rd_delta=team2_rd_delta,
            volatility_delta=team2_vol_delta,
            post_global_rating=team2_global_post_rating,
            post_map_rating=team2_map_post_rating,
            post_effective_rating=team2_effective_post_rating,
            post_global_rd=team2_global_post_rd,
            post_map_rd=team2_map_post_rd,
            post_effective_rd=team2_effective_post_rd,
            post_global_volatility=team2_global_post_vol,
            post_map_volatility=team2_map_post_vol,
            post_effective_volatility=team2_effective_post_vol,
            map_games_played_pre=team2_map_games_pre,
            map_blend_weight=team2_blend_weight,
            tau=self.params.tau,
            rating_period_days=self.params.rating_period_days,
            initial_rating=self.params.initial_rating,
            initial_rd=self.params.initial_rd,
            initial_volatility=self.params.initial_volatility,
            map_prior_games=self.params.map_prior_games,
        )
        return team1_event, team2_event
