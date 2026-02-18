# Team Glicko-2 v1 (Map-Level, Team-Only)

This implementation adds a map-level team Glicko-2 pipeline parallel to Team Elo.

- Two tables: `glicko2_systems` + `team_glicko2`
- Multiple systems loaded from config files
- One event granularity: map result (win/loss)
- Adjustable data window per system (`lookback_days` in config)

## Config Files

Glicko-2 systems are defined as TOML files in:

- `configs/ratings/glicko2/`

Example (`configs/ratings/glicko2/default.toml`):

```toml
[system]
name = "team_glicko2_default"
description = "Baseline map-level team Glicko-2"
lookback_days = 365

[glicko2]
initial_rating = 1500.0
initial_rd = 350.0
initial_volatility = 0.06
tau = 0.5
rating_period_days = 1.0
min_rd = 30.0
max_rd = 350.0
epsilon = 0.000001
```

## Formula

For one map (one Glicko-2 rating period with one opponent):

```
mu = (rating - 1500) / 173.7178
phi = rd / 173.7178
g(phi_j) = 1 / sqrt(1 + 3 * phi_j^2 / pi^2)
E = 1 / (1 + exp(-g(phi_j) * (mu - mu_j)))
v = 1 / (g(phi_j)^2 * E * (1 - E))
delta = v * g(phi_j) * (score - E)
```

Volatility (`sigma`) is updated by the iterative method from the Glicko-2 paper using `tau` and `epsilon`, then:

```
phi* = sqrt(phi^2 + sigma'^2)
phi' = 1 / sqrt(1 / phi*^2 + 1 / v)
mu' = mu + phi'^2 * g(phi_j) * (score - E)
```

Converted back:

```
rating' = 173.7178 * mu' + 1500
rd' = 173.7178 * phi'
```

Inactivity handling:

- before each map, RD inflates based on elapsed time since the team's last map
- `inactive_periods = inactive_days / rating_period_days`
- `phi_pre = sqrt(phi_prev^2 + sigma_prev^2 * inactive_periods)`
- `rd` is then clamped to `[min_rd, max_rd]`

## Tunable Parameters

- `initial_rating`: starting rating for unseen teams.
- `initial_rd`: starting rating deviation (uncertainty).
- `initial_volatility`: starting volatility.
- `tau`: volatility dynamics constraint (higher allows faster volatility movement).
- `rating_period_days`: conversion from elapsed days to Glicko-2 inactivity periods.
- `min_rd`, `max_rd`: RD clamp bounds after inactivity/update.
- `epsilon`: convergence threshold for volatility root solving.
- `lookback_days`: input map window; `0` means all-time.

Validation:

- `lookback_days >= 0`
- `initial_rating > 0`
- `initial_rd > 0` and between `min_rd`/`max_rd`
- `initial_volatility > 0`
- `tau > 0`
- `rating_period_days > 0`
- `min_rd > 0`, `max_rd > 0`, and `min_rd <= max_rd`
- `epsilon > 0`

## Table Shape

`glicko2_systems` stores configuration snapshots:

- `id`, `name`, `description`, `config_json`, timestamps

`team_glicko2` stores one row per team per map:

- `glicko2_system_id`
- `team_id`, `opponent_team_id`
- `match_id`, `map_id`, `map_number`, `event_time`
- `won`, `actual_score`, `expected_score`
- `pre_rating`, `pre_rd`, `pre_volatility`
- `rating_delta`, `rd_delta`, `volatility_delta`
- `post_rating`, `post_rd`, `post_volatility`
- constants used at calculation time: `tau`, `rating_period_days`, `initial_rating`, `initial_rd`, `initial_volatility`

Important constraints:

- `UNIQUE (glicko2_system_id, team_id, map_id)`
- `actual_score` restricted to `0.0` or `1.0`
- `expected_score` restricted to `[0.0, 1.0]`

## Rebuild Script

- `scripts/rebuild_ratings.py`

The script:

1. Creates `glicko2_systems` and `team_glicko2` if needed.
2. Loads all `*.toml` files from `configs/ratings/glicko2/`.
3. For each config, reads finished maps in chronological order using that config's `lookback_days`.
4. Upserts a row in `glicko2_systems`.
5. Recomputes ratings deterministically from scratch.
6. Replaces rows only for that `glicko2_system_id`.

## Run

```bash
venv/bin/pip install -r requirements.txt
venv/bin/python scripts/rebuild_ratings.py rebuild glicko2 --granularity map --subject team
```

Single config:

```bash
venv/bin/python scripts/rebuild_ratings.py rebuild glicko2 --granularity map --subject team --config-name default.toml
```

Dry run:

```bash
venv/bin/python scripts/rebuild_ratings.py rebuild glicko2 --granularity map --subject team --dry-run
```

Show top teams:

```bash
venv/bin/python scripts/show_team_top.py glicko2 \
  --system-name team_glicko2_default \
  --top-n 20 \
  --active-window-days 90 \
  --min-recent-maps 1
```
