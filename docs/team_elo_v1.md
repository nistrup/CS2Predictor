# Team Elo v1 (Map-Level, Team-Only)

This implementation keeps Elo intentionally simple:

- Two tables: `elo_systems` + `team_elo`
- Multiple Elo systems loaded from config files
- One event granularity: map result (win/loss)
- Adjustable data window per system (`lookback_days` in config)
- No `team_elo_current` table

## Config Files

Elo systems are defined as TOML files in:

- `configs/ratings/elo/`

Example (`configs/ratings/elo/default.toml`):

```toml
[system]
name = "team_elo_default"
description = "Pure baseline team Elo (no upset bonus, no BO3/BO5 weighting)"
lookback_days = 365

[elo]
initial_elo = 1500.0
k_factor = 20.0
scale_factor = 400.0
even_multiplier = 1.0
favored_multiplier = 1.0
unfavored_multiplier = 1.0
opponent_strength_weight = 1.0
lan_multiplier = 1.0
round_domination_multiplier = 1.0
kd_ratio_domination_multiplier = 1.0
recency_min_multiplier = 1.0
inactivity_half_life_days = 0.0
bo1_match_multiplier = 1.0
bo3_match_multiplier = 1.0
bo5_match_multiplier = 1.0
```

## Formula

For Team A versus Team B:

```
expected_A = 1 / (1 + 10 ^ ((elo_B - elo_A) / scale_factor))
winner_multiplier = favored_multiplier | unfavored_multiplier | even_multiplier
opponent_strength_factor = opponent_strength_weight ^ ((0.5 - winner_expected_score) / 0.5)
pre_map_elo_A = initial_elo + (prev_elo_A - initial_elo) * 2 ^ (-inactive_days_A / inactivity_half_life_days)
effective_k = k_factor * format_multiplier * winner_multiplier * opponent_strength_factor * lan_factor * round_domination_factor * kd_ratio_domination_factor * recency_factor
delta_A = effective_k * (actual_A - expected_A)
post_elo_A = pre_elo_A + delta_A
```

Where:

- `actual_A` is `1.0` if Team A wins the map, else `0.0`
- `delta_B = -delta_A`
- `winner_multiplier` selection uses pre-map Elo:
  - winner Elo > loser Elo: `favored_multiplier`
  - winner Elo < loser Elo: `unfavored_multiplier`
  - equal Elo: `even_multiplier`
- `opponent_strength_factor` is continuous:
  - uses winner expected score from Elo
  - `opponent_strength_weight=1.0` disables this factor
  - `opponent_strength_weight>1.0` boosts wins against stronger opponents and reduces gains against weaker opponents
- `pre_map_elo` can decay toward `initial_elo` during inactivity:
  - controlled by `inactivity_half_life_days`
  - `0.0` disables inactivity decay
  - with a positive half-life, larger inactivity gaps shrink rating deviation from baseline before the next map
- `lan_factor` is `lan_multiplier` when the match is LAN, otherwise `1.0`
- `round_domination_factor` scales map impact by scoreline:
  - based on winner round share (for example, `13-0` > `13-11`)
- `kd_ratio_domination_factor` scales map impact by winner vs loser K/D ratio gap
- `round_domination_multiplier=1.0` disables round-score dominance
- `kd_ratio_domination_multiplier=1.0` disables K/D-ratio dominance
- `recency_factor` applies linear decay inside the lookback window:
  - at age `0 days`: `1.0`
  - at age `lookback_days`: `recency_min_multiplier`
  - `recency_min_multiplier=1.0` disables decay; `0.0` means oldest maps contribute `0`
- `format_multiplier` defaults: `BO1=1.0`, `BO3=1.0`, `BO5=1.0`
- defaults: `initial_elo=1500`, `k_factor=20`, `scale_factor=400`, `even_multiplier=1.0`, `favored_multiplier=1.0`, `unfavored_multiplier=1.0`, `opponent_strength_weight=1.0`, `lan_multiplier=1.0`, `round_domination_multiplier=1.0`, `kd_ratio_domination_multiplier=1.0`, `recency_min_multiplier=1.0`, `inactivity_half_life_days=0.0`, `bo1_match_multiplier=1.0`, `bo3_match_multiplier=1.0`, `bo5_match_multiplier=1.0`

## Table Shape

`elo_systems` stores configuration snapshots:

- `id`, `name`, `description`, `config_json`, timestamps

`team_elo` stores one row per team per map:

- `elo_system_id`
- `team_id`, `opponent_team_id`
- `match_id`, `map_id`, `map_number`, `event_time`
- `won`, `actual_score`, `expected_score`
- `pre_elo`, `elo_delta`, `post_elo`
- constants used at calculation time: `k_factor`, `scale_factor`, `initial_elo`

Important constraints:

- `UNIQUE (elo_system_id, team_id, map_id)` to prevent duplicate rows per system
- `actual_score` restricted to `0.0` or `1.0`
- `expected_score` restricted to `[0.0, 1.0]`

## Rebuild CLI

CLI path:

- `scripts/rebuild_ratings.py`

Script framework:

- `Typer` CLI
- `SQLAlchemy` ORM/Core
- `psycopg` PostgreSQL driver

The CLI command:

1. Creates `team_elo` if it does not exist.
2. Loads all `*.toml` files from `configs/ratings/elo/`.
3. For each config, reads finished maps in chronological order from `matches` + `maps` using that config's `lookback_days`.
4. Upserts a row in `elo_systems` using the config name + payload.
5. Recomputes Elo deterministically from scratch.
6. Replaces rows only for that `elo_system_id` in `team_elo` (other systems are kept for side-by-side comparisons).

Map ordering:

1. `COALESCE(matches.date, matches.updated_at, matches.created_at)`
2. `matches.id`
3. `maps.map_number`
4. `maps.id`

## Run

Use the project venv:

```bash
venv/bin/pip install -r requirements.txt
venv/bin/python scripts/rebuild_ratings.py rebuild elo --granularity map --subject team
```

Optional arguments:

```bash
venv/bin/python scripts/rebuild_ratings.py rebuild elo \
  --granularity map \
  --subject team \
  --config-dir configs/ratings/elo \
  --config-name default.toml \
  --batch-size 5000
```

Dry run:

```bash
venv/bin/python scripts/rebuild_ratings.py rebuild elo --granularity map --subject team --dry-run
```

Show top teams with inactivity filter (example: require at least 1 map in last 90 days):

```bash
venv/bin/python scripts/show_team_elo_top.py \
  --system-name team_elo_default \
  --top-n 20 \
  --active-window-days 90 \
  --min-recent-maps 1
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
WHERE elo_system_id = :elo_system_id
ORDER BY team_id, event_time DESC, map_id DESC;
```

List Elo systems:

```sql
SELECT id, name, description, created_at, updated_at
FROM elo_systems
ORDER BY id;
```
