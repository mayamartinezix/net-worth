#!/usr/bin/env python3
"""Download / refresh public datasets used for Elo, backtests, and market baselines.

Sources
-------
- martj42/international_results (CC0): all men's full internationals
- Dato-Futbol/fifa-ranking: historical FIFA ranking points
- football-data.co.uk WorldCup2026.xlsx: WC 2014/2018/2022 (+ upcoming) with odds

Usage
-----
  PYTHONPATH=backend python backend/scripts/ingest_public_data.py
  PYTHONPATH=backend python backend/scripts/ingest_public_data.py --skip-download  # process only
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
ODDS = ROOT / "data" / "odds"

RESULTS_URL = (
    "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
)
SHOOTOUTS_URL = (
    "https://raw.githubusercontent.com/martj42/international_results/master/shootouts.csv"
)
FIFA_RANK_URL = (
    "https://raw.githubusercontent.com/Dato-Futbol/fifa-ranking/master/"
    "ranking_fifa_historical.csv"
)
WC_ODDS_URL = "https://www.football-data.co.uk/WorldCup2026.xlsx"

# Editions we care about for the validation memo
TARGET_EDITIONS = [
    {"competition": "FIFA World Cup", "year": 2018, "slug": "wc_2018"},
    {"competition": "FIFA World Cup", "year": 2022, "slug": "wc_2022"},
    {"competition": "UEFA Euro", "year": 2016, "slug": "euro_2016"},
    {"competition": "UEFA Euro", "year": 2020, "slug": "euro_2020"},  # played 2021
    {"competition": "UEFA Euro", "year": 2024, "slug": "euro_2024"},
]


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url} -> {dest}")
    urllib.request.urlretrieve(url, dest)


def to_model_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize martj42 columns to the Elo / Poisson training schema."""
    completed = df.dropna(subset=["home_score", "away_score"]).copy()
    out = pd.DataFrame(
        {
            "match_date": pd.to_datetime(completed["date"]).dt.date.astype(str),
            "home_team_id": completed["home_team"],
            "away_team_id": completed["away_team"],
            "home_goals": completed["home_score"].astype(int),
            "away_goals": completed["away_score"].astype(int),
            "tournament": completed["tournament"],
            "city": completed["city"] if "city" in completed.columns else None,
            "country": completed["country"] if "country" in completed.columns else None,
            "is_neutral_venue": completed["neutral"]
            .astype(str)
            .str.upper()
            .isin(["TRUE", "1"]),
            "is_friendly": completed["tournament"].eq("Friendly"),
        }
    )
    return out.sort_values("match_date").reset_index(drop=True)


def slice_edition(matches: pd.DataFrame, competition: str, year: int) -> pd.DataFrame:
    """Filter final-tournament matches for a competition year.

    Euro 2020 was played in 2021; World Cup / Euro labels in martj42 are the
    competition name without the year, so we window by date.
    """
    m = matches[matches["tournament"] == competition].copy()
    m["year"] = pd.to_datetime(m["match_date"]).dt.year
    if competition == "UEFA Euro" and year == 2020:
        # Tournament staged summer 2021
        return m[m["year"] == 2021].drop(columns=["year"])
    return m[m["year"] == year].drop(columns=["year"])


def export_wc_odds(xlsx_path: Path) -> list[Path]:
    """Flatten World Cup odds sheets into tidy CSVs under data/odds/."""
    xl = pd.ExcelFile(xlsx_path)
    written: list[Path] = []
    sheet_map = {
        "WorldCup2018": "wc_2018_odds.csv",
        "WorldCup2022": "wc_2022_odds.csv",
        "WorldCup2014": "wc_2014_odds.csv",
    }
    for sheet, fname in sheet_map.items():
        if sheet not in xl.sheet_names:
            continue
        df = pd.read_excel(xl, sheet)
        # Standardize closing-ish average odds columns when present
        rename = {}
        for c in df.columns:
            cl = str(c)
            if cl in {"H-Avg", "H_Avg"}:
                rename[c] = "odds_home_avg"
            elif cl in {"D-Avg", "D_Avg"}:
                rename[c] = "odds_draw_avg"
            elif cl in {"A-Avg", "A_Avg"}:
                rename[c] = "odds_away_avg"
            elif cl == "Home":
                rename[c] = "home_team"
            elif cl == "Away":
                rename[c] = "away_team"
            elif cl == "Date":
                rename[c] = "match_date"
            elif cl == "HGFT":
                rename[c] = "home_goals"
            elif cl == "AGFT":
                rename[c] = "away_goals"
        df = df.rename(columns=rename)
        if "match_date" in df.columns:
            df["match_date"] = pd.to_datetime(df["match_date"]).dt.date.astype(str)
        # Implied probabilities from avg decimal odds (overround not removed yet)
        if {"odds_home_avg", "odds_draw_avg", "odds_away_avg"} <= set(df.columns):
            inv = 1.0 / df[["odds_home_avg", "odds_draw_avg", "odds_away_avg"]].astype(float)
            s = inv.sum(axis=1)
            df["mkt_p_home"] = inv["odds_home_avg"] / s
            df["mkt_p_draw"] = inv["odds_draw_avg"] / s
            df["mkt_p_away"] = inv["odds_away_avg"] / s
        out = ODDS / fname
        df.to_csv(out, index=False)
        written.append(out)
        print(f"Wrote {out} ({len(df)} rows)")
    return written


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-download", action="store_true")
    args = parser.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)
    ODDS.mkdir(parents=True, exist_ok=True)

    results_path = RAW / "results.csv"
    shootouts_path = RAW / "shootouts.csv"
    fifa_path = RAW / "fifa_ranking_historical.csv"
    odds_xlsx = ODDS / "WorldCup2026.xlsx"

    if not args.skip_download:
        download(RESULTS_URL, results_path)
        download(SHOOTOUTS_URL, shootouts_path)
        download(FIFA_RANK_URL, fifa_path)
        download(WC_ODDS_URL, odds_xlsx)

    results = pd.read_csv(results_path)
    matches = to_model_schema(results)
    matches.to_csv(PROCESSED / "matches_all.csv", index=False)
    print(f"Wrote matches_all.csv ({len(matches)} rows)")

    # Training corridor: internationals before each tournament can be derived
    # from matches_all; also emit a compact post-2010 slice for faster Elo fits.
    recent = matches[matches["match_date"] >= "2010-01-01"]
    recent.to_csv(PROCESSED / "matches_2010_plus.csv", index=False)
    print(f"Wrote matches_2010_plus.csv ({len(recent)} rows)")

    manifest = []
    for ed in TARGET_EDITIONS:
        sl = slice_edition(matches, ed["competition"], ed["year"])
        out = PROCESSED / f"matches_{ed['slug']}.csv"
        sl.to_csv(out, index=False)
        manifest.append(
            {
                "slug": ed["slug"],
                "competition": ed["competition"],
                "year": ed["year"],
                "n_matches": int(len(sl)),
                "path": str(out.relative_to(ROOT)),
                "date_min": sl["match_date"].min() if len(sl) else None,
                "date_max": sl["match_date"].max() if len(sl) else None,
            }
        )
        print(f"Wrote {out.name}: {len(sl)} matches")

    if shootouts_path.exists():
        so = pd.read_csv(shootouts_path)
        so.to_csv(PROCESSED / "shootouts.csv", index=False)

    # FIFA rankings: keep as-is but ensure sorted
    fifa = pd.read_csv(fifa_path)
    fifa = fifa.sort_values(["date", "total_points"], ascending=[True, False])
    fifa.to_csv(PROCESSED / "fifa_rankings.csv", index=False)
    print(f"Wrote fifa_rankings.csv ({len(fifa)} rows)")

    if odds_xlsx.exists():
        export_wc_odds(odds_xlsx)

    # Placeholder note for Euros odds (not in football-data WC workbook)
    odds_readme = ODDS / "README.md"
    if not odds_readme.exists():
        odds_readme.write_text(
            "# Odds drop zone\n\n"
            "World Cup sheets are auto-exported from `WorldCup2026.xlsx`.\n\n"
            "For **UEFA Euro** market baselines, drop CSVs here named:\n"
            "- `euro_2016_odds.csv`\n"
            "- `euro_2020_odds.csv`\n"
            "- `euro_2024_odds.csv`\n\n"
            "Required columns (decimal odds):\n"
            "`match_date,home_team,away_team,odds_home_avg,odds_draw_avg,odds_away_avg`\n"
            "Optional: `home_goals,away_goals`.\n"
            "Implied probs can be added by re-running ingest or the backtest script.\n"
        )

    (PROCESSED / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print("Wrote processed/manifest.json")


if __name__ == "__main__":
    main()
