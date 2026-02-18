"""Registry coverage tests for player-level systems."""

from __future__ import annotations

from domain.ratings.protocol import Granularity, Subject
from domain.ratings.registry import get


def test_player_descriptors_exist_for_all_algorithms_and_granularities() -> None:
    algorithms = ("elo", "glicko2", "openskill")
    granularities = (
        Granularity.MAP,
        Granularity.MATCH,
        Granularity.MAP_SPECIFIC,
    )

    for algorithm in algorithms:
        for granularity in granularities:
            descriptor = get(algorithm, granularity, Subject.PLAYER)
            assert descriptor.subject == Subject.PLAYER
            assert descriptor.granularity == granularity
            assert descriptor.algorithm == algorithm
