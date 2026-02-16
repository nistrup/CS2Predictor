# CS2Data Data Model (Live PostgreSQL Snapshot)

This document reflects the current database by querying PostgreSQL directly, not only ORM declarations.

## Snapshot Metadata

- Database: `CS2Data`
- User: `postgres`
- Snapshot timestamp (UTC): `2026-02-16T16:30:14.745952+00:00`
- Note: row counts can change during active scraping/backfill runs.
- IDs are application-managed HLTV IDs for core entities/matches/maps, while PostgreSQL columns currently have sequence defaults (for example, `nextval(...)`).

## Tables and Row Counts

| Table | Rows |
|---|---:|
| `teams` | 6,373 |
| `players` | 15,761 |
| `events` | 6,114 |
| `matches` | 80,454 |
| `maps` | 153,046 |
| `match_lineups` | 803,166 |
| `map_vetos` | 485,169 |
| `match_player_stats` | 781,734 |
| `map_player_stats` | 4,592,794 |
| `map_rounds` | 3,807,368 |

## Enum Types (from `pg_enum`)

- `eventtier`: `MAJOR`, `S_TIER`, `A_TIER`, `B_TIER`, `C_TIER`, `QUALIFIER`, `REGIONAL`
- `mapname`: `MIRAGE`, `INFERNO`, `NUKE`, `ANUBIS`, `ANCIENT`, `VERTIGO`, `DUST2`, `OVERPASS`, `TRAIN`, `COBBLESTONE`, `CACHE`, `TUSCAN`, `TBA`, `DEFAULT`, `UNKNOWN`
- `matchformat`: `BO1`, `BO3`, `BO5`
- `matchstatus`: `UPCOMING`, `LIVE`, `FINISHED`, `CANCELLED`, `POSTPONED`
- `playerrole`: `RIFLER`, `AWP`, `IGL`, `SUPPORT`, `ENTRY`, `LURKER`
- `region`: `EUROPE`, `AMERICAS`, `ASIA`, `OCEANIA`, `CIS`, `MIDDLE_EAST`, `AFRICA`
- `roundwinnerside`: `T`, `CT`, `UNKNOWN`
- `roundwintype`: `T_WIN`, `CT_WIN`, `BOMB_DEFUSED`, `BOMB_EXPLODED`, `TIME_OVER`, `UNKNOWN`
- `statsside`: `BOTH`, `T`, `CT`
- `vetoaction`: `PICK`, `BAN`, `DECIDER`

- `playerrole` currently exists as an enum type in PostgreSQL but is not referenced by any column in the 10 active tables.

## Entity Relationships

```text
events (1) ----< matches (N)
matches (1) ---< maps (N)
matches (1) ---< match_lineups (N) >---- players (1)
matches (1) ---< map_vetos (N)
matches (1) ---< match_player_stats (N) >---- players (1)
maps (1) ------< map_player_stats (N) >---- players (1)
maps (1) ------< map_rounds (N)
teams are referenced by matches/maps/lineups/vetos/stats/rounds winner ids
```

## `teams`

Row count: **6,373**

### Columns

| Column | PostgreSQL Type | Nullable | Default |
|---|---|---|---|
| `id` | `integer` | NO | `nextval('teams_id_seq'::regclass)` |
| `name` | `character varying` | NO | `` |
| `logo_url` | `character varying` | YES | `` |
| `country` | `character varying` | YES | `` |
| `region` | `region` | YES | `` |
| `world_rank` | `integer` | YES | `` |
| `valve_rank` | `integer` | YES | `` |
| `weeks_in_top30` | `integer` | YES | `` |
| `avg_player_age` | `double precision` | YES | `` |
| `coach_name` | `character varying` | YES | `` |
| `coach_id` | `integer` | YES | `` |
| `source_url` | `character varying` | YES | `` |
| `scraped_at` | `timestamp without time zone` | YES | `` |
| `created_at` | `timestamp without time zone` | NO | `` |
| `updated_at` | `timestamp without time zone` | NO | `` |

### Constraints

- `teams_pkey`: `PRIMARY KEY (id)`

### Example Query and Result

```sql
SELECT id, name, country, region, world_rank, valve_rank, source_url, scraped_at FROM teams WHERE id IN (10864, 13501) ORDER BY id;
```

```json
[
  {
    "id": 10864,
    "name": "VP.Prodigy",
    "country": null,
    "region": null,
    "world_rank": null,
    "valve_rank": null,
    "source_url": null,
    "scraped_at": null
  },
  {
    "id": 13501,
    "name": "illwill",
    "country": null,
    "region": null,
    "world_rank": null,
    "valve_rank": null,
    "source_url": null,
    "scraped_at": null
  }
]
```

## `players`

Row count: **15,761**

### Columns

| Column | PostgreSQL Type | Nullable | Default |
|---|---|---|---|
| `id` | `integer` | NO | `nextval('players_id_seq'::regclass)` |
| `nickname` | `character varying` | NO | `` |
| `full_name` | `character varying` | YES | `` |
| `country` | `character varying` | YES | `` |
| `age` | `integer` | YES | `` |
| `source_url` | `character varying` | YES | `` |
| `scraped_at` | `timestamp without time zone` | YES | `` |
| `created_at` | `timestamp without time zone` | NO | `` |
| `updated_at` | `timestamp without time zone` | NO | `` |

### Constraints

- `players_pkey`: `PRIMARY KEY (id)`

### Example Query and Result

```sql
SELECT id, nickname, full_name, country, age, source_url, scraped_at FROM players WHERE id IN (SELECT player_id FROM match_player_stats WHERE match_id = 2390365 ORDER BY rating DESC NULLS LAST LIMIT 3) ORDER BY id;
```

```json
[
  {
    "id": 20889,
    "nickname": "7kick",
    "full_name": null,
    "country": "Romania",
    "age": null,
    "source_url": null,
    "scraped_at": null
  },
  {
    "id": 9656,
    "nickname": "hAdji",
    "full_name": null,
    "country": "France",
    "age": null,
    "source_url": null,
    "scraped_at": null
  },
  {
    "id": 8311,
    "nickname": "nEMANHA",
    "full_name": null,
    "country": "Serbia",
    "age": null,
    "source_url": null,
    "scraped_at": null
  }
]
```

## `events`

Row count: **6,114**

### Columns

| Column | PostgreSQL Type | Nullable | Default |
|---|---|---|---|
| `id` | `integer` | NO | `nextval('events_id_seq'::regclass)` |
| `name` | `character varying` | NO | `` |
| `start_date` | `date` | YES | `` |
| `end_date` | `date` | YES | `` |
| `prize_pool` | `character varying` | YES | `` |
| `location` | `character varying` | YES | `` |
| `tier` | `eventtier` | YES | `` |
| `lan` | `boolean` | NO | `` |
| `teams_count` | `integer` | YES | `` |
| `source_url` | `character varying` | YES | `` |
| `scraped_at` | `timestamp without time zone` | YES | `` |
| `created_at` | `timestamp without time zone` | NO | `` |

### Constraints

- `events_pkey`: `PRIMARY KEY (id)`

### Example Query and Result

```sql
SELECT id, name, start_date, end_date, prize_pool, location, tier, lan, teams_count, source_url, scraped_at FROM events WHERE id = 8967;
```

```json
[
  {
    "id": 8967,
    "name": "ESL Challenger League Season 51 Europe Cup 1",
    "start_date": null,
    "end_date": null,
    "prize_pool": null,
    "location": null,
    "tier": null,
    "lan": false,
    "teams_count": null,
    "source_url": null,
    "scraped_at": null
  }
]
```

## `matches`

Row count: **80,454**

### Columns

| Column | PostgreSQL Type | Nullable | Default |
|---|---|---|---|
| `id` | `integer` | NO | `nextval('matches_id_seq'::regclass)` |
| `team1_id` | `integer` | NO | `` |
| `team2_id` | `integer` | NO | `` |
| `event_id` | `integer` | YES | `` |
| `winner_id` | `integer` | YES | `` |
| `date` | `timestamp without time zone` | YES | `` |
| `format` | `matchformat` | YES | `` |
| `status` | `matchstatus` | NO | `` |
| `stage` | `character varying` | YES | `` |
| `score_team1` | `integer` | NO | `` |
| `score_team2` | `integer` | NO | `` |
| `stars` | `integer` | NO | `` |
| `potm_player_id` | `integer` | YES | `` |
| `potm_vote_percentage` | `double precision` | YES | `` |
| `potm_maps_played` | `integer` | YES | `` |
| `potm_kpr` | `double precision` | YES | `` |
| `potm_dpr` | `double precision` | YES | `` |
| `potm_kast` | `double precision` | YES | `` |
| `potm_mk_rating` | `double precision` | YES | `` |
| `potm_swing` | `double precision` | YES | `` |
| `potm_adr` | `double precision` | YES | `` |
| `potm_rating` | `double precision` | YES | `` |
| `source_url` | `character varying` | YES | `` |
| `scraped_at` | `timestamp without time zone` | YES | `` |
| `created_at` | `timestamp without time zone` | NO | `` |
| `updated_at` | `timestamp without time zone` | NO | `` |

### Constraints

- `matches_event_id_fkey`: `FOREIGN KEY (event_id) REFERENCES events(id)`
- `matches_potm_player_id_fkey`: `FOREIGN KEY (potm_player_id) REFERENCES players(id)`
- `matches_team1_id_fkey`: `FOREIGN KEY (team1_id) REFERENCES teams(id)`
- `matches_team2_id_fkey`: `FOREIGN KEY (team2_id) REFERENCES teams(id)`
- `matches_winner_id_fkey`: `FOREIGN KEY (winner_id) REFERENCES teams(id)`
- `matches_pkey`: `PRIMARY KEY (id)`

### Example Query and Result

```sql
SELECT id, team1_id, team2_id, event_id, winner_id, date, format, status, stage, score_team1, score_team2, stars, potm_player_id, potm_vote_percentage, potm_maps_played, potm_kpr, potm_dpr, potm_kast, potm_mk_rating, potm_swing, potm_adr, potm_rating, source_url, scraped_at, created_at, updated_at FROM matches WHERE id = 2390365;
```

```json
[
  {
    "id": 2390365,
    "team1_id": 10864,
    "team2_id": 13501,
    "event_id": 8967,
    "winner_id": 13501,
    "date": "2026-02-16T15:00:00",
    "format": "BO3",
    "status": "FINISHED",
    "stage": "Lower bracket round 2",
    "score_team1": 0,
    "score_team2": 2,
    "stars": 0,
    "potm_player_id": 20889,
    "potm_vote_percentage": null,
    "potm_maps_played": 2,
    "potm_kpr": 0.8,
    "potm_dpr": 0.63,
    "potm_kast": 78.0,
    "potm_mk_rating": 0.89,
    "potm_swing": 6.87,
    "potm_adr": 86.1,
    "potm_rating": 1.42,
    "source_url": "/matches/2390365/_",
    "scraped_at": "2026-02-16T16:22:45.382949",
    "created_at": "2026-02-16T16:22:45.341581",
    "updated_at": "2026-02-16T16:22:46.167795"
  }
]
```

## `maps`

Row count: **153,046**

### Columns

| Column | PostgreSQL Type | Nullable | Default |
|---|---|---|---|
| `id` | `integer` | NO | `nextval('maps_id_seq'::regclass)` |
| `match_id` | `integer` | NO | `` |
| `map_name` | `mapname` | NO | `` |
| `map_number` | `integer` | NO | `` |
| `picked_by_id` | `integer` | YES | `` |
| `winner_id` | `integer` | YES | `` |
| `score_team1` | `integer` | NO | `` |
| `score_team2` | `integer` | NO | `` |
| `score_team1_ct` | `integer` | NO | `` |
| `score_team1_t` | `integer` | NO | `` |
| `score_team2_ct` | `integer` | NO | `` |
| `score_team2_t` | `integer` | NO | `` |
| `score_team1_ot` | `integer` | NO | `` |
| `score_team2_ot` | `integer` | NO | `` |
| `overtime` | `boolean` | NO | `` |
| `stats_source_url` | `character varying` | YES | `` |
| `stats_scraped_at` | `timestamp without time zone` | YES | `` |

### Constraints

- `maps_match_id_fkey`: `FOREIGN KEY (match_id) REFERENCES matches(id)`
- `maps_picked_by_id_fkey`: `FOREIGN KEY (picked_by_id) REFERENCES teams(id)`
- `maps_winner_id_fkey`: `FOREIGN KEY (winner_id) REFERENCES teams(id)`
- `maps_pkey`: `PRIMARY KEY (id)`

### Example Query and Result

```sql
SELECT id, match_id, map_name, map_number, picked_by_id, winner_id, score_team1, score_team2, score_team1_ct, score_team1_t, score_team2_ct, score_team2_t, score_team1_ot, score_team2_ot, overtime, stats_source_url, stats_scraped_at FROM maps WHERE match_id = 2390365 ORDER BY map_number;
```

```json
[
  {
    "id": 219398,
    "match_id": 2390365,
    "map_name": "OVERPASS",
    "map_number": 1,
    "picked_by_id": 10864,
    "winner_id": 13501,
    "score_team1": 6,
    "score_team2": 13,
    "score_team1_ct": 3,
    "score_team1_t": 3,
    "score_team2_ct": 9,
    "score_team2_t": 4,
    "score_team1_ot": 0,
    "score_team2_ot": 0,
    "overtime": false,
    "stats_source_url": "/stats/matches/mapstatsid/219398/_",
    "stats_scraped_at": "2026-02-16T16:22:47.204441"
  },
  {
    "id": 219401,
    "match_id": 2390365,
    "map_name": "NUKE",
    "map_number": 2,
    "picked_by_id": 13501,
    "winner_id": 13501,
    "score_team1": 9,
    "score_team2": 13,
    "score_team1_ct": 6,
    "score_team1_t": 3,
    "score_team2_ct": 7,
    "score_team2_t": 6,
    "score_team1_ot": 0,
    "score_team2_ot": 0,
    "overtime": false,
    "stats_source_url": "/stats/matches/mapstatsid/219401/_",
    "stats_scraped_at": "2026-02-16T16:22:48.244720"
  }
]
```

## `match_lineups`

Row count: **803,166**

### Columns

| Column | PostgreSQL Type | Nullable | Default |
|---|---|---|---|
| `id` | `integer` | NO | `nextval('match_lineups_id_seq'::regclass)` |
| `match_id` | `integer` | NO | `` |
| `player_id` | `integer` | NO | `` |
| `team_id` | `integer` | NO | `` |

### Constraints

- `match_lineups_match_id_fkey`: `FOREIGN KEY (match_id) REFERENCES matches(id)`
- `match_lineups_player_id_fkey`: `FOREIGN KEY (player_id) REFERENCES players(id)`
- `match_lineups_team_id_fkey`: `FOREIGN KEY (team_id) REFERENCES teams(id)`
- `match_lineups_pkey`: `PRIMARY KEY (id)`
- `uq_match_player`: `UNIQUE (match_id, player_id)`

### Example Query and Result

```sql
SELECT ml.match_id, ml.player_id, p.nickname, ml.team_id FROM match_lineups ml JOIN players p ON p.id = ml.player_id WHERE ml.match_id = 2390365 ORDER BY ml.team_id, ml.player_id LIMIT 6;
```

```json
[
  {
    "match_id": 2390365,
    "player_id": 24292,
    "nickname": "F0R3VER",
    "team_id": 10864
  },
  {
    "match_id": 2390365,
    "player_id": 24950,
    "nickname": "AquaRS",
    "team_id": 10864
  },
  {
    "match_id": 2390365,
    "player_id": 24951,
    "nickname": "TriBorgg1",
    "team_id": 10864
  },
  {
    "match_id": 2390365,
    "player_id": 25462,
    "nickname": "lasfas",
    "team_id": 10864
  },
  {
    "match_id": 2390365,
    "player_id": 25463,
    "nickname": "rokilan",
    "team_id": 10864
  },
  {
    "match_id": 2390365,
    "player_id": 8311,
    "nickname": "nEMANHA",
    "team_id": 13501
  }
]
```

## `map_vetos`

Row count: **485,169**

### Columns

| Column | PostgreSQL Type | Nullable | Default |
|---|---|---|---|
| `id` | `integer` | NO | `nextval('map_vetos_id_seq'::regclass)` |
| `match_id` | `integer` | NO | `` |
| `team_id` | `integer` | YES | `` |
| `map_name` | `mapname` | NO | `` |
| `action` | `vetoaction` | NO | `` |
| `veto_order` | `integer` | NO | `` |

### Constraints

- `map_vetos_match_id_fkey`: `FOREIGN KEY (match_id) REFERENCES matches(id)`
- `map_vetos_team_id_fkey`: `FOREIGN KEY (team_id) REFERENCES teams(id)`
- `map_vetos_pkey`: `PRIMARY KEY (id)`
- `uq_match_veto_order`: `UNIQUE (match_id, veto_order)`

### Example Query and Result

```sql
SELECT match_id, team_id, map_name, action, veto_order FROM map_vetos WHERE match_id = 2390365 ORDER BY veto_order;
```

```json
[
  {
    "match_id": 2390365,
    "team_id": 10864,
    "map_name": "INFERNO",
    "action": "BAN",
    "veto_order": 1
  },
  {
    "match_id": 2390365,
    "team_id": 13501,
    "map_name": "ANCIENT",
    "action": "BAN",
    "veto_order": 2
  },
  {
    "match_id": 2390365,
    "team_id": 10864,
    "map_name": "OVERPASS",
    "action": "PICK",
    "veto_order": 3
  },
  {
    "match_id": 2390365,
    "team_id": 13501,
    "map_name": "NUKE",
    "action": "PICK",
    "veto_order": 4
  },
  {
    "match_id": 2390365,
    "team_id": 10864,
    "map_name": "MIRAGE",
    "action": "BAN",
    "veto_order": 5
  },
  {
    "match_id": 2390365,
    "team_id": 13501,
    "map_name": "ANUBIS",
    "action": "BAN",
    "veto_order": 6
  },
  {
    "match_id": 2390365,
    "team_id": null,
    "map_name": "DUST2",
    "action": "DECIDER",
    "veto_order": 7
  }
]
```

## `match_player_stats`

Row count: **781,734**

### Columns

| Column | PostgreSQL Type | Nullable | Default |
|---|---|---|---|
| `id` | `integer` | NO | `nextval('match_player_stats_id_seq'::regclass)` |
| `match_id` | `integer` | NO | `` |
| `player_id` | `integer` | NO | `` |
| `team_id` | `integer` | NO | `` |
| `kills` | `integer` | NO | `` |
| `eco_kills` | `integer` | YES | `` |
| `deaths` | `integer` | NO | `` |
| `eco_deaths` | `integer` | YES | `` |
| `assists` | `integer` | NO | `` |
| `headshots` | `integer` | NO | `` |
| `eco_headshots` | `integer` | YES | `` |
| `first_kills` | `integer` | NO | `` |
| `eco_first_kills` | `integer` | YES | `` |
| `first_deaths` | `integer` | NO | `` |
| `eco_first_deaths` | `integer` | YES | `` |
| `clutches_won` | `integer` | NO | `` |
| `multi_kills` | `integer` | NO | `` |
| `flash_assists` | `integer` | NO | `` |
| `traded_deaths` | `integer` | NO | `` |
| `eco_traded_deaths` | `integer` | YES | `` |
| `adr` | `double precision` | YES | `` |
| `eco_adr` | `double precision` | YES | `` |
| `kast` | `double precision` | YES | `` |
| `eco_kast` | `double precision` | YES | `` |
| `rating` | `double precision` | YES | `` |
| `swing` | `double precision` | YES | `` |

### Constraints

- `match_player_stats_match_id_fkey`: `FOREIGN KEY (match_id) REFERENCES matches(id)`
- `match_player_stats_player_id_fkey`: `FOREIGN KEY (player_id) REFERENCES players(id)`
- `match_player_stats_team_id_fkey`: `FOREIGN KEY (team_id) REFERENCES teams(id)`
- `match_player_stats_pkey`: `PRIMARY KEY (id)`
- `uq_match_player_stats`: `UNIQUE (match_id, player_id)`

### Example Query and Result

```sql
SELECT match_id, player_id, team_id, kills, deaths, adr, kast, rating, swing FROM match_player_stats WHERE match_id = 2390365 ORDER BY rating DESC NULLS LAST LIMIT 5;
```

```json
[
  {
    "match_id": 2390365,
    "player_id": 20889,
    "team_id": 13501,
    "kills": 33,
    "deaths": 26,
    "adr": 86.1,
    "kast": 78.0,
    "rating": 1.42,
    "swing": 6.87
  },
  {
    "match_id": 2390365,
    "player_id": 9656,
    "team_id": 13501,
    "kills": 37,
    "deaths": 23,
    "adr": 84.1,
    "kast": 80.5,
    "rating": 1.35,
    "swing": 1.86
  },
  {
    "match_id": 2390365,
    "player_id": 8311,
    "team_id": 13501,
    "kills": 36,
    "deaths": 30,
    "adr": 98.9,
    "kast": 73.2,
    "rating": 1.32,
    "swing": 1.05
  },
  {
    "match_id": 2390365,
    "player_id": 24951,
    "team_id": 10864,
    "kills": 30,
    "deaths": 33,
    "adr": 88.9,
    "kast": 75.6,
    "rating": 1.18,
    "swing": 0.56
  },
  {
    "match_id": 2390365,
    "player_id": 19698,
    "team_id": 13501,
    "kills": 29,
    "deaths": 25,
    "adr": 66.3,
    "kast": 78.0,
    "rating": 1.09,
    "swing": 0.79
  }
]
```

## `map_player_stats`

Row count: **4,592,794**

### Columns

| Column | PostgreSQL Type | Nullable | Default |
|---|---|---|---|
| `id` | `integer` | NO | `nextval('map_player_stats_id_seq'::regclass)` |
| `map_id` | `integer` | NO | `` |
| `player_id` | `integer` | NO | `` |
| `team_id` | `integer` | NO | `` |
| `side` | `statsside` | NO | `` |
| `kills` | `integer` | NO | `` |
| `deaths` | `integer` | NO | `` |
| `eco_kills` | `integer` | YES | `` |
| `eco_deaths` | `integer` | YES | `` |
| `adr` | `double precision` | YES | `` |
| `eco_adr` | `double precision` | YES | `` |
| `kast` | `double precision` | YES | `` |
| `eco_kast` | `double precision` | YES | `` |
| `rating` | `double precision` | YES | `` |
| `assists` | `integer` | NO | `` |
| `headshots` | `integer` | NO | `` |
| `first_kills` | `integer` | NO | `` |
| `eco_first_kills` | `integer` | YES | `` |
| `first_deaths` | `integer` | NO | `` |
| `eco_first_deaths` | `integer` | YES | `` |
| `clutches_won` | `integer` | NO | `` |
| `multi_kills` | `integer` | NO | `` |
| `flash_assists` | `integer` | NO | `` |
| `traded_deaths` | `integer` | NO | `` |
| `eco_headshots` | `integer` | YES | `` |
| `eco_traded_deaths` | `integer` | YES | `` |
| `swing` | `double precision` | YES | `` |

### Constraints

- `map_player_stats_map_id_fkey`: `FOREIGN KEY (map_id) REFERENCES maps(id)`
- `map_player_stats_player_id_fkey`: `FOREIGN KEY (player_id) REFERENCES players(id)`
- `map_player_stats_team_id_fkey`: `FOREIGN KEY (team_id) REFERENCES teams(id)`
- `map_player_stats_pkey`: `PRIMARY KEY (id)`
- `uq_map_player_side`: `UNIQUE (map_id, player_id, side)`

### Example Query and Result

```sql
SELECT map_id, player_id, team_id, side, kills, deaths, assists, adr, kast, rating, first_kills, first_deaths, swing FROM map_player_stats WHERE map_id = 219398 AND side = 'BOTH' ORDER BY rating DESC NULLS LAST LIMIT 5;
```

```json
[
  {
    "map_id": 219398,
    "player_id": 8311,
    "team_id": 13501,
    "side": "BOTH",
    "kills": 18,
    "deaths": 13,
    "assists": 9,
    "adr": 109.8,
    "kast": 68.4,
    "rating": 1.46,
    "first_kills": 2,
    "first_deaths": 3,
    "swing": 3.36
  },
  {
    "map_id": 219398,
    "player_id": 20889,
    "team_id": 13501,
    "side": "BOTH",
    "kills": 17,
    "deaths": 12,
    "assists": 7,
    "adr": 90.6,
    "kast": 89.5,
    "rating": 1.44,
    "first_kills": 5,
    "first_deaths": 3,
    "swing": 5.73
  },
  {
    "map_id": 219398,
    "player_id": 19698,
    "team_id": 13501,
    "side": "BOTH",
    "kills": 16,
    "deaths": 10,
    "assists": 6,
    "adr": 81.0,
    "kast": 89.5,
    "rating": 1.43,
    "first_kills": 1,
    "first_deaths": 1,
    "swing": 5.21
  },
  {
    "map_id": 219398,
    "player_id": 9656,
    "team_id": 13501,
    "side": "BOTH",
    "kills": 18,
    "deaths": 9,
    "assists": 3,
    "adr": 78.8,
    "kast": 84.2,
    "rating": 1.25,
    "first_kills": 0,
    "first_deaths": 1,
    "swing": 0.2
  },
  {
    "map_id": 219398,
    "player_id": 25462,
    "team_id": 10864,
    "side": "BOTH",
    "kills": 12,
    "deaths": 12,
    "assists": 3,
    "adr": 62.4,
    "kast": 73.7,
    "rating": 1.22,
    "first_kills": 3,
    "first_deaths": 0,
    "swing": 3.38
  }
]
```

## `map_rounds`

Row count: **3,807,368**

### Columns

| Column | PostgreSQL Type | Nullable | Default |
|---|---|---|---|
| `id` | `integer` | NO | `nextval('map_rounds_id_seq'::regclass)` |
| `map_id` | `integer` | NO | `` |
| `round_number` | `integer` | NO | `` |
| `winner_team_id` | `integer` | YES | `` |
| `winner_side` | `roundwinnerside` | NO | `` |
| `win_type` | `roundwintype` | NO | `` |
| `score_team1` | `integer` | YES | `` |
| `score_team2` | `integer` | YES | `` |
| `is_overtime` | `boolean` | NO | `` |

### Constraints

- `map_rounds_map_id_fkey`: `FOREIGN KEY (map_id) REFERENCES maps(id)`
- `map_rounds_winner_team_id_fkey`: `FOREIGN KEY (winner_team_id) REFERENCES teams(id)`
- `map_rounds_pkey`: `PRIMARY KEY (id)`
- `uq_map_round`: `UNIQUE (map_id, round_number)`

### Example Query and Result

```sql
SELECT map_id, round_number, winner_team_id, winner_side, win_type, score_team1, score_team2, is_overtime FROM map_rounds WHERE map_id = 219398 ORDER BY round_number LIMIT 8;
```

```json
[
  {
    "map_id": 219398,
    "round_number": 1,
    "winner_team_id": 13501,
    "winner_side": "CT",
    "win_type": "CT_WIN",
    "score_team1": 0,
    "score_team2": 1,
    "is_overtime": false
  },
  {
    "map_id": 219398,
    "round_number": 2,
    "winner_team_id": 13501,
    "winner_side": "CT",
    "win_type": "CT_WIN",
    "score_team1": 0,
    "score_team2": 2,
    "is_overtime": false
  },
  {
    "map_id": 219398,
    "round_number": 3,
    "winner_team_id": 13501,
    "winner_side": "CT",
    "win_type": "CT_WIN",
    "score_team1": 0,
    "score_team2": 3,
    "is_overtime": false
  },
  {
    "map_id": 219398,
    "round_number": 4,
    "winner_team_id": 13501,
    "winner_side": "CT",
    "win_type": "CT_WIN",
    "score_team1": 0,
    "score_team2": 4,
    "is_overtime": false
  },
  {
    "map_id": 219398,
    "round_number": 5,
    "winner_team_id": 10864,
    "winner_side": "T",
    "win_type": "T_WIN",
    "score_team1": 1,
    "score_team2": 4,
    "is_overtime": false
  },
  {
    "map_id": 219398,
    "round_number": 6,
    "winner_team_id": 10864,
    "winner_side": "T",
    "win_type": "BOMB_EXPLODED",
    "score_team1": 2,
    "score_team2": 4,
    "is_overtime": false
  },
  {
    "map_id": 219398,
    "round_number": 7,
    "winner_team_id": 10864,
    "winner_side": "T",
    "win_type": "BOMB_EXPLODED",
    "score_team1": 3,
    "score_team2": 4,
    "is_overtime": false
  },
  {
    "map_id": 219398,
    "round_number": 8,
    "winner_team_id": 13501,
    "winner_side": "CT",
    "win_type": "CT_WIN",
    "score_team1": 3,
    "score_team2": 5,
    "is_overtime": false
  }
]
```

