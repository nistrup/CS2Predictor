"""Shared protocols and enums for rating systems."""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol, TypeVar, runtime_checkable


class Granularity(str, Enum):
    """How finely ratings are tracked and updated."""

    MAP = "map"


class Subject(str, Enum):
    """What entity is being rated."""

    TEAM = "team"
    PLAYER = "player"


E = TypeVar("E")


@runtime_checkable
class RatingCalculator(Protocol[E]):
    """Base contract all rating calculators satisfy."""

    def tracked_entity_count(self) -> int: ...

    def ratings(self) -> dict[int, Any]: ...


@runtime_checkable
class MapLevelCalculator(RatingCalculator[E], Protocol[E]):
    """Granularity.MAP calculators."""

    def process_map(self, result: object) -> list[E]: ...


__all__ = [
    "Granularity",
    "MapLevelCalculator",
    "RatingCalculator",
    "Subject",
]
