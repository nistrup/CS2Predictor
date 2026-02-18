"""Shared validation and outcome helpers for match-level team rating calculators."""

from __future__ import annotations

from domain.ratings.common import TeamMatchResult


class MatchAdapterMixin:
    """Mixin providing shared match validation and outcome extraction.

    Subclasses implement algorithm-specific pre/expected/update/post and event building.
    """

    def _validate_team_match(self, match_result: TeamMatchResult) -> None:
        if match_result.team1_id == match_result.team2_id:
            raise ValueError(
                f"match_id={match_result.match_id} has identical teams ({match_result.team1_id})"
            )
        if match_result.winner_id not in (match_result.team1_id, match_result.team2_id):
            raise ValueError(
                f"winner_id={match_result.winner_id} does not belong to match teams "
                f"{match_result.team1_id}/{match_result.team2_id} for match_id={match_result.match_id}"
            )

    def _match_outcome(
        self, match_result: TeamMatchResult
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
