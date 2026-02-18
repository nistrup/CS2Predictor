"""Match-level player Glicko-2 logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.ratings.common import PlayerMatchParticipant, PlayerMatchResult
from domain.ratings.glicko2.calculator import (
    Glicko2OpponentResult,
    Glicko2Parameters,
    TeamGlicko2Calculator,
    _TeamGlicko2State,
    calculate_expected_score,
    update_glicko2_player,
)
from domain.ratings.player_mixin import PlayerCalculatorMixin


@dataclass(frozen=True)
class PlayerMatchGlicko2Event:
    player_id: int
    team_id: int
    opponent_team_id: int
    match_id: int
    event_time: datetime
    won: bool
    actual_score: float
    expected_score: float
    pre_rating: float
    pre_rd: float
    pre_volatility: float
    rating_delta: float
    rd_delta: float
    volatility_delta: float
    post_rating: float
    post_rd: float
    post_volatility: float
    tau: float
    rating_period_days: float
    initial_rating: float
    initial_rd: float
    initial_volatility: float
    team_maps_won: int
    opponent_maps_won: int


class PlayerMatchGlicko2Calculator(PlayerCalculatorMixin, TeamGlicko2Calculator):
    """Stateful match-by-match player Glicko-2 calculator."""

    def __init__(self, params: Glicko2Parameters) -> None:
        super().__init__(params=params)

    def _side_pre_state(
        self,
        participants: tuple[PlayerMatchParticipant, ...],
        *,
        event_time: datetime,
    ) -> dict[int, tuple[float, float, float]]:
        state: dict[int, tuple[float, float, float]] = {}
        for participant in participants:
            player_id = participant.player_id
            player_state = self._get_or_create_state(player_id)
            pre_rating = player_state.rating
            pre_rd = self._inflate_rd_for_inactivity(
                team_id=player_id,
                rd=player_state.rd,
                volatility=player_state.volatility,
                event_time=event_time,
            )
            pre_vol = player_state.volatility
            state[player_id] = (pre_rating, pre_rd, pre_vol)
        return state

    @staticmethod
    def _average_side_values(side_state: dict[int, tuple[float, float, float]]) -> tuple[float, float, float]:
        count = float(len(side_state))
        avg_rating = sum(values[0] for values in side_state.values()) / count
        avg_rd = sum(values[1] for values in side_state.values()) / count
        avg_vol = sum(values[2] for values in side_state.values()) / count
        return avg_rating, avg_rd, avg_vol

    def process_match(self, match_result: PlayerMatchResult) -> list[PlayerMatchGlicko2Event]:
        self._validate_player_match(match_result)

        team1_state = self._side_pre_state(
            match_result.team1_players,
            event_time=match_result.event_time,
        )
        team2_state = self._side_pre_state(
            match_result.team2_players,
            event_time=match_result.event_time,
        )

        team1_avg_rating, team1_avg_rd, _ = self._average_side_values(team1_state)
        team2_avg_rating, team2_avg_rd, _ = self._average_side_values(team2_state)

        team1_actual, team2_actual, team1_maps_won, team2_maps_won = self._player_match_outcome(
            match_result
        )

        events: list[PlayerMatchGlicko2Event] = []

        def process_side(
            *,
            participants: tuple[PlayerMatchParticipant, ...],
            side_state: dict[int, tuple[float, float, float]],
            team_id: int,
            opponent_team_id: int,
            actual: float,
            maps_won: int,
            opponent_maps_won: int,
            opponent_avg_rating: float,
            opponent_avg_rd: float,
        ) -> None:
            for participant in participants:
                player_id = participant.player_id
                pre_rating, pre_rd, pre_vol = side_state[player_id]
                expected = calculate_expected_score(
                    rating=pre_rating,
                    rd=pre_rd,
                    opponent_rating=opponent_avg_rating,
                    opponent_rd=opponent_avg_rd,
                )

                post_rating, post_rd, post_vol = update_glicko2_player(
                    rating=pre_rating,
                    rd=pre_rd,
                    volatility=pre_vol,
                    results=[
                        Glicko2OpponentResult(
                            opponent_rating=opponent_avg_rating,
                            opponent_rd=opponent_avg_rd,
                            score=actual,
                        )
                    ],
                    tau=self.params.tau,
                    epsilon=self.params.epsilon,
                )

                post_rd = self._clamp_rd(post_rd)
                self._states[player_id] = _TeamGlicko2State(
                    rating=post_rating,
                    rd=post_rd,
                    volatility=post_vol,
                )
                self._last_event_times[player_id] = match_result.event_time

                events.append(
                    PlayerMatchGlicko2Event(
                        player_id=player_id,
                        team_id=team_id,
                        opponent_team_id=opponent_team_id,
                        match_id=match_result.match_id,
                        event_time=match_result.event_time,
                        won=bool(actual),
                        actual_score=actual,
                        expected_score=expected,
                        pre_rating=pre_rating,
                        pre_rd=pre_rd,
                        pre_volatility=pre_vol,
                        rating_delta=post_rating - pre_rating,
                        rd_delta=post_rd - pre_rd,
                        volatility_delta=post_vol - pre_vol,
                        post_rating=post_rating,
                        post_rd=post_rd,
                        post_volatility=post_vol,
                        tau=self.params.tau,
                        rating_period_days=self.params.rating_period_days,
                        initial_rating=self.params.initial_rating,
                        initial_rd=self.params.initial_rd,
                        initial_volatility=self.params.initial_volatility,
                        team_maps_won=maps_won,
                        opponent_maps_won=opponent_maps_won,
                    )
                )

        process_side(
            participants=match_result.team1_players,
            side_state=team1_state,
            team_id=match_result.team1_id,
            opponent_team_id=match_result.team2_id,
            actual=team1_actual,
            maps_won=team1_maps_won,
            opponent_maps_won=team2_maps_won,
            opponent_avg_rating=team2_avg_rating,
            opponent_avg_rd=team2_avg_rd,
        )
        process_side(
            participants=match_result.team2_players,
            side_state=team2_state,
            team_id=match_result.team2_id,
            opponent_team_id=match_result.team1_id,
            actual=team2_actual,
            maps_won=team2_maps_won,
            opponent_maps_won=team1_maps_won,
            opponent_avg_rating=team1_avg_rating,
            opponent_avg_rd=team1_avg_rd,
        )

        return events
