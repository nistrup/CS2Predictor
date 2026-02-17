"""Team-level Elo logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from math import exp, log

from domain.ratings.common import TeamMapResult


@dataclass(frozen=True)
class EloParameters:
    initial_elo: float = 1500.0
    k_factor: float = 20.0
    scale_factor: float = 400.0
    even_multiplier: float = 1.0
    favored_multiplier: float = 1.0
    unfavored_multiplier: float = 1.0
    opponent_strength_weight: float = 1.0
    lan_multiplier: float = 1.0
    round_domination_multiplier: float = 1.0
    kd_ratio_domination_multiplier: float = 1.0
    recency_min_multiplier: float = 1.0
    inactivity_half_life_days: float = 0.0
    bo1_match_multiplier: float = 1.0
    bo3_match_multiplier: float = 1.0
    bo5_match_multiplier: float = 1.0


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

    def __init__(
        self,
        params: EloParameters,
        *,
        lookback_days: int | None = None,
        as_of_time: datetime | None = None,
    ) -> None:
        self.params = params
        self.lookback_days = lookback_days if lookback_days is not None and lookback_days > 0 else None
        self.as_of_time = as_of_time or datetime.now(UTC).replace(tzinfo=None)
        self._ratings: dict[int, float] = {}
        self._last_event_times: dict[int, datetime] = {}
        if self.params.inactivity_half_life_days > 0.0:
            self._inactivity_decay_lambda = log(2.0) / self.params.inactivity_half_life_days
        else:
            self._inactivity_decay_lambda = 0.0

    def get_rating(self, team_id: int) -> float:
        return self._ratings.get(team_id, self.params.initial_elo)

    def tracked_team_count(self) -> int:
        return len(self._ratings)

    def tracked_entity_count(self) -> int:
        """Subject-agnostic alias for protocol compatibility."""
        return self.tracked_team_count()

    def ratings(self) -> dict[int, float]:
        """Return a snapshot of current team ratings."""
        return dict(self._ratings)

    def _apply_inactivity_decay(self, *, team_id: int, event_time: datetime) -> float:
        rating = self.get_rating(team_id)
        if self._inactivity_decay_lambda <= 0.0:
            return rating

        last_event_time = self._last_event_times.get(team_id)
        if last_event_time is None:
            return rating

        inactive_days = (event_time - last_event_time).total_seconds() / 86_400.0
        if inactive_days <= 0.0:
            return rating

        decay_factor = exp(-self._inactivity_decay_lambda * inactive_days)
        return self.params.initial_elo + ((rating - self.params.initial_elo) * decay_factor)

    def _format_multiplier(self, match_format: str | None) -> float:
        if match_format == "BO5":
            return self.params.bo5_match_multiplier
        if match_format == "BO3":
            return self.params.bo3_match_multiplier
        if match_format == "BO1":
            return self.params.bo1_match_multiplier
        return 1.0

    def _winner_outcome_multiplier(self, *, winner_pre_elo: float, loser_pre_elo: float) -> float:
        if winner_pre_elo > loser_pre_elo:
            return self.params.favored_multiplier
        if winner_pre_elo < loser_pre_elo:
            return self.params.unfavored_multiplier
        return self.params.even_multiplier

    def _opponent_strength_multiplier(self, *, winner_expected_score: float) -> float:
        if self.params.opponent_strength_weight == 1.0:
            return 1.0

        # winner_expected_score < 0.5 means the winner beat a stronger opponent.
        strength_index = max(-1.0, min((0.5 - winner_expected_score) / 0.5, 1.0))
        return self.params.opponent_strength_weight**strength_index

    def _round_domination_multiplier(self, map_result: TeamMapResult) -> float:
        if self.params.round_domination_multiplier == 1.0:
            return 1.0
        if map_result.team1_score is None or map_result.team2_score is None:
            return 1.0

        team1_score = max(map_result.team1_score, 0)
        team2_score = max(map_result.team2_score, 0)
        total_rounds = team1_score + team2_score
        if total_rounds <= 0:
            return 1.0

        winner_score = team1_score if map_result.winner_id == map_result.team1_id else team2_score
        winner_share = winner_score / total_rounds
        domination_index = max(0.0, min((winner_share - 0.5) / 0.5, 1.0))
        return 1.0 + ((self.params.round_domination_multiplier - 1.0) * domination_index)

    def _kd_ratio_domination_multiplier(self, map_result: TeamMapResult) -> float:
        if self.params.kd_ratio_domination_multiplier == 1.0:
            return 1.0
        if map_result.team1_kd_ratio is None or map_result.team2_kd_ratio is None:
            return 1.0

        winner_kd_ratio = (
            map_result.team1_kd_ratio
            if map_result.winner_id == map_result.team1_id
            else map_result.team2_kd_ratio
        )
        loser_kd_ratio = (
            map_result.team2_kd_ratio
            if map_result.winner_id == map_result.team1_id
            else map_result.team1_kd_ratio
        )

        if winner_kd_ratio <= 0.0 or loser_kd_ratio <= 0.0:
            return 1.0

        kd_ratio_gap = max(0.0, winner_kd_ratio - loser_kd_ratio)
        domination_index = min(kd_ratio_gap, 1.0)
        return 1.0 + ((self.params.kd_ratio_domination_multiplier - 1.0) * domination_index)

    def _recency_multiplier(self, event_time: datetime) -> float:
        if self.lookback_days is None or self.params.recency_min_multiplier == 1.0:
            return 1.0

        age_days = (self.as_of_time - event_time).total_seconds() / 86_400.0
        age_fraction = max(0.0, min(age_days / float(self.lookback_days), 1.0))
        return 1.0 - ((1.0 - self.params.recency_min_multiplier) * age_fraction)

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

        team1_pre = self._apply_inactivity_decay(team_id=map_result.team1_id, event_time=map_result.event_time)
        team2_pre = self._apply_inactivity_decay(team_id=map_result.team2_id, event_time=map_result.event_time)

        team1_expected = calculate_expected_score(
            rating=team1_pre,
            opponent_rating=team2_pre,
            scale_factor=self.params.scale_factor,
        )
        team2_expected = 1.0 - team1_expected

        team1_actual = 1.0 if map_result.winner_id == map_result.team1_id else 0.0
        team2_actual = 1.0 - team1_actual

        winner_pre_elo = team1_pre if team1_actual == 1.0 else team2_pre
        loser_pre_elo = team2_pre if team1_actual == 1.0 else team1_pre
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

        team1_post = team1_pre + team1_delta
        team2_post = team2_pre + team2_delta

        self._ratings[map_result.team1_id] = team1_post
        self._ratings[map_result.team2_id] = team2_post
        self._last_event_times[map_result.team1_id] = map_result.event_time
        self._last_event_times[map_result.team2_id] = map_result.event_time

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
            k_factor=effective_k,
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
            k_factor=effective_k,
            scale_factor=self.params.scale_factor,
            initial_elo=self.params.initial_elo,
        )
        return team1_event, team2_event
