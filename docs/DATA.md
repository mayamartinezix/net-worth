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
| ClubElo API (`api.clubelo.com`) | ✅ | Yes — each WC player’s club Elo → squad index |
| risingtransfers per-90 + squads | ✅ | Yes — individual club league attack stats |
| mominullptr squad market values | ✅ | Yes — value proxy in squad index |
| UEFA Euro player club stats | ❌ | Not yet; Euro sims stay Elo-only for squad feature |
| UEFA Euro odds | ❌ drop into `data/odds/` | Optional |

## Squad club-performance feature

National Elo is complemented by a **squad_index** built from how rostered players perform at their clubs:

1. Match each WC 2026 player to their club’s **ClubElo**
2. Weight **league per-90** attack contribution (goals, assists, shots, key passes)
3. Add log **market value** as a talent proxy
4. Standardize within the 48-team field → `squad_index`
5. Feed the home–away difference into Poisson λ with a small coefficient (default 0.12)

Refresh:

```bash
PYTHONPATH=backend python backend/scripts/ingest_player_club_data.py
```

This is still a team-level feature (aggregated players), not a full lineups/xG game model.
