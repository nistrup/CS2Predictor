"""Map-specific team OpenSkill logic with global-rating shrinkage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from domain.ratings.common import TeamMapResult
from domain.ratings.map_specific_mixin import MapSpecificMixin
from domain.ratings.openskill.calculator import OpenSkillParameters, TeamOpenSkillCalculator


@dataclass(frozen=True)
class MapSpecificOpenSkillParameters(OpenSkillParameters):
    """OpenSkill parameters plus map-specific shrinkage control."""

    map_prior_games: float = 20.0


@dataclass(frozen=True)
class TeamMapOpenSkillEvent:
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
    pre_global_mu: float
    pre_map_mu: float
    pre_effective_mu: float
    pre_global_sigma: float
    pre_map_sigma: float
    pre_effective_sigma: float
    pre_global_ordinal: float
    pre_map_ordinal: float
    pre_effective_ordinal: float
    mu_delta: float
    sigma_delta: float
    ordinal_delta: float
    post_global_mu: float
    post_map_mu: float
    post_effective_mu: float
    post_global_sigma: float
    post_map_sigma: float
    post_effective_sigma: float
    post_global_ordinal: float
    post_map_ordinal: float
    post_effective_ordinal: float
    map_games_played_pre: int
    map_blend_weight: float
    beta: float
    kappa: float
    tau: float
    limit_sigma: bool
    balance: bool
    ordinal_z: float
    initial_mu: float
    initial_sigma: float
    map_prior_games: float


class TeamMapSpecificOpenSkillCalculator(MapSpecificMixin, TeamOpenSkillCalculator):
    """Stateful map-by-map calculator blending map-specific and global OpenSkill state."""

    def __init__(self, params: MapSpecificOpenSkillParameters) -> None:
        super().__init__(params=params)
        self.params = params
        self._map_ratings: dict[tuple[int, str], Any] = {}
        self._map_games_played = {}

    def _create_rating(self, *, name: str, mu: float, sigma: float) -> Any:
        return self._model.rating(
            mu=mu,
            sigma=max(sigma, 1e-9),
            name=name,
        )

    def _get_or_create_map_rating(self, *, team_id: int, map_name: str) -> Any:
        key = self._map_key(team_id=team_id, map_name=map_name)
        existing = self._map_ratings.get(key)
        if existing is not None:
            return existing
        rating = self._create_rating(
            name=f"{team_id}:{map_name}",
            mu=self.params.initial_mu,
            sigma=self.params.initial_sigma,
        )
        self._map_ratings[key] = rating
        return rating

    def process_map(self, map_result: TeamMapResult) -> tuple[TeamMapOpenSkillEvent, TeamMapOpenSkillEvent]:
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

        team1_global_pre = self._get_or_create_rating(map_result.team1_id)
        team2_global_pre = self._get_or_create_rating(map_result.team2_id)
        team1_map_pre = self._get_or_create_map_rating(team_id=map_result.team1_id, map_name=map_name)
        team2_map_pre = self._get_or_create_map_rating(team_id=map_result.team2_id, map_name=map_name)

        team1_map_games_pre = self._get_map_games_played(team_id=map_result.team1_id, map_name=map_name)
        team2_map_games_pre = self._get_map_games_played(team_id=map_result.team2_id, map_name=map_name)
        team1_blend_weight = self._map_blend_weight(map_games_played=team1_map_games_pre)
        team2_blend_weight = self._map_blend_weight(map_games_played=team2_map_games_pre)

        team1_global_pre_mu = float(team1_global_pre.mu)
        team2_global_pre_mu = float(team2_global_pre.mu)
        team1_global_pre_sigma = float(team1_global_pre.sigma)
        team2_global_pre_sigma = float(team2_global_pre.sigma)
        team1_map_pre_mu = float(team1_map_pre.mu)
        team2_map_pre_mu = float(team2_map_pre.mu)
        team1_map_pre_sigma = float(team1_map_pre.sigma)
        team2_map_pre_sigma = float(team2_map_pre.sigma)

        team1_effective_pre_mu = (
            (team1_blend_weight * team1_map_pre_mu)
            + ((1.0 - team1_blend_weight) * team1_global_pre_mu)
        )
        team2_effective_pre_mu = (
            (team2_blend_weight * team2_map_pre_mu)
            + ((1.0 - team2_blend_weight) * team2_global_pre_mu)
        )
        team1_effective_pre_sigma = (
            (team1_blend_weight * team1_map_pre_sigma)
            + ((1.0 - team1_blend_weight) * team1_global_pre_sigma)
        )
        team2_effective_pre_sigma = (
            (team2_blend_weight * team2_map_pre_sigma)
            + ((1.0 - team2_blend_weight) * team2_global_pre_sigma)
        )

        team1_effective_pre = self._create_rating(
            name=f"effective:{map_result.team1_id}",
            mu=team1_effective_pre_mu,
            sigma=team1_effective_pre_sigma,
        )
        team2_effective_pre = self._create_rating(
            name=f"effective:{map_result.team2_id}",
            mu=team2_effective_pre_mu,
            sigma=team2_effective_pre_sigma,
        )

        predicted = self._model.predict_win([[team1_effective_pre], [team2_effective_pre]])
        team1_expected = float(predicted[0])
        team2_expected = float(predicted[1])

        team1_actual = 1.0 if map_result.winner_id == map_result.team1_id else 0.0
        team2_actual = 1.0 - team1_actual
        ranks = [1, 2] if team1_actual == 1.0 else [2, 1]

        updated = self._model.rate(
            [[team1_effective_pre], [team2_effective_pre]],
            ranks=ranks,
        )
        team1_effective_post = updated[0][0]
        team2_effective_post = updated[1][0]

        team1_mu_delta = float(team1_effective_post.mu) - team1_effective_pre_mu
        team2_mu_delta = float(team2_effective_post.mu) - team2_effective_pre_mu
        team1_sigma_delta = float(team1_effective_post.sigma) - team1_effective_pre_sigma
        team2_sigma_delta = float(team2_effective_post.sigma) - team2_effective_pre_sigma
        team1_ordinal_delta = (
            float(team1_effective_post.ordinal(self.params.ordinal_z))
            - float(team1_effective_pre.ordinal(self.params.ordinal_z))
        )
        team2_ordinal_delta = (
            float(team2_effective_post.ordinal(self.params.ordinal_z))
            - float(team2_effective_pre.ordinal(self.params.ordinal_z))
        )

        team1_global_post_mu = team1_global_pre_mu + team1_mu_delta
        team2_global_post_mu = team2_global_pre_mu + team2_mu_delta
        team1_map_post_mu = team1_map_pre_mu + team1_mu_delta
        team2_map_post_mu = team2_map_pre_mu + team2_mu_delta
        team1_global_post_sigma = max(team1_global_pre_sigma + team1_sigma_delta, 1e-9)
        team2_global_post_sigma = max(team2_global_pre_sigma + team2_sigma_delta, 1e-9)
        team1_map_post_sigma = max(team1_map_pre_sigma + team1_sigma_delta, 1e-9)
        team2_map_post_sigma = max(team2_map_pre_sigma + team2_sigma_delta, 1e-9)

        team1_global_post = self._create_rating(
            name=str(map_result.team1_id),
            mu=team1_global_post_mu,
            sigma=team1_global_post_sigma,
        )
        team2_global_post = self._create_rating(
            name=str(map_result.team2_id),
            mu=team2_global_post_mu,
            sigma=team2_global_post_sigma,
        )
        team1_map_post = self._create_rating(
            name=f"{map_result.team1_id}:{map_name}",
            mu=team1_map_post_mu,
            sigma=team1_map_post_sigma,
        )
        team2_map_post = self._create_rating(
            name=f"{map_result.team2_id}:{map_name}",
            mu=team2_map_post_mu,
            sigma=team2_map_post_sigma,
        )

        self._ratings[map_result.team1_id] = team1_global_post
        self._ratings[map_result.team2_id] = team2_global_post
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

        team1_effective_post_mu = (
            (team1_blend_weight * team1_map_post_mu)
            + ((1.0 - team1_blend_weight) * team1_global_post_mu)
        )
        team2_effective_post_mu = (
            (team2_blend_weight * team2_map_post_mu)
            + ((1.0 - team2_blend_weight) * team2_global_post_mu)
        )
        team1_effective_post_sigma = (
            (team1_blend_weight * team1_map_post_sigma)
            + ((1.0 - team1_blend_weight) * team1_global_post_sigma)
        )
        team2_effective_post_sigma = (
            (team2_blend_weight * team2_map_post_sigma)
            + ((1.0 - team2_blend_weight) * team2_global_post_sigma)
        )

        team1_effective_post_rating = self._create_rating(
            name=f"effective_post:{map_result.team1_id}",
            mu=team1_effective_post_mu,
            sigma=team1_effective_post_sigma,
        )
        team2_effective_post_rating = self._create_rating(
            name=f"effective_post:{map_result.team2_id}",
            mu=team2_effective_post_mu,
            sigma=team2_effective_post_sigma,
        )

        team1_event = TeamMapOpenSkillEvent(
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
            pre_global_mu=team1_global_pre_mu,
            pre_map_mu=team1_map_pre_mu,
            pre_effective_mu=team1_effective_pre_mu,
            pre_global_sigma=team1_global_pre_sigma,
            pre_map_sigma=team1_map_pre_sigma,
            pre_effective_sigma=team1_effective_pre_sigma,
            pre_global_ordinal=float(team1_global_pre.ordinal(self.params.ordinal_z)),
            pre_map_ordinal=float(team1_map_pre.ordinal(self.params.ordinal_z)),
            pre_effective_ordinal=float(team1_effective_pre.ordinal(self.params.ordinal_z)),
            mu_delta=team1_mu_delta,
            sigma_delta=team1_sigma_delta,
            ordinal_delta=team1_ordinal_delta,
            post_global_mu=team1_global_post_mu,
            post_map_mu=team1_map_post_mu,
            post_effective_mu=team1_effective_post_mu,
            post_global_sigma=team1_global_post_sigma,
            post_map_sigma=team1_map_post_sigma,
            post_effective_sigma=team1_effective_post_sigma,
            post_global_ordinal=float(team1_global_post.ordinal(self.params.ordinal_z)),
            post_map_ordinal=float(team1_map_post.ordinal(self.params.ordinal_z)),
            post_effective_ordinal=float(team1_effective_post_rating.ordinal(self.params.ordinal_z)),
            map_games_played_pre=team1_map_games_pre,
            map_blend_weight=team1_blend_weight,
            beta=self.params.beta,
            kappa=self.params.kappa,
            tau=self.params.tau,
            limit_sigma=self.params.limit_sigma,
            balance=self.params.balance,
            ordinal_z=self.params.ordinal_z,
            initial_mu=self.params.initial_mu,
            initial_sigma=self.params.initial_sigma,
            map_prior_games=self.params.map_prior_games,
        )
        team2_event = TeamMapOpenSkillEvent(
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
            pre_global_mu=team2_global_pre_mu,
            pre_map_mu=team2_map_pre_mu,
            pre_effective_mu=team2_effective_pre_mu,
            pre_global_sigma=team2_global_pre_sigma,
            pre_map_sigma=team2_map_pre_sigma,
            pre_effective_sigma=team2_effective_pre_sigma,
            pre_global_ordinal=float(team2_global_pre.ordinal(self.params.ordinal_z)),
            pre_map_ordinal=float(team2_map_pre.ordinal(self.params.ordinal_z)),
            pre_effective_ordinal=float(team2_effective_pre.ordinal(self.params.ordinal_z)),
            mu_delta=team2_mu_delta,
            sigma_delta=team2_sigma_delta,
            ordinal_delta=team2_ordinal_delta,
            post_global_mu=team2_global_post_mu,
            post_map_mu=team2_map_post_mu,
            post_effective_mu=team2_effective_post_mu,
            post_global_sigma=team2_global_post_sigma,
            post_map_sigma=team2_map_post_sigma,
            post_effective_sigma=team2_effective_post_sigma,
            post_global_ordinal=float(team2_global_post.ordinal(self.params.ordinal_z)),
            post_map_ordinal=float(team2_map_post.ordinal(self.params.ordinal_z)),
            post_effective_ordinal=float(team2_effective_post_rating.ordinal(self.params.ordinal_z)),
            map_games_played_pre=team2_map_games_pre,
            map_blend_weight=team2_blend_weight,
            beta=self.params.beta,
            kappa=self.params.kappa,
            tau=self.params.tau,
            limit_sigma=self.params.limit_sigma,
            balance=self.params.balance,
            ordinal_z=self.params.ordinal_z,
            initial_mu=self.params.initial_mu,
            initial_sigma=self.params.initial_sigma,
            map_prior_games=self.params.map_prior_games,
        )
        return team1_event, team2_event
