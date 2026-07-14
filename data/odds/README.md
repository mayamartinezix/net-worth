# Odds drop zone

World Cup sheets are auto-exported from `WorldCup2026.xlsx`.

For **UEFA Euro** market baselines, drop CSVs here named:
- `euro_2016_odds.csv`
- `euro_2020_odds.csv`
- `euro_2024_odds.csv`

Required columns (decimal odds):
`match_date,home_team,away_team,odds_home_avg,odds_draw_avg,odds_away_avg`
Optional: `home_goals,away_goals`.
Implied probs can be added by re-running ingest or the backtest script.
