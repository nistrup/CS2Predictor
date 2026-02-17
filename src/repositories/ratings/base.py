"""Generic persistence scaffold for rating repositories."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from sqlalchemy import delete, func, insert, inspect, select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from models.base import Base

SystemModelT = TypeVar("SystemModelT")
EventModelT = TypeVar("EventModelT")
DomainEventT = TypeVar("DomainEventT")


class BaseRatingRepository(Generic[SystemModelT, EventModelT, DomainEventT]):
    """Reusable persistence operations shared across rating systems."""

    def __init__(
        self,
        *,
        system_model: type[SystemModelT],
        event_model: type[EventModelT],
        system_id_column: str,
        entity_id_column: str,
        event_to_row: Callable[[DomainEventT, int], dict[str, Any]],
        copy_sql: str | None = None,
        event_to_copy_row: Callable[[DomainEventT, int], tuple[Any, ...]] | None = None,
        reflect_tables: Sequence[str] = (),
        schema_migration: Callable[[Connection], None] | None = None,
    ) -> None:
        self.system_model = system_model
        self.event_model = event_model
        self.system_id_column = system_id_column
        self.entity_id_column = entity_id_column
        self.event_to_row = event_to_row
        self.copy_sql = copy_sql
        self.event_to_copy_row = event_to_copy_row
        self.reflect_tables = tuple(reflect_tables)
        self.schema_migration = schema_migration
        event_table_name = getattr(self.event_model, "__tablename__", "events")
        self._copy_support_cache_key = f"_{event_table_name}_supports_copy"

    def ensure_schema(self, engine: Engine) -> None:
        """Create required tables and indexes when missing."""
        with engine.begin() as connection:
            inspector = inspect(connection)
            existing_tables = set(inspector.get_table_names())
            reflect_only = [table for table in self.reflect_tables if table in existing_tables]
            if reflect_only:
                Base.metadata.reflect(bind=connection, only=reflect_only)

            system_table = getattr(self.system_model, "__table__")
            event_table = getattr(self.event_model, "__table__")
            system_table.create(bind=connection, checkfirst=True)
            if self.schema_migration is not None:
                self.schema_migration(connection)
            event_table.create(bind=connection, checkfirst=True)

    def upsert_system(
        self,
        session: Session,
        *,
        name: str,
        description: str | None,
        config_json: dict[str, Any],
    ) -> SystemModelT:
        """Create or update the system metadata row."""
        name_column = getattr(self.system_model, "name")
        system = session.execute(select(self.system_model).where(name_column == name)).scalar_one_or_none()
        if system is None:
            system = self.system_model(  # type: ignore[call-arg]
                name=name,
                description=description,
                config_json=config_json,
            )
            session.add(system)
        else:
            setattr(system, "description", description)
            setattr(system, "config_json", config_json)
            if hasattr(system, "updated_at"):
                setattr(system, "updated_at", datetime.now(UTC).replace(tzinfo=None))
        session.flush()
        return system

    def delete_events_for_system(self, session: Session, system_id: int) -> None:
        """Delete historical events for one system."""
        system_column = getattr(self.event_model, self.system_id_column)
        session.execute(delete(self.event_model).where(system_column == system_id))

    def insert_events(self, session: Session, events: Sequence[DomainEventT], *, system_id: int) -> None:
        """Bulk insert domain events using COPY on supported Postgres drivers."""
        if not events:
            return

        if self._supports_copy_bulk_insert(session):
            self._copy_events(session, events, system_id=system_id)
            return

        payload = [self.event_to_row(event, system_id) for event in events]
        session.execute(insert(self.event_model), payload)

    def count_tracked_entities(self, session: Session, *, system_id: int | None = None) -> int:
        """Count distinct rated entities for one system or all systems."""
        entity_column = getattr(self.event_model, self.entity_id_column)
        statement = select(func.count(func.distinct(entity_column)))

        if system_id is not None:
            system_column = getattr(self.event_model, self.system_id_column)
            statement = statement.where(system_column == system_id)

        result = session.scalar(statement)
        return int(result or 0)

    def _supports_copy_bulk_insert(self, session: Session) -> bool:
        if self.copy_sql is None or self.event_to_copy_row is None:
            return False

        cached_value = session.info.get(self._copy_support_cache_key)
        if cached_value is not None:
            return bool(cached_value)

        bind = session.get_bind()
        if bind is None or bind.dialect.name != "postgresql":
            session.info[self._copy_support_cache_key] = False
            return False

        try:
            raw_connection = session.connection().connection.driver_connection
        except Exception:
            session.info[self._copy_support_cache_key] = False
            return False

        try:
            with raw_connection.cursor() as cursor:
                supports_copy = hasattr(cursor, "copy")
        except Exception:
            supports_copy = False

        session.info[self._copy_support_cache_key] = supports_copy
        return supports_copy

    def _copy_events(
        self,
        session: Session,
        events: Sequence[DomainEventT],
        *,
        system_id: int,
    ) -> None:
        if self.copy_sql is None or self.event_to_copy_row is None:
            raise RuntimeError("COPY not configured for this repository")

        raw_connection = session.connection().connection.driver_connection
        with raw_connection.cursor() as cursor:
            with cursor.copy(self.copy_sql) as copy:
                for event in events:
                    copy.write_row(self.event_to_copy_row(event, system_id))
