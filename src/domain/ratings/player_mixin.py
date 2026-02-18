"""Shared helpers for player-level rating calculators (validation, map proxy, average rating)."""

from __future__ import annotations

from domain.ratings.common import PlayerMapResult, PlayerMatchResult, TeamMapResult


class PlayerCalculatorMixin:
    """Mixin providing shared player-map/match validation, map proxy, and average rating.

    Subclasses implement algorithm-specific pre/update/post and event building.
    """

    def _validate_player_map(self, map_result: PlayerMapResult) -> None:
        if map_result.team1_id == map_result.team2_id:
            raise ValueError(
                f"map_id={map_result.map_id} has identical teams ({map_result.team1_id})"
            )
        if map_result.winner_id not in (map_result.team1_id, map_result.team2_id):
            raise ValueError(
                f"winner_id={map_result.winner_id} does not belong to map teams "
                f"{map_result.team1_id}/{map_result.team2_id} for map_id={map_result.map_id}"
            )
        if not map_result.team1_players or not map_result.team2_players:
            raise ValueError(
                f"map_id={map_result.map_id} is missing players for one or both teams"
            )

    def _validate_player_match(self, match_result: PlayerMatchResult) -> None:
        if match_result.team1_id == match_result.team2_id:
            raise ValueError(
                f"match_id={match_result.match_id} has identical teams ({match_result.team1_id})"
            )
        if match_result.winner_id not in (match_result.team1_id, match_result.team2_id):
            raise ValueError(
                f"winner_id={match_result.winner_id} does not belong to match teams "
                f"{match_result.team1_id}/{match_result.team2_id} for match_id={match_result.match_id}"
            )
        if not match_result.team1_players or not match_result.team2_players:
            raise ValueError(
                f"match_id={match_result.match_id} is missing players for one or both teams"
            )

    def _map_proxy(self, map_result: PlayerMapResult) -> TeamMapResult:
        """Convert PlayerMapResult to TeamMapResult for reusing team multiplier methods."""
        return TeamMapResult(
            match_id=map_result.match_id,
            map_id=map_result.map_id,
            map_name=map_result.map_name,
            map_number=map_result.map_number,
            event_time=map_result.event_time,
            team1_id=map_result.team1_id,
            team2_id=map_result.team2_id,
            winner_id=map_result.winner_id,
            team1_score=map_result.team1_score,
            team2_score=map_result.team2_score,
            team1_kd_ratio=map_result.team1_kd_ratio,
            team2_kd_ratio=map_result.team2_kd_ratio,
            is_lan=map_result.is_lan,
            match_format=map_result.match_format,
        )

    @staticmethod
    def _average_rating(pre_ratings: dict[int, float]) -> float:
        return sum(pre_ratings.values()) / float(len(pre_ratings))

    def _player_map_outcome(
        self, map_result: PlayerMapResult
    ) -> tuple[float, float]:
        """Return (team1_actual, team2_actual)."""
        team1_actual = 1.0 if map_result.winner_id == map_result.team1_id else 0.0
        team2_actual = 1.0 - team1_actual
        return team1_actual, team2_actual

    def _player_match_outcome(
        self, match_result: PlayerMatchResult
    ) -> tuple[float, float, int, int]:
        """Return (team1_actual, team2_actual, team1_maps_won, team2_maps_won)."""
        team1_actual = 1.0 if match_result.winner_id == match_result.team1_id else 0.0
        team2_actual = 1.0 - team1_actual
        return (
            team1_actual,
            team2_actual,
            match_result.team1_maps_won,
            match_result.team2_maps_won,
        )
