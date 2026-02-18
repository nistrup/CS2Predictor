"""Map-specific player Elo logic with global-rating shrinkage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.ratings.common import PlayerMapParticipant, PlayerMapResult
from domain.ratings.elo.calculator import calculate_expected_score
from domain.ratings.elo.map_specific_calculator import MapSpecificEloParameters
from domain.ratings.elo.player_calculator import PlayerEloCalculator


@dataclass(frozen=True)
class PlayerMapEloEvent:
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


class PlayerMapSpecificEloCalculator(PlayerEloCalculator):
    """Stateful map-by-map calculator blending map-specific and global player Elo."""

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
        self._map_games_played: dict[tuple[int, str], int] = {}
        self._map_last_event_times: dict[tuple[int, str], datetime] = {}

    def _normalize_map_name(self, map_name: str | None) -> str:
        normalized = (map_name or "").strip().upper()
        return normalized or "UNKNOWN"

    def _map_key(self, *, player_id: int, map_name: str) -> tuple[int, str]:
        return (player_id, map_name)

    def _get_map_rating(self, *, player_id: int, map_name: str) -> float:
        key = self._map_key(player_id=player_id, map_name=map_name)
        return self._map_ratings.get(key, self.params.initial_elo)

    def _get_map_games_played(self, *, player_id: int, map_name: str) -> int:
        key = self._map_key(player_id=player_id, map_name=map_name)
        return self._map_games_played.get(key, 0)

    def _map_blend_weight(self, *, map_games_played: int) -> float:
        if self.params.map_prior_games <= 0.0:
            return 1.0
        return map_games_played / (map_games_played + self.params.map_prior_games)

    def _apply_map_inactivity_decay(self, *, player_id: int, map_name: str, event_time: datetime) -> float:
        rating = self._get_map_rating(player_id=player_id, map_name=map_name)
        if self._inactivity_decay_lambda <= 0.0:
            return rating

        key = self._map_key(player_id=player_id, map_name=map_name)
        last_event_time = self._map_last_event_times.get(key)
        if last_event_time is None:
            return rating

        inactive_days = (event_time - last_event_time).total_seconds() / 86_400.0
        if inactive_days <= 0.0:
            return rating

        decay_factor = pow(2.0, -inactive_days / self.params.inactivity_half_life_days)
        return self.params.initial_elo + ((rating - self.params.initial_elo) * decay_factor)

    def _side_pre_state(
        self,
        participants: tuple[PlayerMapParticipant, ...],
        *,
        map_name: str,
        event_time: datetime,
    ) -> dict[int, dict[str, float | int]]:
        state: dict[int, dict[str, float | int]] = {}
        for participant in participants:
            player_id = participant.player_id
            global_pre = self._apply_inactivity_decay(
                team_id=player_id,
                event_time=event_time,
            )
            map_pre = self._apply_map_inactivity_decay(
                player_id=player_id,
                map_name=map_name,
                event_time=event_time,
            )
            map_games_pre = self._get_map_games_played(
                player_id=player_id,
                map_name=map_name,
            )
            blend_weight = self._map_blend_weight(map_games_played=map_games_pre)
            effective_pre = (blend_weight * map_pre) + ((1.0 - blend_weight) * global_pre)

            state[player_id] = {
                "global_pre": global_pre,
                "map_pre": map_pre,
                "map_games_pre": map_games_pre,
                "blend_weight": blend_weight,
                "effective_pre": effective_pre,
            }
        return state

    @staticmethod
    def _average_effective_pre(side_state: dict[int, dict[str, float | int]]) -> float:
        total = sum(float(values["effective_pre"]) for values in side_state.values())
        return total / float(len(side_state))

    def process_map(self, map_result: PlayerMapResult) -> list[PlayerMapEloEvent]:
        self._validate_player_map(map_result)

        map_name = self._normalize_map_name(map_result.map_name)
        team1_state = self._side_pre_state(
            map_result.team1_players,
            map_name=map_name,
            event_time=map_result.event_time,
        )
        team2_state = self._side_pre_state(
            map_result.team2_players,
            map_name=map_name,
            event_time=map_result.event_time,
        )

        team1_avg_effective_pre = self._average_effective_pre(team1_state)
        team2_avg_effective_pre = self._average_effective_pre(team2_state)

        team1_expected_team = calculate_expected_score(
            rating=team1_avg_effective_pre,
            opponent_rating=team2_avg_effective_pre,
            scale_factor=self.params.scale_factor,
        )
        team2_expected_team = 1.0 - team1_expected_team

        team1_actual, team2_actual = self._player_map_outcome(map_result)

        winner_pre_elo = team1_avg_effective_pre if team1_actual == 1.0 else team2_avg_effective_pre
        loser_pre_elo = team2_avg_effective_pre if team1_actual == 1.0 else team1_avg_effective_pre
        winner_expected_score = team1_expected_team if team1_actual == 1.0 else team2_expected_team

        effective_k = (
            self.params.k_factor
            * self._format_multiplier(map_result.match_format)
            * self._winner_outcome_multiplier(
                winner_pre_elo=winner_pre_elo,
                loser_pre_elo=loser_pre_elo,
            )
            * self._opponent_strength_multiplier(winner_expected_score=winner_expected_score)
            * (self.params.lan_multiplier if map_result.is_lan else 1.0)
            * self._round_domination_multiplier(self._map_proxy(map_result))
            * self._kd_ratio_domination_multiplier(self._map_proxy(map_result))
            * self._recency_multiplier(map_result.event_time)
        )

        events: list[PlayerMapEloEvent] = []

        def process_side(
            *,
            participants: tuple[PlayerMapParticipant, ...],
            side_state: dict[int, dict[str, float | int]],
            team_id: int,
            opponent_team_id: int,
            actual: float,
            opponent_average_pre: float,
        ) -> None:
            for participant in participants:
                player_id = participant.player_id
                values = side_state[player_id]
                global_pre = float(values["global_pre"])
                map_pre = float(values["map_pre"])
                map_games_pre = int(values["map_games_pre"])
                blend_weight = float(values["blend_weight"])
                effective_pre = float(values["effective_pre"])

                expected = calculate_expected_score(
                    rating=effective_pre,
                    opponent_rating=opponent_average_pre,
                    scale_factor=self.params.scale_factor,
                )
                delta = effective_k * (actual - expected)

                global_post = global_pre + delta
                map_post = map_pre + delta
                effective_post = (blend_weight * map_post) + ((1.0 - blend_weight) * global_post)

                self._ratings[player_id] = global_post
                self._last_event_times[player_id] = map_result.event_time

                key = self._map_key(player_id=player_id, map_name=map_name)
                self._map_ratings[key] = map_post
                self._map_games_played[key] = map_games_pre + 1
                self._map_last_event_times[key] = map_result.event_time

                events.append(
                    PlayerMapEloEvent(
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
                        pre_global_elo=global_pre,
                        pre_map_elo=map_pre,
                        pre_effective_elo=effective_pre,
                        elo_delta=delta,
                        post_global_elo=global_post,
                        post_map_elo=map_post,
                        post_effective_elo=effective_post,
                        map_games_played_pre=map_games_pre,
                        map_blend_weight=blend_weight,
                        k_factor=effective_k,
                        scale_factor=self.params.scale_factor,
                        initial_elo=self.params.initial_elo,
                        map_prior_games=self.params.map_prior_games,
                    )
                )

        process_side(
            participants=map_result.team1_players,
            side_state=team1_state,
            team_id=map_result.team1_id,
            opponent_team_id=map_result.team2_id,
            actual=team1_actual,
            opponent_average_pre=team2_avg_effective_pre,
        )
        process_side(
            participants=map_result.team2_players,
            side_state=team2_state,
            team_id=map_result.team2_id,
            opponent_team_id=map_result.team1_id,
            actual=team2_actual,
            opponent_average_pre=team1_avg_effective_pre,
        )

        return events
