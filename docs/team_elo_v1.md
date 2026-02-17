# Team Elo v1 (Map-Level, Team-Only)

This implementation keeps Elo intentionally simple:

- One table: `team_elo`
- One Elo system
- One event granularity: map result (win/loss)
- No `team_elo_current` table

## Formula

For Team A versus Team B:

```
expected_A = 1 / (1 + 10 ^ ((elo_B - elo_A) / scale_factor))
delta_A = k_factor * (actual_A - expected_A)
post_elo_A = pre_elo_A + delta_A
```

Where:

- `actual_A` is `1.0` if Team A wins the map, else `0.0`
- `delta_B = -delta_A`
- defaults: `initial_elo=1500`, `k_factor=20`, `scale_factor=400`

## Table Shape

`team_elo` stores one row per team per map:

- `team_id`, `opponent_team_id`
- `match_id`, `map_id`, `map_number`, `event_time`
- `won`, `actual_score`, `expected_score`
- `pre_elo`, `elo_delta`, `post_elo`
- constants used at calculation time: `k_factor`, `scale_factor`, `initial_elo`

Important constraints:

- `UNIQUE (team_id, map_id)` to prevent duplicate team-map rows
- `actual_score` restricted to `0.0` or `1.0`
- `expected_score` restricted to `[0.0, 1.0]`

## Rebuild Script

Script path:

- `scripts/rebuild_team_elo.py`

Script framework:

- `Typer` CLI
- `SQLAlchemy` ORM/Core
- `psycopg` PostgreSQL driver

The script:

1. Creates `team_elo` if it does not exist.
2. Reads finished maps in chronological order from `matches` + `maps`.
3. Recomputes Elo deterministically from scratch.
4. Truncates and repopulates `team_elo`.

Map ordering:

1. `COALESCE(matches.date, matches.updated_at, matches.created_at)`
2. `matches.id`
3. `maps.map_number`
4. `maps.id`

## Run

Use the project venv:

```bash
venv/bin/pip install -r requirements.txt
venv/bin/python scripts/rebuild_team_elo.py rebuild
```

Optional arguments:

```bash
venv/bin/python scripts/rebuild_team_elo.py rebuild \
  --k-factor 20 \
  --initial-elo 1500 \
  --scale-factor 400 \
  --batch-size 5000
```

Dry run:

```bash
venv/bin/python scripts/rebuild_team_elo.py rebuild --dry-run
```

Database URL:

1. Defaults to:
   `postgresql+psycopg://postgres:postgres@localhost:5432/cs2predictor`
2. Override with `--db-url` when needed.

## Query Current Elo (without a current table)

```sql
SELECT DISTINCT ON (team_id)
    team_id,
    post_elo AS current_elo,
    event_time,
    map_id
FROM team_elo
ORDER BY team_id, event_time DESC, map_id DESC;
```
