"""Player-level OpenSkill logic (Plackett-Luce model)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.ratings.common import PlayerMapResult
from domain.ratings.openskill.calculator import OpenSkillParameters, TeamOpenSkillCalculator
from domain.ratings.player_mixin import PlayerCalculatorMixin


@dataclass(frozen=True)
class PlayerOpenSkillEvent:
    player_id: int
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


class PlayerOpenSkillCalculator(PlayerCalculatorMixin, TeamOpenSkillCalculator):
    """Stateful map-by-map player OpenSkill calculator."""

    def __init__(self, params: OpenSkillParameters) -> None:
        super().__init__(params=params)

    def process_map(self, map_result: PlayerMapResult) -> list[PlayerOpenSkillEvent]:
        self._validate_player_map(map_result)

        team1_pre = [self._get_or_create_rating(player.player_id) for player in map_result.team1_players]
        team2_pre = [self._get_or_create_rating(player.player_id) for player in map_result.team2_players]

        predicted = self._model.predict_win([team1_pre, team2_pre])
        team1_expected = float(predicted[0])
        team2_expected = float(predicted[1])

        team1_actual, team2_actual = self._player_map_outcome(map_result)
        ranks = [1, 2] if team1_actual == 1.0 else [2, 1]

        updated = self._model.rate(
            [team1_pre, team2_pre],
            ranks=ranks,
        )
        team1_post = updated[0]
        team2_post = updated[1]

        events: list[PlayerOpenSkillEvent] = []

        for index, participant in enumerate(map_result.team1_players):
            player_id = participant.player_id
            pre_rating = team1_pre[index]
            post_rating = team1_post[index]

            pre_mu = float(pre_rating.mu)
            pre_sigma = float(pre_rating.sigma)
            pre_ordinal = float(pre_rating.ordinal(self.params.ordinal_z))
            post_mu = float(post_rating.mu)
            post_sigma = float(post_rating.sigma)
            post_ordinal = float(post_rating.ordinal(self.params.ordinal_z))

            self._ratings[player_id] = post_rating

            events.append(
                PlayerOpenSkillEvent(
                    player_id=player_id,
                    team_id=map_result.team1_id,
                    opponent_team_id=map_result.team2_id,
                    match_id=map_result.match_id,
                    map_id=map_result.map_id,
                    map_number=map_result.map_number,
                    event_time=map_result.event_time,
                    won=bool(team1_actual),
                    actual_score=team1_actual,
                    expected_score=team1_expected,
                    pre_mu=pre_mu,
                    pre_sigma=pre_sigma,
                    pre_ordinal=pre_ordinal,
                    mu_delta=post_mu - pre_mu,
                    sigma_delta=post_sigma - pre_sigma,
                    ordinal_delta=post_ordinal - pre_ordinal,
                    post_mu=post_mu,
                    post_sigma=post_sigma,
                    post_ordinal=post_ordinal,
                    beta=self.params.beta,
                    kappa=self.params.kappa,
                    tau=self.params.tau,
                    limit_sigma=self.params.limit_sigma,
                    balance=self.params.balance,
                    ordinal_z=self.params.ordinal_z,
                    initial_mu=self.params.initial_mu,
                    initial_sigma=self.params.initial_sigma,
                )
            )

        for index, participant in enumerate(map_result.team2_players):
            player_id = participant.player_id
            pre_rating = team2_pre[index]
            post_rating = team2_post[index]

            pre_mu = float(pre_rating.mu)
            pre_sigma = float(pre_rating.sigma)
            pre_ordinal = float(pre_rating.ordinal(self.params.ordinal_z))
            post_mu = float(post_rating.mu)
            post_sigma = float(post_rating.sigma)
            post_ordinal = float(post_rating.ordinal(self.params.ordinal_z))

            self._ratings[player_id] = post_rating

            events.append(
                PlayerOpenSkillEvent(
                    player_id=player_id,
                    team_id=map_result.team2_id,
                    opponent_team_id=map_result.team1_id,
                    match_id=map_result.match_id,
                    map_id=map_result.map_id,
                    map_number=map_result.map_number,
                    event_time=map_result.event_time,
                    won=bool(team2_actual),
                    actual_score=team2_actual,
                    expected_score=team2_expected,
                    pre_mu=pre_mu,
                    pre_sigma=pre_sigma,
                    pre_ordinal=pre_ordinal,
                    mu_delta=post_mu - pre_mu,
                    sigma_delta=post_sigma - pre_sigma,
                    ordinal_delta=post_ordinal - pre_ordinal,
                    post_mu=post_mu,
                    post_sigma=post_sigma,
                    post_ordinal=post_ordinal,
                    beta=self.params.beta,
                    kappa=self.params.kappa,
                    tau=self.params.tau,
                    limit_sigma=self.params.limit_sigma,
                    balance=self.params.balance,
                    ordinal_z=self.params.ordinal_z,
                    initial_mu=self.params.initial_mu,
                    initial_sigma=self.params.initial_sigma,
                )
            )

        return events
