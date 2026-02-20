"""Team-level OpenSkill logic (Plackett-Luce model)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from openskill.models import PlackettLuce

from domain.common import TeamMapResult


@dataclass(frozen=True)
class OpenSkillParameters:
    initial_mu: float = 25.0
    initial_sigma: float = 25.0 / 3.0
    beta: float = 25.0 / 6.0
    kappa: float = 0.0001
    tau: float = 25.0 / 300.0
    limit_sigma: bool = False
    balance: bool = False
    ordinal_z: float = 3.0


@dataclass(frozen=True)
class TeamOpenSkillEvent:
    team_id: int
    opponent_team_id: int
    match_id: int
    map_id: int
    map_number: int
    event_time: datetime
    won: bool
    actual_score: float
    expected_score: float
    pre_mu: float
    pre_sigma: float
    pre_ordinal: float
    mu_delta: float
    sigma_delta: float
    ordinal_delta: float
    post_mu: float
    post_sigma: float
    post_ordinal: float
    beta: float
    kappa: float
    tau: float
    limit_sigma: bool
    balance: bool
    ordinal_z: float
    initial_mu: float
    initial_sigma: float


class TeamOpenSkillCalculator:
    """Stateful map-by-map team OpenSkill calculator."""

    def __init__(self, params: OpenSkillParameters) -> None:
        self.params = params
        self._model = PlackettLuce(
            mu=self.params.initial_mu,
            sigma=self.params.initial_sigma,
            beta=self.params.beta,
            kappa=self.params.kappa,
            tau=self.params.tau,
            limit_sigma=self.params.limit_sigma,
            balance=self.params.balance,
        )
        self._ratings: dict[int, object] = {}

    def _get_or_create_rating(self, team_id: int):
        existing = self._ratings.get(team_id)
        if existing is not None:
            return existing
        rating = self._model.rating(
            mu=self.params.initial_mu,
            sigma=self.params.initial_sigma,
            name=str(team_id),
        )
        self._ratings[team_id] = rating
        return rating

    def get_mu(self, team_id: int) -> float:
        rating = self._get_or_create_rating(team_id)
        return float(rating.mu)

    def get_sigma(self, team_id: int) -> float:
        rating = self._get_or_create_rating(team_id)
        return float(rating.sigma)

    def get_ordinal(self, team_id: int) -> float:
        rating = self._get_or_create_rating(team_id)
        return float(rating.ordinal(self.params.ordinal_z))

    def tracked_team_count(self) -> int:
        return len(self._ratings)

    def tracked_entity_count(self) -> int:
        """Subject-agnostic alias for protocol compatibility."""
        return self.tracked_team_count()

    def ratings(self) -> dict[int, tuple[float, float, float]]:
        """Return a snapshot of current team ratings."""
        return {
            team_id: (
                float(rating.mu),
                float(rating.sigma),
                float(rating.ordinal(self.params.ordinal_z)),
            )
            for team_id, rating in self._ratings.items()
        }

    def process_map(self, map_result: TeamMapResult) -> tuple[TeamOpenSkillEvent, TeamOpenSkillEvent]:
        if map_result.team1_id == map_result.team2_id:
            raise ValueError(
                f"map_id={map_result.map_id} has identical teams ({map_result.team1_id})"
            )
        if map_result.winner_id not in (map_result.team1_id, map_result.team2_id):
            raise ValueError(
                f"winner_id={map_result.winner_id} does not belong to map teams "
                f"{map_result.team1_id}/{map_result.team2_id} for map_id={map_result.map_id}"
            )

        team1_pre = self._get_or_create_rating(map_result.team1_id)
        team2_pre = self._get_or_create_rating(map_result.team2_id)

        predicted = self._model.predict_win([[team1_pre], [team2_pre]])
        team1_expected = float(predicted[0])
        team2_expected = float(predicted[1])

        team1_actual = 1.0 if map_result.winner_id == map_result.team1_id else 0.0
        team2_actual = 1.0 - team1_actual
        ranks = [1, 2] if team1_actual == 1.0 else [2, 1]

        team1_pre_mu = float(team1_pre.mu)
        team2_pre_mu = float(team2_pre.mu)
        team1_pre_sigma = float(team1_pre.sigma)
        team2_pre_sigma = float(team2_pre.sigma)
        team1_pre_ordinal = float(team1_pre.ordinal(self.params.ordinal_z))
        team2_pre_ordinal = float(team2_pre.ordinal(self.params.ordinal_z))

        updated = self._model.rate(
            [[team1_pre], [team2_pre]],
            ranks=ranks,
        )
        team1_post = updated[0][0]
        team2_post = updated[1][0]

        team1_post_mu = float(team1_post.mu)
        team2_post_mu = float(team2_post.mu)
        team1_post_sigma = float(team1_post.sigma)
        team2_post_sigma = float(team2_post.sigma)
        team1_post_ordinal = float(team1_post.ordinal(self.params.ordinal_z))
        team2_post_ordinal = float(team2_post.ordinal(self.params.ordinal_z))

        self._ratings[map_result.team1_id] = team1_post
        self._ratings[map_result.team2_id] = team2_post

        team1_event = TeamOpenSkillEvent(
            team_id=map_result.team1_id,
            opponent_team_id=map_result.team2_id,
            match_id=map_result.match_id,
            map_id=map_result.map_id,
            map_number=map_result.map_number,
            event_time=map_result.event_time,
            won=bool(team1_actual),
            actual_score=team1_actual,
            expected_score=team1_expected,
            pre_mu=team1_pre_mu,
            pre_sigma=team1_pre_sigma,
            pre_ordinal=team1_pre_ordinal,
            mu_delta=team1_post_mu - team1_pre_mu,
            sigma_delta=team1_post_sigma - team1_pre_sigma,
            ordinal_delta=team1_post_ordinal - team1_pre_ordinal,
            post_mu=team1_post_mu,
            post_sigma=team1_post_sigma,
            post_ordinal=team1_post_ordinal,
            beta=self.params.beta,
            kappa=self.params.kappa,
            tau=self.params.tau,
            limit_sigma=self.params.limit_sigma,
            balance=self.params.balance,
            ordinal_z=self.params.ordinal_z,
            initial_mu=self.params.initial_mu,
            initial_sigma=self.params.initial_sigma,
        )
        team2_event = TeamOpenSkillEvent(
            team_id=map_result.team2_id,
            opponent_team_id=map_result.team1_id,
            match_id=map_result.match_id,
            map_id=map_result.map_id,
            map_number=map_result.map_number,
            event_time=map_result.event_time,
            won=bool(team2_actual),
            actual_score=team2_actual,
            expected_score=team2_expected,
            pre_mu=team2_pre_mu,
            pre_sigma=team2_pre_sigma,
            pre_ordinal=team2_pre_ordinal,
            mu_delta=team2_post_mu - team2_pre_mu,
            sigma_delta=team2_post_sigma - team2_pre_sigma,
            ordinal_delta=team2_post_ordinal - team2_pre_ordinal,
            post_mu=team2_post_mu,
            post_sigma=team2_post_sigma,
            post_ordinal=team2_post_ordinal,
            beta=self.params.beta,
            kappa=self.params.kappa,
            tau=self.params.tau,
            limit_sigma=self.params.limit_sigma,
            balance=self.params.balance,
            ordinal_z=self.params.ordinal_z,
            initial_mu=self.params.initial_mu,
            initial_sigma=self.params.initial_sigma,
        )
        return team1_event, team2_event
