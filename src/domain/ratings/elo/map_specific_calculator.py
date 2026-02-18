"""Map-specific team Elo logic with global-rating shrinkage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.ratings.common import TeamMapResult
from domain.ratings.elo.calculator import EloParameters, TeamEloCalculator, calculate_expected_score
from domain.ratings.map_specific_mixin import MapSpecificMixin


@dataclass(frozen=True)
class MapSpecificEloParameters(EloParameters):
    """Elo parameters plus map-specific shrinkage control."""

    map_prior_games: float = 20.0


@dataclass(frozen=True)
class TeamMapEloEvent:
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
    pre_global_elo: float
    pre_map_elo: float
    pre_effective_elo: float
    elo_delta: float
    post_global_elo: float
    post_map_elo: float
    post_effective_elo: float
    map_games_played_pre: int
    map_blend_weight: float
    k_factor: float
    scale_factor: float
    initial_elo: float
    map_prior_games: float


class TeamMapSpecificEloCalculator(MapSpecificMixin, TeamEloCalculator):
    """Stateful map-by-map calculator blending map-specific and global Elo."""

    def __init__(
        self,
        params: MapSpecificEloParameters,
        *,
        lookback_days: int | None = None,
        as_of_time: datetime | None = None,
    ) -> None:
        super().__init__(
            params=params,
            lookback_days=lookback_days,
            as_of_time=as_of_time,
        )
        self.params = params
        self._map_ratings: dict[tuple[int, str], float] = {}
        self._map_games_played = {}
        self._map_last_event_times = {}

    def _get_map_rating(self, *, team_id: int, map_name: str) -> float:
        key = self._map_key(team_id=team_id, map_name=map_name)
        return self._map_ratings.get(key, self.params.initial_elo)

    def _apply_map_inactivity_decay(self, *, team_id: int, map_name: str, event_time: datetime) -> float:
        rating = self._get_map_rating(team_id=team_id, map_name=map_name)
        if self._inactivity_decay_lambda <= 0.0:
            return rating

        key = self._map_key(team_id=team_id, map_name=map_name)
        last_event_time = self._map_last_event_times.get(key)
        if last_event_time is None:
            return rating

        inactive_days = (event_time - last_event_time).total_seconds() / 86_400.0
        if inactive_days <= 0.0:
            return rating

        decay_factor = pow(2.0, -inactive_days / self.params.inactivity_half_life_days)
        return self.params.initial_elo + ((rating - self.params.initial_elo) * decay_factor)

    def process_map(self, map_result: TeamMapResult) -> tuple[TeamMapEloEvent, TeamMapEloEvent]:
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

        team1_global_pre = self._apply_inactivity_decay(
            team_id=map_result.team1_id,
            event_time=map_result.event_time,
        )
        team2_global_pre = self._apply_inactivity_decay(
            team_id=map_result.team2_id,
            event_time=map_result.event_time,
        )
        team1_map_pre = self._apply_map_inactivity_decay(
            team_id=map_result.team1_id,
            map_name=map_name,
            event_time=map_result.event_time,
        )
        team2_map_pre = self._apply_map_inactivity_decay(
            team_id=map_result.team2_id,
            map_name=map_name,
            event_time=map_result.event_time,
        )

        team1_map_games_pre = self._get_map_games_played(team_id=map_result.team1_id, map_name=map_name)
        team2_map_games_pre = self._get_map_games_played(team_id=map_result.team2_id, map_name=map_name)
        team1_blend_weight = self._map_blend_weight(map_games_played=team1_map_games_pre)
        team2_blend_weight = self._map_blend_weight(map_games_played=team2_map_games_pre)

        team1_effective_pre = (
            (team1_blend_weight * team1_map_pre)
            + ((1.0 - team1_blend_weight) * team1_global_pre)
        )
        team2_effective_pre = (
            (team2_blend_weight * team2_map_pre)
            + ((1.0 - team2_blend_weight) * team2_global_pre)
        )

        team1_expected = calculate_expected_score(
            rating=team1_effective_pre,
            opponent_rating=team2_effective_pre,
            scale_factor=self.params.scale_factor,
        )
        team2_expected = 1.0 - team1_expected

        team1_actual = 1.0 if map_result.winner_id == map_result.team1_id else 0.0
        team2_actual = 1.0 - team1_actual

        winner_pre_elo = team1_effective_pre if team1_actual == 1.0 else team2_effective_pre
        loser_pre_elo = team2_effective_pre if team1_actual == 1.0 else team1_effective_pre
        winner_expected_score = team1_expected if team1_actual == 1.0 else team2_expected
        effective_k_multiplier = self._winner_outcome_multiplier(
            winner_pre_elo=winner_pre_elo,
            loser_pre_elo=loser_pre_elo,
        )
        effective_k = (
            self.params.k_factor
            * self._format_multiplier(map_result.match_format)
            * effective_k_multiplier
            * self._opponent_strength_multiplier(winner_expected_score=winner_expected_score)
            * (self.params.lan_multiplier if map_result.is_lan else 1.0)
            * self._round_domination_multiplier(map_result)
            * self._kd_ratio_domination_multiplier(map_result)
            * self._recency_multiplier(map_result.event_time)
        )

        team1_delta = effective_k * (team1_actual - team1_expected)
        team2_delta = -team1_delta

        team1_global_post = team1_global_pre + team1_delta
        team2_global_post = team2_global_pre + team2_delta
        team1_map_post = team1_map_pre + team1_delta
        team2_map_post = team2_map_pre + team2_delta

        self._ratings[map_result.team1_id] = team1_global_post
        self._ratings[map_result.team2_id] = team2_global_post
        self._last_event_times[map_result.team1_id] = map_result.event_time
        self._last_event_times[map_result.team2_id] = map_result.event_time

        key1 = self._map_key(team_id=map_result.team1_id, map_name=map_name)
        key2 = self._map_key(team_id=map_result.team2_id, map_name=map_name)
        self._map_ratings[key1] = team1_map_post
        self._map_ratings[key2] = team2_map_post
        self._record_map_games_played(
            team1_id=map_result.team1_id,
            team2_id=map_result.team2_id,
            map_name=map_name,
            team1_games_pre=team1_map_games_pre,
            team2_games_pre=team2_map_games_pre,
            event_time=map_result.event_time,
        )

        team1_effective_post = (
            (team1_blend_weight * team1_map_post)
            + ((1.0 - team1_blend_weight) * team1_global_post)
        )
        team2_effective_post = (
            (team2_blend_weight * team2_map_post)
            + ((1.0 - team2_blend_weight) * team2_global_post)
        )

        team1_event = TeamMapEloEvent(
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
            pre_global_elo=team1_global_pre,
            pre_map_elo=team1_map_pre,
            pre_effective_elo=team1_effective_pre,
            elo_delta=team1_delta,
            post_global_elo=team1_global_post,
            post_map_elo=team1_map_post,
            post_effective_elo=team1_effective_post,
            map_games_played_pre=team1_map_games_pre,
            map_blend_weight=team1_blend_weight,
            k_factor=effective_k,
            scale_factor=self.params.scale_factor,
            initial_elo=self.params.initial_elo,
            map_prior_games=self.params.map_prior_games,
        )
        team2_event = TeamMapEloEvent(
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
            pre_global_elo=team2_global_pre,
            pre_map_elo=team2_map_pre,
            pre_effective_elo=team2_effective_pre,
            elo_delta=team2_delta,
            post_global_elo=team2_global_post,
            post_map_elo=team2_map_post,
            post_effective_elo=team2_effective_post,
            map_games_played_pre=team2_map_games_pre,
            map_blend_weight=team2_blend_weight,
            k_factor=effective_k,
            scale_factor=self.params.scale_factor,
            initial_elo=self.params.initial_elo,
            map_prior_games=self.params.map_prior_games,
        )
        return team1_event, team2_event
