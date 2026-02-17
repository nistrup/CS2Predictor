# Match Outcome Feature Prioritization (Hypothesized)

This document lists features to calculate for CS2 match outcome prediction and ranks them by expected predictive importance.

## Assumptions

- Primary ranking is for **pre-game** prediction.
- Importance score is a **hypothesized relative impact** from `0.0` to `10.0` (not a measured model importance yet).
- Data status:
  - `Available now`: can be built from current CS2Data snapshot fields.
  - `Derived`: available now but requires non-trivial aggregation/modeling.
  - `External/new`: likely needs additional data sources not in the current snapshot.

## Pre-Game Features (Ranked)

| Rank | Feature to Calculate | Importance (0-10) | Why It Should Matter | Data Status |
|---:|---|---:|---|---|
| 1 | **Team Elo differential** (global, recency-decayed, opponent-adjusted) | 9.8 | Strong summary of team strength and win expectancy across formats/opponents. | Derived |
| 2 | **Lineup-weighted player Elo differential** (projected 5-man aggregate) | 9.5 | Captures individual skill distribution and star-power effects not visible in team-only ratings. | Derived |
| 3 | **Map-specific team Elo + map pool edge** | 9.3 | CS2 outcomes are highly map-dependent; map-level strength is often decisive in BO3/BO5. | Derived |
| 4 | **Market implied probability** (bookmaker consensus) | 9.2 | Betting markets are usually a strong aggregate of public + expert information. | External/new |
| 5 | **Veto advantage score** (pick/ban tendencies and expected map sequence edge) | 8.8 | Win probability often shifts heavily after accounting for likely veto flow. | Derived |
| 6 | **Recent form vs strength-of-schedule** (last N maps/matches, decayed) | 8.6 | Separates true improvement/decline from easy-opponent inflation. | Derived |
| 7 | **CT/T side strength differential** (overall + map-specific) | 8.3 | Side-specific capability is a consistent edge driver, especially on polarized maps. | Derived |
| 8 | **Entry duel edge** (first-kill/first-death rates) | 8.0 | Opening duel control strongly affects round and map conversion. | Available now |
| 9 | **Lineup stability/continuity** (matches together, days since roster change) | 7.8 | Roster stability generally improves coordination and reduces performance variance. | Derived |
| 10 | **Clutch conversion edge** (1vX success, high-leverage rounds) | 7.6 | Close-game outcomes are often decided by clutch and late-round execution. | Available now |
| 11 | **Opponent-adjusted performance residual** (actual - Elo-expected) | 7.4 | Measures over/under-performance beyond baseline strength ratings. | Derived |
| 12 | **Event pressure feature** (stage importance, elimination risk, playoffs/finals) | 7.1 | Some teams/players overperform or underperform under pressure. | Available now |
| 13 | **LAN vs online differential** | 7.0 | Teams can have materially different performance profiles by environment. | Available now |
| 14 | **Round dominance profile** (average round differential, close-map conversion) | 6.9 | Distinguishes clean wins from fragile win rates. | Derived |
| 15 | **Rest/fatigue/travel load** (days rest, match congestion, timezone shift) | 6.7 | Fatigue and travel can reduce consistency and mechanics. | External/new |
| 16 | **Head-to-head style matchup feature** (historical tactical matchup tendencies) | 6.5 | Certain playstyle interactions repeatedly produce edges independent of rank. | Derived |
| 17 | **Role balance index** (entry/AWP/support/lurk mix and dependency risk) | 6.3 | Unbalanced roles can create structural weaknesses in defaults/trades. | External/new |
| 18 | **IGL/coach change recency shock** | 6.1 | Leadership changes often cause short-term volatility or strategic shifts. | External/new |
| 19 | **Communication/language cohesion proxy** | 5.7 | Mixed-language or recent international lineups may have temporary coordination penalties. | External/new |
| 20 | **News/sentiment disruption score** (visa issues, illness, stand-ins) | 4.8 | Off-server disruptions can matter but are noisy and hard to quantify reliably. | External/new |

## Mid-Game (Live) Features (Separate Ranking)

These are high-value once predicting during a live map/match.

| Rank | Feature to Calculate | Importance (0-10) | Data Status |
|---:|---|---:|---|
| 1 | Current score differential + rounds remaining context | 10.0 | Available now |
| 2 | Side context (current side, upcoming side switch, OT proximity) | 9.5 | Available now |
| 3 | Rolling round momentum (last 3/5 rounds, streak break flags) | 9.0 | Available now |
| 4 | Live entry control trend (opening kills in recent rounds) | 8.9 | External/new |
| 5 | Economy advantage state (full-buy/force/eco quality) | 8.8 | External/new |
| 6 | Live player impact trend (ADR/KAST/rating trajectory this map) | 8.5 | Available now |
| 7 | Clutch/anti-eco swing events in current map | 8.2 | Available now |
| 8 | Timeout and tactical reset effects | 7.9 | External/new |
| 9 | Utility effectiveness trend (damage and execute success) | 7.8 | External/new |
| 10 | Win-probability change velocity (state-transition model) | 7.6 | Derived |

## Recommended Starting Build Order

1. Team Elo differential.
2. Lineup-weighted player Elo differential.
3. Map-specific Elo/map-pool edge.
4. Veto advantage score.
5. Recent form with strength-of-schedule adjustment.
6. CT/T side strength differential.
7. Entry duel edge.
8. Lineup stability.

After baseline training, replace hypothesized scores with measured importance (for example permutation importance + SHAP) and re-rank.
