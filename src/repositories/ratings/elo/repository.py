"""Persistence helpers for map-level team Elo using SQLAlchemy."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import (
    Float,
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    cast,
    case,
    delete,
    func,
    insert,
    inspect,
    and_,
    or_,
    select,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from models.base import Base
from models.ratings.elo import EloSystem, TeamElo
from domain.ratings.common import TeamMapResult
from domain.ratings.elo.calculator import TeamEloEvent

_metadata = MetaData()

_matches = Table(
    "matches",
    _metadata,
    Column("id", Integer),
    Column("team1_id", Integer),
    Column("team2_id", Integer),
    Column("event_id", Integer),
    Column("format", String),
    Column("status", String),
    Column("date", DateTime(timezone=False)),
    Column("updated_at", DateTime(timezone=False)),
    Column("created_at", DateTime(timezone=False)),
)

_events = Table(
    "events",
    _metadata,
    Column("id", Integer),
    Column("lan", Boolean),
)

_maps = Table(
    "maps",
    _metadata,
    Column("id", Integer),
    Column("match_id", Integer),
    Column("map_number", Integer),
    Column("winner_id", Integer),
    Column("score_team1", Integer),
    Column("score_team2", Integer),
)

_map_player_stats = Table(
    "map_player_stats",
    _metadata,
    Column("map_id", Integer),
    Column("team_id", Integer),
    Column("kills", Integer),
    Column("deaths", Integer),
)

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


def ensure_team_elo_schema(engine: Engine) -> None:
    """Create the team_elo table and its indexes if they do not exist."""
    # team_elo has FKs to existing core tables; reflect those table
    # definitions into metadata first so SQLAlchemy can resolve references.
    with engine.begin() as connection:
        inspector = inspect(connection)
        existing_tables = set(inspector.get_table_names())
        reflect_only = [
            table_name
            for table_name in ["teams", "matches", "maps", "team_elo", "elo_systems"]
            if table_name in existing_tables
        ]
        Base.metadata.reflect(
            bind=connection,
            only=reflect_only,
        )
        EloSystem.__table__.create(bind=connection, checkfirst=True)

        team_elo_exists = inspector.has_table("team_elo")
        if team_elo_exists:
            column_names = {col["name"] for col in inspector.get_columns("team_elo")}
            if "elo_system_id" not in column_names:
                _migrate_legacy_team_elo_schema(connection)

        TeamElo.__table__.create(bind=connection, checkfirst=True)


def _migrate_legacy_team_elo_schema(connection: Any) -> None:
    """Migrate legacy team_elo schema (without elo_system_id) in-place."""
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


def fetch_map_results(session: Session, lookback_days: int | None = 365) -> list[TeamMapResult]:
    """Fetch map outcomes in deterministic chronological order."""
    cutoff_time = None
    if lookback_days is not None and lookback_days > 0:
        cutoff_time = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=lookback_days)

    event_time_expr = func.coalesce(
        _matches.c.date,
        _matches.c.updated_at,
        _matches.c.created_at,
    ).label("event_time")

    conditions = [
        cast(_matches.c.status, String) == "FINISHED",
        _maps.c.winner_id.is_not(None),
        or_(
            _maps.c.winner_id == _matches.c.team1_id,
            _maps.c.winner_id == _matches.c.team2_id,
        ),
    ]
    if cutoff_time is not None:
        conditions.append(event_time_expr >= cutoff_time)

    filtered_maps = (
        select(
            _matches.c.id.label("match_id"),
            _maps.c.id.label("map_id"),
            _maps.c.map_number.label("map_number"),
            event_time_expr,
            _matches.c.team1_id.label("team1_id"),
            _matches.c.team2_id.label("team2_id"),
            _maps.c.winner_id.label("winner_id"),
            _maps.c.score_team1.label("team1_score"),
            _maps.c.score_team2.label("team2_score"),
            func.coalesce(_events.c.lan, False).label("is_lan"),
            cast(_matches.c.format, String).label("match_format"),
        )
        .select_from(_maps.join(_matches, _maps.c.match_id == _matches.c.id).outerjoin(
            _events, _matches.c.event_id == _events.c.id
        ))
        .where(*conditions)
        .cte("filtered_maps")
    )

    from_obj = filtered_maps.outerjoin(
        _map_player_stats,
        _map_player_stats.c.map_id == filtered_maps.c.map_id,
    )

    team1_kills = func.sum(
        case(
            (
                _map_player_stats.c.team_id == filtered_maps.c.team1_id,
                _map_player_stats.c.kills,
            ),
            else_=0,
        )
    )
    team1_deaths = func.sum(
        case(
            (
                _map_player_stats.c.team_id == filtered_maps.c.team1_id,
                _map_player_stats.c.deaths,
            ),
            else_=0,
        )
    )
    team2_kills = func.sum(
        case(
            (
                _map_player_stats.c.team_id == filtered_maps.c.team2_id,
                _map_player_stats.c.kills,
            ),
            else_=0,
        )
    )
    team2_deaths = func.sum(
        case(
            (
                _map_player_stats.c.team_id == filtered_maps.c.team2_id,
                _map_player_stats.c.deaths,
            ),
            else_=0,
        )
    )

    statement = (
        select(
            filtered_maps.c.match_id,
            filtered_maps.c.map_id,
            filtered_maps.c.map_number,
            filtered_maps.c.event_time,
            filtered_maps.c.team1_id,
            filtered_maps.c.team2_id,
            filtered_maps.c.winner_id,
            filtered_maps.c.team1_score,
            filtered_maps.c.team2_score,
            (
                cast(team1_kills, Float)
                / func.nullif(cast(team1_deaths, Float), 0.0)
            ).label("team1_kd_ratio"),
            (
                cast(team2_kills, Float)
                / func.nullif(cast(team2_deaths, Float), 0.0)
            ).label("team2_kd_ratio"),
            filtered_maps.c.is_lan,
            filtered_maps.c.match_format,
        )
        .select_from(from_obj)
        .group_by(
            filtered_maps.c.match_id,
            filtered_maps.c.map_id,
            filtered_maps.c.map_number,
            filtered_maps.c.event_time,
            filtered_maps.c.team1_id,
            filtered_maps.c.team2_id,
            filtered_maps.c.winner_id,
            filtered_maps.c.team1_score,
            filtered_maps.c.team2_score,
            filtered_maps.c.is_lan,
            filtered_maps.c.match_format,
        )
        .order_by(
            filtered_maps.c.event_time,
            filtered_maps.c.match_id,
            filtered_maps.c.map_number,
            filtered_maps.c.map_id,
        )
    )

    rows = session.execute(statement).mappings().all()

    map_results: list[TeamMapResult] = []
    for row in rows:
        event_time = row["event_time"]
        if not isinstance(event_time, datetime):
            raise ValueError(f"map_id={row['map_id']} has invalid event_time={event_time!r}")

        map_results.append(
            TeamMapResult(
                match_id=row["match_id"],
                map_id=row["map_id"],
                map_number=row["map_number"],
                event_time=event_time,
                team1_id=row["team1_id"],
                team2_id=row["team2_id"],
                winner_id=row["winner_id"],
                team1_score=row["team1_score"],
                team2_score=row["team2_score"],
                team1_kd_ratio=(
                    float(row["team1_kd_ratio"]) if row["team1_kd_ratio"] is not None else None
                ),
                team2_kd_ratio=(
                    float(row["team2_kd_ratio"]) if row["team2_kd_ratio"] is not None else None
                ),
                is_lan=bool(row["is_lan"]),
                match_format=row["match_format"],
            )
        )

    return map_results


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
    system = session.execute(select(EloSystem).where(EloSystem.name == name)).scalar_one_or_none()
    if system is None:
        system = EloSystem(
            name=name,
            description=description,
            config_json=config_json,
        )
        session.add(system)
    else:
        system.description = description
        system.config_json = config_json
        system.updated_at = datetime.now(UTC).replace(tzinfo=None)
    session.flush()
    return system


def delete_team_elo_for_system(session: Session, elo_system_id: int) -> None:
    """Delete existing events for a single Elo system."""
    session.execute(delete(TeamElo).where(TeamElo.elo_system_id == elo_system_id))


def insert_team_elo_events(
    session: Session,
    events: Sequence[TeamEloEvent],
    *,
    elo_system_id: int,
) -> None:
    """Bulk insert Elo events."""
    if not events:
        return

    supports_copy = session.info.get("_team_elo_supports_copy")
    if supports_copy is None:
        supports_copy = _supports_copy_bulk_insert(session)
        session.info["_team_elo_supports_copy"] = supports_copy

    if supports_copy:
        _copy_team_elo_events(session, events, elo_system_id=elo_system_id)
        return

    payload = [
        {
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
        for event in events
    ]
    session.execute(insert(TeamElo), payload)


def _supports_copy_bulk_insert(session: Session) -> bool:
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return False

    try:
        raw_connection = session.connection().connection.driver_connection
    except Exception:
        return False

    try:
        with raw_connection.cursor() as cursor:
            return hasattr(cursor, "copy")
    except Exception:
        return False


def _copy_team_elo_events(
    session: Session,
    events: Sequence[TeamEloEvent],
    *,
    elo_system_id: int,
) -> None:
    raw_connection = session.connection().connection.driver_connection
    with raw_connection.cursor() as cursor:
        with cursor.copy(TEAM_ELO_COPY_SQL) as copy:
            for event in events:
                copy.write_row(
                    (
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
                )


def count_tracked_teams(session: Session, *, elo_system_id: int | None = None) -> int:
    """Count teams with at least one Elo event."""
    statement = select(func.count(func.distinct(TeamElo.team_id)))
    if elo_system_id is not None:
        statement = statement.where(TeamElo.elo_system_id == elo_system_id)
    result = session.scalar(statement)
    return int(result or 0)
