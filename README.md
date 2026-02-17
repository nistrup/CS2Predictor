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
- `scripts/`: executable scripts for backfills and data jobs.
- `tests/`: unit tests for core calculation logic.
- `docs/`: design and reference documentation.
- `pyproject.toml`: packaging and tool configuration.

## Team Elo v1

Team Elo v1 is implemented as a map-level, team-only Elo calculation with system versioning:

- `elo_systems` (stores config per Elo system)
- `team_elo` (stores events keyed by `elo_system_id`)
- file-based system configs in `configs/elo_systems/*.toml`

Implementation docs:

- `docs/team_elo_v1.md`

Quick start:

```bash
venv/bin/pip install -r requirements.txt
venv/bin/python scripts/rebuild_team_elo.py
```

Run a single config file:

```bash
venv/bin/python scripts/rebuild_team_elo.py --config-name default.toml
```

Run tests:

```bash
venv/bin/pip install -r requirements-dev.txt
venv/bin/pytest
```
