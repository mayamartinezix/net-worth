# Data layout

Where historical inputs live for Elo fitting, Poisson calibration, backtests, and market baselines.

## Directory map

```
data/
  raw/                         # Upstream dumps (re-downloadable)
    results.csv                # martj42 international results (CC0)
    shootouts.csv              # Penalty shootout winners
    fifa_ranking_historical.csv
  processed/                   # Normalized for our models
    matches_all.csv
    matches_2010_plus.csv
    matches_wc_2018.csv
    matches_wc_2022.csv
    matches_euro_2016.csv
    matches_euro_2020.csv      # staged in 2021
    matches_euro_2024.csv
    fifa_rankings.csv
    shootouts.csv
    manifest.json
  odds/                        # Market baseline (you may add Euros here)
    WorldCup2026.xlsx          # Source workbook from football-data.co.uk
    wc_2018_odds.csv           # Auto-exported
    wc_2022_odds.csv
    wc_2014_odds.csv
    euro_*_odds.csv            # ← DROP UEFA Euro odds HERE (not auto-fetched)
  sample/                      # Tiny fixtures for unit tests only
```

## What this agent already gathered

| Dataset | Status | Source |
|---------|--------|--------|
| All internationals (results) | ✅ in `data/raw/results.csv` | [martj42/international_results](https://github.com/martj42/international_results) |
| Shootouts | ✅ | same |
| FIFA rankings 1992–2024 | ✅ | [Dato-Futbol/fifa-ranking](https://github.com/Dato-Futbol/fifa-ranking) |
| World Cup odds 2014/2018/2022 | ✅ | [football-data.co.uk](https://www.football-data.co.uk/WorldCup2026.xlsx) |
| UEFA Euro odds 2016/2020/2024 | ❌ not freely bulk-downloadable in the same workbook | **you drop CSVs** |

Refresh / rebuild processed slices:

```bash
PYTHONPATH=backend python backend/scripts/ingest_public_data.py
# or, if raw files already present:
PYTHONPATH=backend python backend/scripts/ingest_public_data.py --skip-download
```

## What you should add (only if you want market baselines for Euros)

Put files in **`data/odds/`**:

- `euro_2016_odds.csv`
- `euro_2020_odds.csv`
- `euro_2024_odds.csv`

Minimum columns:

```text
match_date,home_team,away_team,odds_home_avg,odds_draw_avg,odds_away_avg
```

Use **decimal** odds. Team names should match `data/processed/matches_euro_*.csv` (`home_team_id` / `away_team_id`), e.g. `France`, `England`, `Czech Republic` (not `CZE`).

Practical sources to export from:
- OddsPortal / Footiqo (manual CSV export per tournament)
- Any historical odds archive you already have

World Cup market comparison does **not** need extra files — `wc_2018_odds.csv` and `wc_2022_odds.csv` are enough.

## Match schema used by Elo / Poisson

Processed match files use:

```text
match_date,home_team_id,away_team_id,home_goals,away_goals,
tournament,city,country,is_neutral_venue,is_friendly
```

## Notes

- Euro 2020 matches are labeled year **2021** in the raw file (COVID delay); ingest maps them to `euro_2020`.
- Raw `results.csv` is large (~50k rows). Prefer `matches_2010_plus.csv` for day-to-day Elo fits.
- Do not hand-edit `raw/`; re-run ingest after dropping new odds files if you extend the exporter.
