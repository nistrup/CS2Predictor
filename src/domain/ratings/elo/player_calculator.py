"""Player-level Elo logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.ratings.common import PlayerMapParticipant, PlayerMapResult, TeamMapResult
from domain.ratings.elo.calculator import EloParameters, TeamEloCalculator, calculate_expected_score
from domain.ratings.player_mixin import PlayerCalculatorMixin


@dataclass(frozen=True)
class PlayerEloEvent:
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
    pre_elo: float
    elo_delta: float
    post_elo: float
    k_factor: float
    scale_factor: float
    initial_elo: float


class PlayerEloCalculator(PlayerCalculatorMixin, TeamEloCalculator):
    """Stateful map-by-map player Elo calculator."""

    def __init__(
        self,
        params: EloParameters,
        *,
        lookback_days: int | None = None,
        as_of_time: datetime | None = None,
    ) -> None:
        super().__init__(
            params=params,
            lookback_days=lookback_days,
            as_of_time=as_of_time,
        )

    def _side_pre_ratings(
        self,
        participants: tuple[PlayerMapParticipant, ...],
        *,
        event_time: datetime,
    ) -> dict[int, float]:
        return {
            participant.player_id: self._apply_inactivity_decay(
                team_id=participant.player_id,
                event_time=event_time,
            )
            for participant in participants
        }

    def process_map(self, map_result: PlayerMapResult) -> list[PlayerEloEvent]:
        self._validate_player_map(map_result)

        team1_pre = self._side_pre_ratings(
            map_result.team1_players,
            event_time=map_result.event_time,
        )
        team2_pre = self._side_pre_ratings(
            map_result.team2_players,
            event_time=map_result.event_time,
        )

        team1_avg_pre = self._average_rating(team1_pre)
        team2_avg_pre = self._average_rating(team2_pre)

        team1_expected_team = calculate_expected_score(
            rating=team1_avg_pre,
            opponent_rating=team2_avg_pre,
            scale_factor=self.params.scale_factor,
        )
        team2_expected_team = 1.0 - team1_expected_team

        team1_actual, team2_actual = self._player_map_outcome(map_result)

        winner_pre_elo = team1_avg_pre if team1_actual == 1.0 else team2_avg_pre
        loser_pre_elo = team2_avg_pre if team1_actual == 1.0 else team1_avg_pre
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

        events: list[PlayerEloEvent] = []

        for participant in map_result.team1_players:
            pre_elo = team1_pre[participant.player_id]
            expected = calculate_expected_score(
                rating=pre_elo,
                opponent_rating=team2_avg_pre,
                scale_factor=self.params.scale_factor,
            )
            delta = effective_k * (team1_actual - expected)
            post_elo = pre_elo + delta
            self._ratings[participant.player_id] = post_elo
            self._last_event_times[participant.player_id] = map_result.event_time

            events.append(
                PlayerEloEvent(
                    player_id=participant.player_id,
                    team_id=map_result.team1_id,
                    opponent_team_id=map_result.team2_id,
                    match_id=map_result.match_id,
                    map_id=map_result.map_id,
                    map_number=map_result.map_number,
                    event_time=map_result.event_time,
                    won=bool(team1_actual),
                    actual_score=team1_actual,
                    expected_score=expected,
                    pre_elo=pre_elo,
                    elo_delta=delta,
                    post_elo=post_elo,
                    k_factor=effective_k,
                    scale_factor=self.params.scale_factor,
                    initial_elo=self.params.initial_elo,
                )
            )

        for participant in map_result.team2_players:
            pre_elo = team2_pre[participant.player_id]
            expected = calculate_expected_score(
                rating=pre_elo,
                opponent_rating=team1_avg_pre,
                scale_factor=self.params.scale_factor,
            )
            delta = effective_k * (team2_actual - expected)
            post_elo = pre_elo + delta
            self._ratings[participant.player_id] = post_elo
            self._last_event_times[participant.player_id] = map_result.event_time

            events.append(
                PlayerEloEvent(
                    player_id=participant.player_id,
                    team_id=map_result.team2_id,
                    opponent_team_id=map_result.team1_id,
                    match_id=map_result.match_id,
                    map_id=map_result.map_id,
                    map_number=map_result.map_number,
                    event_time=map_result.event_time,
                    won=bool(team2_actual),
                    actual_score=team2_actual,
                    expected_score=expected,
                    pre_elo=pre_elo,
                    elo_delta=delta,
                    post_elo=post_elo,
                    k_factor=effective_k,
                    scale_factor=self.params.scale_factor,
                    initial_elo=self.params.initial_elo,
                )
            )

        return events
