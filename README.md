# CS2Predictor

CS2Predictor is a modeling project built on top of `CS2Data`.
Its goal is to predict the winner of a Counter-Strike 2 matchup and explain as much variance in that outcome as possible through:

- feature engineering
- domain heuristics
- data science and statistical modeling

## Scope

- Build win-prediction models for **pre-game** scenarios.
- Build win-prediction models for **mid-game (live)** scenarios.
- Prioritize interpretable signals and measurable predictive lift.

## Data Source

Raw data is scraped and maintained in the separate `CS2Data` repository.

- Data model reference: `docs/data_model.md`
- Local database URL (SQLAlchemy psycopg):  
  `postgresql+psycopg://postgres:postgres@localhost:5432/cs2predictor`

## Target Variable

Primary target: **winner of a given matchup** (team A vs team B), for both pre-game and mid-game prediction contexts.

## Initial Project Direction

1. Define modeling datasets from the CS2Data schema.
2. Engineer match-, map-, lineup-, and player-level features.
3. Train and evaluate baseline and advanced models.
4. Compare pre-game vs mid-game performance and calibration.

## Project Structure

- `src/`: Python package code (core logic and repositories).
- `src/domain/`: rating-system modules grouped by algorithm (`elo`, `glicko2`, `openskill`) plus shared types.
- `src/models/`: ORM models including unified rating persistence (`rating_systems`, `team_ratings`).
- `src/repositories/`: unified persistence layer and shared repository helpers.
- `scripts/`: executable scripts for backfills and data jobs.
- `tests/`: unit tests for core calculation logic.
- `docs/`: design and reference documentation.
- `pyproject.toml`: packaging and tool configuration.

## Team Elo v1

Team Elo v1 is a map-level, team-only Elo system with per-system versioning and many tunable parameters.

- `rating_systems`: stores each system definition and config snapshot (algorithm/granularity/subject scoped).
- `team_ratings`: stores one row per team per map, keyed by `rating_system_id`.
- `configs/ratings/elo/*.toml`: file-based Elo system definitions.

Implementation docs:

- `docs/team_elo_v1.md`

### Config shape

Each Elo system config has a `[system]` section and an `[elo]` section:

```toml
[system]
name = "team_elo_default"
description = "Pure baseline team Elo"
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

### Tunable parameters

- `lookback_days`: time window for input maps (`0` means all-time).
- `initial_elo`: starting rating and inactivity baseline.
- `k_factor`: base Elo update size before multipliers.
- `scale_factor`: expected-score curve width (higher means slower expected-score change per Elo gap).
- `even_multiplier`: applies when winner and loser had equal pre-map Elo.
- `favored_multiplier`: applies when higher-rated team wins.
- `unfavored_multiplier`: applies when lower-rated team wins.
- `opponent_strength_weight`: continuous upset/favorite adjustment (`1.0` disables).
- `lan_multiplier`: extra weight on LAN matches (`is_lan=true`).
- `round_domination_multiplier`: scales by winner round-share dominance (`1.0` disables).
- `kd_ratio_domination_multiplier`: scales by winner-loser K/D ratio gap (`1.0` disables).
- `recency_min_multiplier`: floor for linear recency weighting inside `lookback_days` (`1.0` disables).
- `inactivity_half_life_days`: decays ratings toward `initial_elo` between maps (`0.0` disables).
- `bo1_match_multiplier`, `bo3_match_multiplier`, `bo5_match_multiplier`: format-specific scaling.

Validation rules:

- All multipliers and core Elo constants must be `> 0`, except:
- `lookback_days >= 0`
- `inactivity_half_life_days >= 0`
- `recency_min_multiplier` must be in `[0, 1]`

### Rebuild and inspect

Install dependencies and rebuild all configured systems:

```bash
venv/bin/pip install -r requirements.txt
venv/bin/python scripts/rebuild_ratings.py rebuild elo --granularity map --subject team
```

Run a single config:

```bash
venv/bin/python scripts/rebuild_ratings.py rebuild elo --granularity map --subject team --config-name default.toml
```

Dry run (compute without writing to `team_ratings`):

```bash
venv/bin/python scripts/rebuild_ratings.py rebuild elo --granularity map --subject team --dry-run
```

Show top teams for one Elo system, filtering inactive teams:

```bash
venv/bin/python scripts/show_team_top.py elo \
  --system-name team_elo_default \
  --top-n 20 \
  --active-window-days 90 \
  --min-recent-maps 1
```

Tune by creating a new config file under `configs/ratings/elo/` (for example by copying `default.toml`), adjusting parameters, then rebuilding that config with `--config-name`. Automated hyperparameter tuning is intentionally deferred for now.

## Team Glicko-2 v1

Team Glicko-2 v1 is implemented in parallel to Elo for side-by-side comparison.

- `rating_systems`: stores each Glicko-2 system definition and config snapshot.
- `team_ratings`: stores Glicko-2 events in unified form, keyed by `rating_system_id`.
- `configs/ratings/glicko2/*.toml`: file-based Glicko-2 system definitions.

Implementation docs:

- `docs/team_glicko2_v1.md`

Quick start:

```bash
venv/bin/python scripts/rebuild_ratings.py rebuild glicko2 --granularity map --subject team
```

Run a single config:

```bash
venv/bin/python scripts/rebuild_ratings.py rebuild glicko2 --granularity map --subject team --config-name default.toml
```

Show top teams for one Glicko-2 system, filtering inactive teams:

```bash
venv/bin/python scripts/show_team_top.py glicko2 \
  --system-name team_glicko2_default \
  --top-n 20 \
  --active-window-days 90 \
  --min-recent-maps 1
```

Tune by creating a new config file under `configs/ratings/glicko2/` (for example by copying `default.toml`), adjusting parameters, then rebuilding that config with `--config-name`.

## Team OpenSkill v1

Team OpenSkill v1 is implemented in parallel to Elo/Glicko-2 using the OpenSkill Plackett-Luce model.

- `rating_systems`: stores each OpenSkill system definition and config snapshot.
- `team_ratings`: stores OpenSkill events in unified form, keyed by `rating_system_id`.
- `configs/ratings/openskill/*.toml`: file-based OpenSkill system definitions.

Implementation docs:

- `docs/team_openskill_v1.md`

Quick start:

```bash
venv/bin/python scripts/rebuild_ratings.py rebuild openskill --granularity map --subject team
```

Run a single config:

```bash
venv/bin/python scripts/rebuild_ratings.py rebuild openskill --granularity map --subject team --config-name default.toml
```

Show top teams for one OpenSkill system, filtering inactive teams:

```bash
venv/bin/python scripts/show_team_top.py openskill \
  --system-name team_openskill_default \
  --top-n 20 \
  --active-window-days 90 \
  --min-recent-maps 1
```

Tune by creating a new config file under `configs/ratings/openskill/` (for example by copying `default.toml`), adjusting parameters, then rebuilding that config with `--config-name`.

Run tests:

```bash
venv/bin/pip install -r requirements-dev.txt
venv/bin/pytest
```
