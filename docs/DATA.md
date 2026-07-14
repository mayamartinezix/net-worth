# Data layout

Where historical inputs live for Elo fitting, backtests, and market baselines.

## Decision window (important)

**Live model decisions use internationals from `2020-01-01` onward only.**

| File | Role |
|------|------|
| `data/processed/matches_2020_plus.csv` | **Elo fitting / simulator strength** |
| `data/processed/matches_2010_plus.csv` | Legacy slice for experiments only |
| `data/processed/matches_all.csv` | Full archive (not used for live Elo) |

Elo cold-starts at 1500 and is fit sequentially on the 2020+ window up to each event’s as-of date. Hand-written prior Elos are **not** blended into decisions.

## Directory map

```
data/
  raw/
    results.csv                    # martj42 internationals
    shootouts.csv
    fifa_ranking_historical.csv    # Dato-Futbol FIFA rankings
    fifa_ranking_cnc8_2020.csv     # alternate FIFA ranking schema snapshot
    eloratings_world.tsv           # World Football Elo Ratings (live snapshot)
    eloratings_en_teams.tsv        # country code → name map
    wc2026_openfootball_*.json     # openfootball WC 2026 structure
  processed/
    matches_2020_plus.csv          # ★ decision window
    matches_2010_plus.csv
    matches_all.csv
    matches_wc_*.csv / matches_euro_*.csv
    fifa_rankings.csv
    fifa_rankings_2020_plus.csv
    fifa_rankings_cnc8_snapshot.csv
    eloratings_world_snapshot.csv  # external comparator (not primary Elo)
    shootouts.csv
    manifest.json
  odds/
    wc_*_odds.csv                  # football-data.co.uk
    euro_*_odds.csv                # optional drop zone
```

## Sources gathered

| Source | Status | Used for decisions? |
|--------|--------|---------------------|
| martj42 international results | ✅ | Yes (2020+ only) |
| World Football Elo Ratings (eloratings.net) | ✅ snapshot | Comparator / research, not primary |
| FIFA rankings (Dato-Futbol) | ✅ + 2020+ filter | Baseline validation |
| FIFA rankings (cnc8 snapshot) | ✅ | Alternate schema / research |
| football-data.co.uk WC odds | ✅ | Market baseline |
| openfootball WC 2026 JSON | ✅ | Groups / teams / venues reference |
| ClubElo API | available (`api.clubelo.com`) | Clubs only — not used for national-team decisions |
| UEFA Euro odds | ❌ drop into `data/odds/` | Optional |

Refresh:

```bash
PYTHONPATH=backend python backend/scripts/ingest_public_data.py
```
