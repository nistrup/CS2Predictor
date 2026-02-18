"""One-off migration for legacy team_elo table (without elo_system_id)."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection


def migrate_legacy_team_elo_schema(connection: Connection) -> None:
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
