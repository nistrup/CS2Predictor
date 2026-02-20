"""Generic rebuild pipeline for registered rating systems."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from domain.config_base import BaseSystemConfig
from domain.registry import RatingSystemDescriptor


@dataclass(frozen=True)
class RebuildSummary:
    """Outcome for one rebuilt system config."""

    algorithm: str
    granularity: str
    subject: str
    system_name: str
    config_file: str
    system_id: int
    processed_results: int
    inserted_events: int
    tracked_entities: int
    dry_run: bool


def rebuild_single_system(
    *,
    session_factory,
    descriptor: RatingSystemDescriptor,
    system_config: BaseSystemConfig,
    batch_size: int = 5000,
    dry_run: bool = False,
    echo: Callable[[str], None] | None = None,
) -> RebuildSummary:
    """Run the generic rebuild loop for one descriptor/config pair."""
    if batch_size <= 0:
        raise ValueError("batch_size must be greater than 0")

    inserted_events = 0
    lookback_days = None if system_config.lookback_days == 0 else system_config.lookback_days

    with session_factory() as session:
        results = descriptor.fetch_results(session, lookback_days)
        total_results = len(results)

        calculator = descriptor.create_calculator(system_config)
        system = descriptor.repository.upsert_system(
            session,
            name=system_config.name,
            description=system_config.description,
            config_json=system_config.as_config_json(),
            system_fields={
                "algorithm": descriptor.algorithm,
                "granularity": descriptor.granularity.value,
                "subject": descriptor.subject.value,
            },
        )
        system_id = int(getattr(system, "id"))

        if dry_run:
            for result in results:
                _process_result(calculator, descriptor.process_method, result)

            tracked_entities = _tracked_entity_count(calculator)
            if echo is not None:
                echo(
                    f"[dry-run] config={system_config.file_path.name} "
                    f"algorithm={descriptor.algorithm} "
                    f"granularity={descriptor.granularity.value} "
                    f"subject={descriptor.subject.value} "
                    f"system={system_config.name} "
                    f"processed_results={total_results} "
                    f"tracked_entities={tracked_entities}"
                )
            session.rollback()
            return RebuildSummary(
                algorithm=descriptor.algorithm,
                granularity=descriptor.granularity.value,
                subject=descriptor.subject.value,
                system_name=system_config.name,
                config_file=system_config.file_path.name,
                system_id=system_id,
                processed_results=total_results,
                inserted_events=0,
                tracked_entities=tracked_entities,
                dry_run=True,
            )

        buffered_events: list[Any] = []
        try:
            descriptor.repository.delete_events_for_system(session, system_id)

            for index, result in enumerate(results, start=1):
                buffered_events.extend(_process_result(calculator, descriptor.process_method, result))

                if len(buffered_events) >= batch_size:
                    payload = buffered_events[:]
                    buffered_events.clear()
                    descriptor.repository.insert_events(session, payload, system_id=system_id)
                    inserted_events += len(payload)

                if echo is not None and index % 10_000 == 0:
                    echo(
                        f"config={system_config.file_path.name} "
                        f"algorithm={descriptor.algorithm} "
                        f"granularity={descriptor.granularity.value} "
                        f"subject={descriptor.subject.value} "
                        f"processed_results={index}/{total_results}"
                    )

            if buffered_events:
                payload = buffered_events[:]
                buffered_events.clear()
                descriptor.repository.insert_events(session, payload, system_id=system_id)
                inserted_events += len(payload)

            session.commit()
        except Exception:
            session.rollback()
            raise

        tracked_entities = descriptor.repository.count_tracked_entities(session, system_id=system_id)
        if echo is not None:
            echo(
                "completed "
                f"config={system_config.file_path.name} "
                f"algorithm={descriptor.algorithm} "
                f"granularity={descriptor.granularity.value} "
                f"subject={descriptor.subject.value} "
                f"system={system_config.name} "
                f"system_id={system_id} "
                f"processed_results={total_results} "
                f"inserted_events={inserted_events} "
                f"tracked_entities={tracked_entities}"
            )

        return RebuildSummary(
            algorithm=descriptor.algorithm,
            granularity=descriptor.granularity.value,
            subject=descriptor.subject.value,
            system_name=system_config.name,
            config_file=system_config.file_path.name,
            system_id=system_id,
            processed_results=total_results,
            inserted_events=inserted_events,
            tracked_entities=tracked_entities,
            dry_run=False,
        )


def _process_result(calculator: Any, process_method: str, result: Any) -> list[Any]:
    process_fn = getattr(calculator, process_method)
    events = process_fn(result)
    if isinstance(events, list):
        return events
    return list(events)


def _tracked_entity_count(calculator: Any) -> int:
    if hasattr(calculator, "tracked_entity_count"):
        return int(calculator.tracked_entity_count())
    if hasattr(calculator, "tracked_team_count"):
        return int(calculator.tracked_team_count())
    if hasattr(calculator, "ratings"):
        ratings = calculator.ratings()
        if isinstance(ratings, dict):
            return len(ratings)
    return 0


__all__ = ["RebuildSummary", "rebuild_single_system"]
