"""Match-level team OpenSkill logic (Plackett-Luce model)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.ratings.common import TeamMatchResult
from domain.ratings.match_adapter import MatchAdapterMixin
from domain.ratings.openskill.calculator import OpenSkillParameters, TeamOpenSkillCalculator


@dataclass(frozen=True)
class TeamMatchOpenSkillEvent:
    team_id: int
    opponent_team_id: int
    match_id: int
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
    team_maps_won: int
    opponent_maps_won: int
    beta: float
    kappa: float
    tau: float
    limit_sigma: bool
    balance: bool
    ordinal_z: float
    initial_mu: float
    initial_sigma: float


class TeamMatchOpenSkillCalculator(MatchAdapterMixin, TeamOpenSkillCalculator):
    """Stateful match-by-match team OpenSkill calculator."""

    def __init__(self, params: OpenSkillParameters) -> None:
        super().__init__(params=params)

    def process_match(
        self,
        match_result: TeamMatchResult,
    ) -> tuple[TeamMatchOpenSkillEvent, TeamMatchOpenSkillEvent]:
        self._validate_team_match(match_result)

        team1_pre = self._get_or_create_rating(match_result.team1_id)
        team2_pre = self._get_or_create_rating(match_result.team2_id)

        predicted = self._model.predict_win([[team1_pre], [team2_pre]])
        team1_expected = float(predicted[0])
        team2_expected = float(predicted[1])

        team1_actual, team2_actual, team1_maps_won, team2_maps_won = self._match_outcome(match_result)
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

        self._ratings[match_result.team1_id] = team1_post
        self._ratings[match_result.team2_id] = team2_post

        team1_event = TeamMatchOpenSkillEvent(
            team_id=match_result.team1_id,
            opponent_team_id=match_result.team2_id,
            match_id=match_result.match_id,
            event_time=match_result.event_time,
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
            team_maps_won=team1_maps_won,
            opponent_maps_won=team2_maps_won,
            beta=self.params.beta,
            kappa=self.params.kappa,
            tau=self.params.tau,
            limit_sigma=self.params.limit_sigma,
            balance=self.params.balance,
            ordinal_z=self.params.ordinal_z,
            initial_mu=self.params.initial_mu,
            initial_sigma=self.params.initial_sigma,
        )
        team2_event = TeamMatchOpenSkillEvent(
            team_id=match_result.team2_id,
            opponent_team_id=match_result.team1_id,
            match_id=match_result.match_id,
            event_time=match_result.event_time,
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
            team_maps_won=team2_maps_won,
            opponent_maps_won=team1_maps_won,
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
