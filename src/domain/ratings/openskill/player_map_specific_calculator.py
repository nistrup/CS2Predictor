"""Map-specific player OpenSkill logic with global-rating shrinkage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from domain.ratings.common import PlayerMapResult
from domain.ratings.openskill.map_specific_calculator import MapSpecificOpenSkillParameters
from domain.ratings.openskill.player_calculator import PlayerOpenSkillCalculator


@dataclass(frozen=True)
class PlayerMapOpenSkillEvent:
    player_id: int
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


class PlayerMapSpecificOpenSkillCalculator(PlayerOpenSkillCalculator):
    """Stateful map-by-map calculator blending map-specific and global player OpenSkill state."""

    def __init__(self, params: MapSpecificOpenSkillParameters) -> None:
        super().__init__(params=params)
        self.params = params
        self._map_ratings: dict[tuple[int, str], Any] = {}
        self._map_games_played: dict[tuple[int, str], int] = {}

    def _normalize_map_name(self, map_name: str | None) -> str:
        normalized = (map_name or "").strip().upper()
        return normalized or "UNKNOWN"

    def _map_key(self, *, player_id: int, map_name: str) -> tuple[int, str]:
        return (player_id, map_name)

    def _create_rating(self, *, name: str, mu: float, sigma: float) -> Any:
        return self._model.rating(
            mu=mu,
            sigma=max(sigma, 1e-9),
            name=name,
        )

    def _get_or_create_map_rating(self, *, player_id: int, map_name: str) -> Any:
        key = self._map_key(player_id=player_id, map_name=map_name)
        existing = self._map_ratings.get(key)
        if existing is not None:
            return existing
        rating = self._create_rating(
            name=f"{player_id}:{map_name}",
            mu=self.params.initial_mu,
            sigma=self.params.initial_sigma,
        )
        self._map_ratings[key] = rating
        return rating

    def _get_map_games_played(self, *, player_id: int, map_name: str) -> int:
        key = self._map_key(player_id=player_id, map_name=map_name)
        return self._map_games_played.get(key, 0)

    def _map_blend_weight(self, *, map_games_played: int) -> float:
        if self.params.map_prior_games <= 0.0:
            return 1.0
        return map_games_played / (map_games_played + self.params.map_prior_games)

    def process_map(self, map_result: PlayerMapResult) -> list[PlayerMapOpenSkillEvent]:
        self._validate_player_map(map_result)

        map_name = self._normalize_map_name(map_result.map_name)

        def side_pre_state(players, team_id: int) -> dict[int, dict[str, Any]]:
            state: dict[int, dict[str, Any]] = {}
            for participant in players:
                player_id = participant.player_id
                global_pre = self._get_or_create_rating(player_id)
                map_pre = self._get_or_create_map_rating(player_id=player_id, map_name=map_name)

                map_games_pre = self._get_map_games_played(player_id=player_id, map_name=map_name)
                blend_weight = self._map_blend_weight(map_games_played=map_games_pre)

                global_pre_mu = float(global_pre.mu)
                global_pre_sigma = float(global_pre.sigma)
                map_pre_mu = float(map_pre.mu)
                map_pre_sigma = float(map_pre.sigma)

                effective_pre_mu = (blend_weight * map_pre_mu) + ((1.0 - blend_weight) * global_pre_mu)
                effective_pre_sigma = (blend_weight * map_pre_sigma) + ((1.0 - blend_weight) * global_pre_sigma)
                effective_pre = self._create_rating(
                    name=f"effective:{player_id}:{map_name}",
                    mu=effective_pre_mu,
                    sigma=effective_pre_sigma,
                )

                state[player_id] = {
                    "team_id": team_id,
                    "global_pre": global_pre,
                    "map_pre": map_pre,
                    "map_games_pre": map_games_pre,
                    "blend_weight": blend_weight,
                    "effective_pre": effective_pre,
                    "global_pre_mu": global_pre_mu,
                    "global_pre_sigma": global_pre_sigma,
                    "map_pre_mu": map_pre_mu,
                    "map_pre_sigma": map_pre_sigma,
                    "effective_pre_mu": effective_pre_mu,
                    "effective_pre_sigma": effective_pre_sigma,
                }
            return state

        team1_state = side_pre_state(map_result.team1_players, map_result.team1_id)
        team2_state = side_pre_state(map_result.team2_players, map_result.team2_id)

        team1_effective_pre = [team1_state[player.player_id]["effective_pre"] for player in map_result.team1_players]
        team2_effective_pre = [team2_state[player.player_id]["effective_pre"] for player in map_result.team2_players]

        predicted = self._model.predict_win([team1_effective_pre, team2_effective_pre])
        team1_expected = float(predicted[0])
        team2_expected = float(predicted[1])

        team1_actual, team2_actual = self._player_map_outcome(map_result)
        ranks = [1, 2] if team1_actual == 1.0 else [2, 1]

        updated = self._model.rate(
            [team1_effective_pre, team2_effective_pre],
            ranks=ranks,
        )
        team1_effective_post = updated[0]
        team2_effective_post = updated[1]

        events: list[PlayerMapOpenSkillEvent] = []

        def process_side(
            *,
            players,
            side_state: dict[int, dict[str, Any]],
            effective_post,
            team_id: int,
            opponent_team_id: int,
            actual: float,
            expected: float,
        ) -> None:
            for index, participant in enumerate(players):
                player_id = participant.player_id
                values = side_state[player_id]
                global_pre = values["global_pre"]
                map_pre = values["map_pre"]
                effective_pre = values["effective_pre"]
                blend_weight = float(values["blend_weight"])
                map_games_pre = int(values["map_games_pre"])

                global_pre_mu = float(values["global_pre_mu"])
                global_pre_sigma = float(values["global_pre_sigma"])
                map_pre_mu = float(values["map_pre_mu"])
                map_pre_sigma = float(values["map_pre_sigma"])
                effective_pre_mu = float(values["effective_pre_mu"])
                effective_pre_sigma = float(values["effective_pre_sigma"])

                effective_post_rating = effective_post[index]
                effective_post_mu = float(effective_post_rating.mu)
                effective_post_sigma = float(effective_post_rating.sigma)

                mu_delta = effective_post_mu - effective_pre_mu
                sigma_delta = effective_post_sigma - effective_pre_sigma
                ordinal_delta = (
                    float(effective_post_rating.ordinal(self.params.ordinal_z))
                    - float(effective_pre.ordinal(self.params.ordinal_z))
                )

                global_post_mu = global_pre_mu + mu_delta
                map_post_mu = map_pre_mu + mu_delta
                global_post_sigma = max(global_pre_sigma + sigma_delta, 1e-9)
                map_post_sigma = max(map_pre_sigma + sigma_delta, 1e-9)

                global_post = self._create_rating(
                    name=str(player_id),
                    mu=global_post_mu,
                    sigma=global_post_sigma,
                )
                map_post = self._create_rating(
                    name=f"{player_id}:{map_name}",
                    mu=map_post_mu,
                    sigma=map_post_sigma,
                )

                self._ratings[player_id] = global_post
                key = self._map_key(player_id=player_id, map_name=map_name)
                self._map_ratings[key] = map_post
                self._map_games_played[key] = map_games_pre + 1

                effective_post_mu_blended = (blend_weight * map_post_mu) + ((1.0 - blend_weight) * global_post_mu)
                effective_post_sigma_blended = (blend_weight * map_post_sigma) + ((1.0 - blend_weight) * global_post_sigma)
                effective_post_blended = self._create_rating(
                    name=f"effective_post:{player_id}:{map_name}",
                    mu=effective_post_mu_blended,
                    sigma=effective_post_sigma_blended,
                )

                events.append(
                    PlayerMapOpenSkillEvent(
                        player_id=player_id,
                        team_id=team_id,
                        opponent_team_id=opponent_team_id,
                        match_id=map_result.match_id,
                        map_id=map_result.map_id,
                        map_number=map_result.map_number,
                        map_name=map_name,
                        event_time=map_result.event_time,
                        won=bool(actual),
                        actual_score=actual,
                        expected_score=expected,
                        pre_global_mu=global_pre_mu,
                        pre_map_mu=map_pre_mu,
                        pre_effective_mu=effective_pre_mu,
                        pre_global_sigma=global_pre_sigma,
                        pre_map_sigma=map_pre_sigma,
                        pre_effective_sigma=effective_pre_sigma,
                        pre_global_ordinal=float(global_pre.ordinal(self.params.ordinal_z)),
                        pre_map_ordinal=float(map_pre.ordinal(self.params.ordinal_z)),
                        pre_effective_ordinal=float(effective_pre.ordinal(self.params.ordinal_z)),
                        mu_delta=mu_delta,
                        sigma_delta=sigma_delta,
                        ordinal_delta=ordinal_delta,
                        post_global_mu=global_post_mu,
                        post_map_mu=map_post_mu,
                        post_effective_mu=effective_post_mu_blended,
                        post_global_sigma=global_post_sigma,
                        post_map_sigma=map_post_sigma,
                        post_effective_sigma=effective_post_sigma_blended,
                        post_global_ordinal=float(global_post.ordinal(self.params.ordinal_z)),
                        post_map_ordinal=float(map_post.ordinal(self.params.ordinal_z)),
                        post_effective_ordinal=float(effective_post_blended.ordinal(self.params.ordinal_z)),
                        map_games_played_pre=map_games_pre,
                        map_blend_weight=blend_weight,
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
                )

        process_side(
            players=map_result.team1_players,
            side_state=team1_state,
            effective_post=team1_effective_post,
            team_id=map_result.team1_id,
            opponent_team_id=map_result.team2_id,
            actual=team1_actual,
            expected=team1_expected,
        )
        process_side(
            players=map_result.team2_players,
            side_state=team2_state,
            effective_post=team2_effective_post,
            team_id=map_result.team2_id,
            opponent_team_id=map_result.team1_id,
            actual=team2_actual,
            expected=team2_expected,
        )

        return events
