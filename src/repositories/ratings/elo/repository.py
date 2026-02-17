"""Persistence helpers for map-level team Elo."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from domain.ratings.elo.calculator import TeamEloEvent
from models.ratings.elo import EloSystem, TeamElo
from repositories.ratings.base import BaseRatingRepository
from repositories.ratings.common import fetch_map_results

TEAM_ELO_COPY_SQL = """
    COPY team_elo (
        elo_system_id,
        team_id,
        opponent_team_id,
        match_id,
        map_id,
        map_number,
        event_time,
        won,
        actual_score,
        expected_score,
        pre_elo,
        elo_delta,
        post_elo,
        k_factor,
        scale_factor,
        initial_elo
    ) FROM STDIN
"""


def _team_elo_event_to_row(event: TeamEloEvent, elo_system_id: int) -> dict[str, Any]:
    return {
        "elo_system_id": elo_system_id,
        "team_id": event.team_id,
        "opponent_team_id": event.opponent_team_id,
        "match_id": event.match_id,
        "map_id": event.map_id,
        "map_number": event.map_number,
        "event_time": event.event_time,
        "won": event.won,
        "actual_score": event.actual_score,
        "expected_score": event.expected_score,
        "pre_elo": event.pre_elo,
        "elo_delta": event.elo_delta,
        "post_elo": event.post_elo,
        "k_factor": event.k_factor,
        "scale_factor": event.scale_factor,
        "initial_elo": event.initial_elo,
    }


def _team_elo_event_to_copy_row(event: TeamEloEvent, elo_system_id: int) -> tuple[Any, ...]:
    return (
        elo_system_id,
        event.team_id,
        event.opponent_team_id,
        event.match_id,
        event.map_id,
        event.map_number,
        event.event_time,
        event.won,
        event.actual_score,
        event.expected_score,
        event.pre_elo,
        event.elo_delta,
        event.post_elo,
        event.k_factor,
        event.scale_factor,
        event.initial_elo,
    )


def _migrate_legacy_team_elo_schema(connection: Connection) -> None:
    """Migrate legacy team_elo schema (without elo_system_id) in-place."""
    inspector = inspect(connection)
    if not inspector.has_table("team_elo"):
        return

    column_names = {column["name"] for column in inspector.get_columns("team_elo")}
    if "elo_system_id" in column_names:
        return

    connection.execute(
        text(
            """
            INSERT INTO elo_systems (name, description, config_json)
            VALUES (:name, :description, '{}'::jsonb)
            ON CONFLICT (name) DO NOTHING
            """
        ),
        {
            "name": "legacy_default",
            "description": "Auto-created during migration from single-system team_elo.",
        },
    )
    legacy_system_id = connection.execute(
        text("SELECT id FROM elo_systems WHERE name = :name"),
        {"name": "legacy_default"},
    ).scalar_one()

    connection.execute(text("ALTER TABLE team_elo ADD COLUMN IF NOT EXISTS elo_system_id BIGINT"))
    connection.execute(
        text("UPDATE team_elo SET elo_system_id = :elo_system_id WHERE elo_system_id IS NULL"),
        {"elo_system_id": legacy_system_id},
    )
    connection.execute(text("ALTER TABLE team_elo ALTER COLUMN elo_system_id SET NOT NULL"))

    connection.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'team_elo_elo_system_id_fkey'
                ) THEN
                    ALTER TABLE team_elo
                    ADD CONSTRAINT team_elo_elo_system_id_fkey
                    FOREIGN KEY (elo_system_id) REFERENCES elo_systems(id);
                END IF;
            END$$;
            """
        )
    )

    connection.execute(text("ALTER TABLE team_elo DROP CONSTRAINT IF EXISTS uq_team_elo_team_map"))
    connection.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_team_elo_system_team_map'
                ) THEN
                    ALTER TABLE team_elo
                    ADD CONSTRAINT uq_team_elo_system_team_map
                    UNIQUE (elo_system_id, team_id, map_id);
                END IF;
            END$$;
            """
        )
    )

    connection.execute(
        text("CREATE INDEX IF NOT EXISTS idx_team_elo_system ON team_elo (elo_system_id)")
    )
    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS idx_team_elo_system_team_event
            ON team_elo (elo_system_id, team_id, event_time, map_id)
            """
        )
    )


TEAM_ELO_REPOSITORY = BaseRatingRepository[EloSystem, TeamElo, TeamEloEvent](
    system_model=EloSystem,
    event_model=TeamElo,
    system_id_column="elo_system_id",
    entity_id_column="team_id",
    event_to_row=_team_elo_event_to_row,
    copy_sql=TEAM_ELO_COPY_SQL,
    event_to_copy_row=_team_elo_event_to_copy_row,
    reflect_tables=("teams", "matches", "maps", "team_elo", "elo_systems"),
    schema_migration=_migrate_legacy_team_elo_schema,
)


def ensure_team_elo_schema(engine: Engine) -> None:
    """Create the team_elo schema and indexes if they do not exist."""
    TEAM_ELO_REPOSITORY.ensure_schema(engine)


def truncate_team_elo(session: Session) -> None:
    """Hard-reset table contents before a full deterministic rebuild."""
    session.execute(text("TRUNCATE TABLE team_elo RESTART IDENTITY"))


def upsert_elo_system(
    session: Session,
    *,
    name: str,
    description: str | None,
    config_json: dict[str, Any],
) -> EloSystem:
    """Create or update an Elo system definition."""
    return cast(
        EloSystem,
        TEAM_ELO_REPOSITORY.upsert_system(
            session,
            name=name,
            description=description,
            config_json=config_json,
        ),
    )


def delete_team_elo_for_system(session: Session, elo_system_id: int) -> None:
    """Delete existing events for a single Elo system."""
    TEAM_ELO_REPOSITORY.delete_events_for_system(session, elo_system_id)


def insert_team_elo_events(
    session: Session,
    events: Sequence[TeamEloEvent],
    *,
    elo_system_id: int,
) -> None:
    """Bulk insert Elo events."""
    TEAM_ELO_REPOSITORY.insert_events(session, events, system_id=elo_system_id)


def count_tracked_teams(session: Session, *, elo_system_id: int | None = None) -> int:
    """Count teams with at least one Elo event."""
    return TEAM_ELO_REPOSITORY.count_tracked_entities(session, system_id=elo_system_id)
