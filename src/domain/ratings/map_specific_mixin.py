"""Shared mixin for map-specific rating calculators (per-map state and blending helpers)."""

from __future__ import annotations

from datetime import datetime


class MapSpecificMixin:
    """Mixin providing shared per-map name normalization, keying, games played, and blend weight.

    Subclasses must:
    - Define params with map_prior_games (float).
    - Initialize _map_ratings or _map_states (and optionally _map_last_event_times) in __init__.
    - Use _map_key, _get_map_games_played, _map_blend_weight when implementing process_map.
    """

    _map_games_played: dict[tuple[int, str], int]

    def _normalize_map_name(self, map_name: str | None) -> str:
        normalized = (map_name or "").strip().upper()
        return normalized or "UNKNOWN"

    def _map_key(self, *, team_id: int, map_name: str) -> tuple[int, str]:
        return (team_id, map_name)

    def _get_map_games_played(self, *, team_id: int, map_name: str) -> int:
        key = self._map_key(team_id=team_id, map_name=map_name)
        return self._map_games_played.get(key, 0)

    def _map_blend_weight(self, *, map_games_played: int) -> float:
        prior = getattr(self.params, "map_prior_games", 0.0)
        if prior <= 0.0:
            return 1.0
        return map_games_played / (map_games_played + prior)

    def _record_map_games_played(
        self,
        *,
        team1_id: int,
        team2_id: int,
        map_name: str,
        team1_games_pre: int,
        team2_games_pre: int,
        event_time: datetime,
    ) -> None:
        """Update _map_games_played and optionally _map_last_event_times after a map."""
        key1 = self._map_key(team_id=team1_id, map_name=map_name)
        key2 = self._map_key(team_id=team2_id, map_name=map_name)
        self._map_games_played[key1] = team1_games_pre + 1
        self._map_games_played[key2] = team2_games_pre + 1
        if hasattr(self, "_map_last_event_times"):
            last_times: dict[tuple[int, str], datetime] = self._map_last_event_times
            last_times[key1] = event_time
            last_times[key2] = event_time
