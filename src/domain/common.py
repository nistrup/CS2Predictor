"""Shared types for team-based rating systems."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class TeamMapResult:
    """Canonical map outcome payload used by rating calculators."""

    match_id: int
    map_id: int
    map_number: int
    event_time: datetime
    team1_id: int
    team2_id: int
    winner_id: int
    map_name: str | None = None
    team1_score: int | None = None
    team2_score: int | None = None
    team1_kd_ratio: float | None = None
    team2_kd_ratio: float | None = None
    is_lan: bool = False
    match_format: str | None = None
