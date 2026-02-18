"""Map-specific player Glicko-2 logic with global-rating shrinkage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.ratings.common import PlayerMapParticipant, PlayerMapResult
from domain.ratings.glicko2.calculator import (
    GLICKO2_SCALE,
    Glicko2OpponentResult,
    _TeamGlicko2State,
    calculate_expected_score,
    update_glicko2_player,
)
from domain.ratings.glicko2.map_specific_calculator import MapSpecificGlicko2Parameters
from domain.ratings.glicko2.player_calculator import PlayerGlicko2Calculator


@dataclass(frozen=True)
class PlayerMapGlicko2Event:
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
    pre_global_rating: float
    pre_map_rating: float
    pre_effective_rating: float
    pre_global_rd: float
    pre_map_rd: float
    pre_effective_rd: float
    pre_global_volatility: float
    pre_map_volatility: float
    pre_effective_volatility: float
    rating_delta: float
    rd_delta: float
    volatility_delta: float
    post_global_rating: float
    post_map_rating: float
    post_effective_rating: float
    post_global_rd: float
    post_map_rd: float
    post_effective_rd: float
    post_global_volatility: float
    post_map_volatility: float
    post_effective_volatility: float
    map_games_played_pre: int
    map_blend_weight: float
    tau: float
    rating_period_days: float
    initial_rating: float
    initial_rd: float
    initial_volatility: float
    map_prior_games: float


class PlayerMapSpecificGlicko2Calculator(PlayerGlicko2Calculator):
    """Stateful map-by-map calculator blending map-specific and global player Glicko-2 state."""

    def __init__(self, params: MapSpecificGlicko2Parameters) -> None:
        super().__init__(params=params)
        self.params = params
        self._map_states: dict[tuple[int, str], _TeamGlicko2State] = {}
        self._map_games_played: dict[tuple[int, str], int] = {}
        self._map_last_event_times: dict[tuple[int, str], datetime] = {}

    def _normalize_map_name(self, map_name: str | None) -> str:
        normalized = (map_name or "").strip().upper()
        return normalized or "UNKNOWN"

    def _map_key(self, *, player_id: int, map_name: str) -> tuple[int, str]:
        return (player_id, map_name)

    def _get_or_create_map_state(self, *, player_id: int, map_name: str) -> _TeamGlicko2State:
        key = self._map_key(player_id=player_id, map_name=map_name)
        existing = self._map_states.get(key)
        if existing is not None:
            return existing

        state = _TeamGlicko2State(
            rating=self.params.initial_rating,
            rd=self._clamp_rd(self.params.initial_rd),
            volatility=self.params.initial_volatility,
        )
        self._map_states[key] = state
        return state

    def _get_map_games_played(self, *, player_id: int, map_name: str) -> int:
        key = self._map_key(player_id=player_id, map_name=map_name)
        return self._map_games_played.get(key, 0)

    def _map_blend_weight(self, *, map_games_played: int) -> float:
        if self.params.map_prior_games <= 0.0:
            return 1.0
        return map_games_played / (map_games_played + self.params.map_prior_games)

    def _inflate_map_rd_for_inactivity(
        self,
        *,
        player_id: int,
        map_name: str,
        rd: float,
        volatility: float,
        event_time: datetime,
    ) -> float:
        key = self._map_key(player_id=player_id, map_name=map_name)
        last_event_time = self._map_last_event_times.get(key)
        if last_event_time is None:
            return self._clamp_rd(rd)

        inactive_days = (event_time - last_event_time).total_seconds() / 86_400.0
        if inactive_days <= 0.0:
            return self._clamp_rd(rd)

        inactive_periods = inactive_days / self.params.rating_period_days
        if inactive_periods <= 0.0:
            return self._clamp_rd(rd)

        inflated_rd = (
            ((rd / GLICKO2_SCALE) ** 2 + ((volatility**2) * inactive_periods)) ** 0.5
            * GLICKO2_SCALE
        )
        return self._clamp_rd(inflated_rd)

    @staticmethod
    def _clamp_volatility(volatility: float) -> float:
        return max(volatility, 1e-9)

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

            global_state = self._get_or_create_state(player_id)
            global_pre_rating = global_state.rating
            global_pre_vol = global_state.volatility
            global_pre_rd = self._inflate_rd_for_inactivity(
                team_id=player_id,
                rd=global_state.rd,
                volatility=global_state.volatility,
                event_time=event_time,
            )

            map_state = self._get_or_create_map_state(player_id=player_id, map_name=map_name)
            map_pre_rating = map_state.rating
            map_pre_vol = map_state.volatility
            map_pre_rd = self._inflate_map_rd_for_inactivity(
                player_id=player_id,
                map_name=map_name,
                rd=map_state.rd,
                volatility=map_state.volatility,
                event_time=event_time,
            )

            map_games_pre = self._get_map_games_played(player_id=player_id, map_name=map_name)
            blend_weight = self._map_blend_weight(map_games_played=map_games_pre)

            effective_pre_rating = (blend_weight * map_pre_rating) + ((1.0 - blend_weight) * global_pre_rating)
            effective_pre_rd = (blend_weight * map_pre_rd) + ((1.0 - blend_weight) * global_pre_rd)
            effective_pre_vol = (blend_weight * map_pre_vol) + ((1.0 - blend_weight) * global_pre_vol)

            state[player_id] = {
                "global_pre_rating": global_pre_rating,
                "global_pre_rd": global_pre_rd,
                "global_pre_vol": global_pre_vol,
                "map_pre_rating": map_pre_rating,
                "map_pre_rd": map_pre_rd,
                "map_pre_vol": map_pre_vol,
                "map_games_pre": map_games_pre,
                "blend_weight": blend_weight,
                "effective_pre_rating": effective_pre_rating,
                "effective_pre_rd": effective_pre_rd,
                "effective_pre_vol": effective_pre_vol,
            }

        return state

    @staticmethod
    def _average_effective_state(side_state: dict[int, dict[str, float | int]]) -> tuple[float, float, float]:
        count = float(len(side_state))
        avg_rating = sum(float(values["effective_pre_rating"]) for values in side_state.values()) / count
        avg_rd = sum(float(values["effective_pre_rd"]) for values in side_state.values()) / count
        avg_vol = sum(float(values["effective_pre_vol"]) for values in side_state.values()) / count
        return avg_rating, avg_rd, avg_vol

    def process_map(self, map_result: PlayerMapResult) -> list[PlayerMapGlicko2Event]:
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

        team1_avg_rating, team1_avg_rd, _ = self._average_effective_state(team1_state)
        team2_avg_rating, team2_avg_rd, _ = self._average_effective_state(team2_state)

        team1_actual, team2_actual = self._player_map_outcome(map_result)

        events: list[PlayerMapGlicko2Event] = []

        def process_side(
            *,
            participants: tuple[PlayerMapParticipant, ...],
            side_state: dict[int, dict[str, float | int]],
            team_id: int,
            opponent_team_id: int,
            actual: float,
            opponent_avg_rating: float,
            opponent_avg_rd: float,
        ) -> None:
            for participant in participants:
                player_id = participant.player_id
                values = side_state[player_id]

                global_pre_rating = float(values["global_pre_rating"])
                global_pre_rd = float(values["global_pre_rd"])
                global_pre_vol = float(values["global_pre_vol"])
                map_pre_rating = float(values["map_pre_rating"])
                map_pre_rd = float(values["map_pre_rd"])
                map_pre_vol = float(values["map_pre_vol"])
                map_games_pre = int(values["map_games_pre"])
                blend_weight = float(values["blend_weight"])
                effective_pre_rating = float(values["effective_pre_rating"])
                effective_pre_rd = float(values["effective_pre_rd"])
                effective_pre_vol = float(values["effective_pre_vol"])

                expected = calculate_expected_score(
                    rating=effective_pre_rating,
                    rd=effective_pre_rd,
                    opponent_rating=opponent_avg_rating,
                    opponent_rd=opponent_avg_rd,
                )

                effective_post_rating, effective_post_rd, effective_post_vol = update_glicko2_player(
                    rating=effective_pre_rating,
                    rd=effective_pre_rd,
                    volatility=effective_pre_vol,
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

                effective_post_rd = self._clamp_rd(effective_post_rd)

                rating_delta = effective_post_rating - effective_pre_rating
                rd_delta = effective_post_rd - effective_pre_rd
                volatility_delta = effective_post_vol - effective_pre_vol

                global_post_rating = global_pre_rating + rating_delta
                map_post_rating = map_pre_rating + rating_delta
                global_post_rd = self._clamp_rd(global_pre_rd + rd_delta)
                map_post_rd = self._clamp_rd(map_pre_rd + rd_delta)
                global_post_vol = self._clamp_volatility(global_pre_vol + volatility_delta)
                map_post_vol = self._clamp_volatility(map_pre_vol + volatility_delta)

                self._states[player_id] = _TeamGlicko2State(
                    rating=global_post_rating,
                    rd=global_post_rd,
                    volatility=global_post_vol,
                )
                key = self._map_key(player_id=player_id, map_name=map_name)
                self._map_states[key] = _TeamGlicko2State(
                    rating=map_post_rating,
                    rd=map_post_rd,
                    volatility=map_post_vol,
                )
                self._map_games_played[key] = map_games_pre + 1
                self._last_event_times[player_id] = map_result.event_time
                self._map_last_event_times[key] = map_result.event_time

                effective_post_rating = (blend_weight * map_post_rating) + ((1.0 - blend_weight) * global_post_rating)
                effective_post_rd = (blend_weight * map_post_rd) + ((1.0 - blend_weight) * global_post_rd)
                effective_post_vol = (blend_weight * map_post_vol) + ((1.0 - blend_weight) * global_post_vol)

                events.append(
                    PlayerMapGlicko2Event(
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
                        pre_global_rating=global_pre_rating,
                        pre_map_rating=map_pre_rating,
                        pre_effective_rating=effective_pre_rating,
                        pre_global_rd=global_pre_rd,
                        pre_map_rd=map_pre_rd,
                        pre_effective_rd=effective_pre_rd,
                        pre_global_volatility=global_pre_vol,
                        pre_map_volatility=map_pre_vol,
                        pre_effective_volatility=effective_pre_vol,
                        rating_delta=rating_delta,
                        rd_delta=rd_delta,
                        volatility_delta=volatility_delta,
                        post_global_rating=global_post_rating,
                        post_map_rating=map_post_rating,
                        post_effective_rating=effective_post_rating,
                        post_global_rd=global_post_rd,
                        post_map_rd=map_post_rd,
                        post_effective_rd=effective_post_rd,
                        post_global_volatility=global_post_vol,
                        post_map_volatility=map_post_vol,
                        post_effective_volatility=effective_post_vol,
                        map_games_played_pre=map_games_pre,
                        map_blend_weight=blend_weight,
                        tau=self.params.tau,
                        rating_period_days=self.params.rating_period_days,
                        initial_rating=self.params.initial_rating,
                        initial_rd=self.params.initial_rd,
                        initial_volatility=self.params.initial_volatility,
                        map_prior_games=self.params.map_prior_games,
                    )
                )

        process_side(
            participants=map_result.team1_players,
            side_state=team1_state,
            team_id=map_result.team1_id,
            opponent_team_id=map_result.team2_id,
            actual=team1_actual,
            opponent_avg_rating=team2_avg_rating,
            opponent_avg_rd=team2_avg_rd,
        )
        process_side(
            participants=map_result.team2_players,
            side_state=team2_state,
            team_id=map_result.team2_id,
            opponent_team_id=map_result.team1_id,
            actual=team2_actual,
            opponent_avg_rating=team1_avg_rating,
            opponent_avg_rd=team1_avg_rd,
        )

        return events
