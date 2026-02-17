# Team OpenSkill v1 (Map-Level, Team-Only)

This implementation adds a map-level team OpenSkill pipeline parallel to Elo and Glicko-2.

- Two tables: `openskill_systems` + `team_openskill`
- Multiple systems loaded from config files
- One event granularity: map result (win/loss)
- Adjustable data window per system (`lookback_days` in config)

## Config Files

OpenSkill systems are defined as TOML files in:

- `configs/ratings/openskill/`

Example (`configs/ratings/openskill/default.toml`):

```toml
[system]
name = "team_openskill_default"
description = "Baseline map-level OpenSkill (Plackett-Luce)"
lookback_days = 365

[openskill]
initial_mu = 25.0
initial_sigma = 8.333333333333334
beta = 4.166666666666667
kappa = 0.0001
tau = 0.08333333333333333
limit_sigma = false
balance = false
ordinal_z = 3.0
```

## Formula

Model: OpenSkill Plackett-Luce (`openskill` v6).

For each map, two single-player teams are rated:

- Team 1: `[rating_team1]`
- Team 2: `[rating_team2]`

Expected score is from:

- `model.predict_win([[team1], [team2]])`

Update is from:

- `model.rate([[team1], [team2]], ranks=[1, 2])` for team1 win
- `model.rate([[team1], [team2]], ranks=[2, 1])` for team2 win

Conservative rating (used for ranking output) is:

- `ordinal = rating.ordinal(z=ordinal_z)`

## Tunable Parameters

- `initial_mu`: starting mean for unseen teams.
- `initial_sigma`: starting uncertainty for unseen teams.
- `beta`: performance variance scale.
- `kappa`: additive dynamics term for numerical stability.
- `tau`: additive dynamics to sigma on each update.
- `limit_sigma`: if true, keeps sigma from increasing after updates.
- `balance`: enables balanced pairwise weighting behavior in OpenSkill.
- `ordinal_z`: z-score used for conservative `ordinal` ranking.
- `lookback_days`: input map window; `0` means all-time.

Validation:

- `lookback_days >= 0`
- `initial_mu > 0`
- `initial_sigma > 0`
- `beta > 0`
- `kappa > 0`
- `tau > 0`
- `ordinal_z > 0`
- `limit_sigma` and `balance` must be booleans

## Table Shape

`openskill_systems` stores configuration snapshots:

- `id`, `name`, `description`, `config_json`, timestamps

`team_openskill` stores one row per team per map:

- `openskill_system_id`
- `team_id`, `opponent_team_id`
- `match_id`, `map_id`, `map_number`, `event_time`
- `won`, `actual_score`, `expected_score`
- `pre_mu`, `pre_sigma`, `pre_ordinal`
- `mu_delta`, `sigma_delta`, `ordinal_delta`
- `post_mu`, `post_sigma`, `post_ordinal`
- constants used at calculation time: `beta`, `kappa`, `tau`, `limit_sigma`, `balance`, `ordinal_z`, `initial_mu`, `initial_sigma`

Important constraints:

- `UNIQUE (openskill_system_id, team_id, map_id)`
- `actual_score` restricted to `0.0` or `1.0`
- `expected_score` restricted to `[0.0, 1.0]`

## Rebuild Script

- `scripts/rebuild_ratings.py`

The script:

1. Creates `openskill_systems` and `team_openskill` if needed.
2. Loads all `*.toml` files from `configs/ratings/openskill/`.
3. For each config, reads finished maps in chronological order using that config's `lookback_days`.
4. Upserts a row in `openskill_systems`.
5. Recomputes ratings deterministically from scratch.
6. Replaces rows only for that `openskill_system_id`.

## Run

```bash
venv/bin/pip install -r requirements.txt
venv/bin/python scripts/rebuild_ratings.py rebuild openskill --granularity map --subject team
```

Single config:

```bash
venv/bin/python scripts/rebuild_ratings.py rebuild openskill --granularity map --subject team --config-name default.toml
```

Dry run:

```bash
venv/bin/python scripts/rebuild_ratings.py rebuild openskill --granularity map --subject team --dry-run
```

Show top teams:

```bash
venv/bin/python scripts/show_team_openskill_top.py \
  --system-name team_openskill_default \
  --top-n 20 \
  --active-window-days 90 \
  --min-recent-maps 1
```
