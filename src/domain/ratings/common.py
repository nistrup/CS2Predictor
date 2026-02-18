"""Shared types for rating systems."""

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


@dataclass(frozen=True)
class TeamMatchResult:
    """Canonical match outcome payload used by match-level rating calculators."""

    match_id: int
    event_time: datetime
    team1_id: int
    team2_id: int
    winner_id: int
    team1_maps_won: int
    team2_maps_won: int
    is_lan: bool = False
    match_format: str | None = None


@dataclass(frozen=True)
class PlayerMapParticipant:
    """Per-player map payload used by player-level rating calculators."""

    player_id: int
    team_id: int
    kills: int | None = None
    deaths: int | None = None
    adr: float | None = None
    kast: float | None = None
    rating: float | None = None
    swing: float | None = None


@dataclass(frozen=True)
class PlayerMapResult:
    """Canonical map outcome payload for player-level calculators."""

    match_id: int
    map_id: int
    map_number: int
    event_time: datetime
    team1_id: int
    team2_id: int
    winner_id: int
    team1_players: tuple[PlayerMapParticipant, ...]
    team2_players: tuple[PlayerMapParticipant, ...]
    map_name: str | None = None
    team1_score: int | None = None
    team2_score: int | None = None
    team1_kd_ratio: float | None = None
    team2_kd_ratio: float | None = None
    is_lan: bool = False
    match_format: str | None = None


@dataclass(frozen=True)
class PlayerMatchParticipant:
    """Per-player match payload used by player-level match calculators."""

    player_id: int
    team_id: int
    maps_played: int
    kills: int | None = None
    deaths: int | None = None
    adr: float | None = None
    kast: float | None = None
    rating: float | None = None
    swing: float | None = None


@dataclass(frozen=True)
class PlayerMatchResult:
    """Canonical match outcome payload for player-level calculators."""

    match_id: int
    event_time: datetime
    team1_id: int
    team2_id: int
    winner_id: int
    team1_maps_won: int
    team2_maps_won: int
    team1_players: tuple[PlayerMatchParticipant, ...]
    team2_players: tuple[PlayerMatchParticipant, ...]
    is_lan: bool = False
    match_format: str | None = None
