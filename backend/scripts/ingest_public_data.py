#!/usr/bin/env python3
"""Download / refresh public datasets used for Elo, backtests, and market baselines.

Decision window
---------------
Model decisions (Elo fitting used in live simulations) use internationals from
**2020-01-01 onward only** (`matches_2020_plus.csv`).

Sources
-------
- martj42/international_results (CC0): all men's full internationals
- Dato-Futbol/fifa-ranking: historical FIFA ranking points
- cnc8/fifa-world-ranking: alternate FIFA ranking snapshot schema
- football-data.co.uk WorldCup2026.xlsx: WC odds / results sheets
- eloratings.net World.tsv + en.teams.tsv: World Football Elo Ratings snapshot
- openfootball/worldcup.json: WC 2026 groups / teams / stadiums

Usage
-----
  PYTHONPATH=backend python backend/scripts/ingest_public_data.py
  PYTHONPATH=backend python backend/scripts/ingest_public_data.py --skip-download
"""

from __future__ import annotations

import argparse
import csv
import json
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
ODDS = ROOT / "data" / "odds"

DECISION_START = "2020-01-01"

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
FIFA_RANK_CNC8_URL = (
    "https://raw.githubusercontent.com/cnc8/fifa-world-ranking/master/"
    "fifa_ranking-2020-12-10.csv"
)
WC_ODDS_URL = "https://www.football-data.co.uk/WorldCup2026.xlsx"
ELORATINGS_WORLD_URL = "https://www.eloratings.net/World.tsv"
ELORATINGS_TEAMS_URL = "https://www.eloratings.net/en.teams.tsv"
OPENFOOTBALL_BASE = (
    "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026"
)

TARGET_EDITIONS = [
    {"competition": "FIFA World Cup", "year": 2018, "slug": "wc_2018"},
    {"competition": "FIFA World Cup", "year": 2022, "slug": "wc_2022"},
    {"competition": "FIFA World Cup", "year": 2026, "slug": "wc_2026"},
    {"competition": "UEFA Euro", "year": 2016, "slug": "euro_2016"},
    {"competition": "UEFA Euro", "year": 2020, "slug": "euro_2020"},
    {"competition": "UEFA Euro", "year": 2024, "slug": "euro_2024"},
]

ODDS_TEAM_ALIASES = {
    "USA": "United States",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "Curacao": "Curaçao",
    "D.R. Congo": "DR Congo",
    "Korea Republic": "South Korea",
    "IR Iran": "Iran",
    "Czechia": "Czech Republic",
}

ELORATINGS_NAME_ALIASES = {
    "United States of America": "United States",
    "Korea Republic": "South Korea",
    "IR Iran": "Iran",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Côte d’Ivoire": "Ivory Coast",
    "Cote d'Ivoire": "Ivory Coast",
    "Czechia": "Czech Republic",
    "Türkiye": "Turkey",
    "Cape Verde Islands": "Cape Verde",
    "Congo DR": "DR Congo",
}


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


def normalize_team_name(name: str) -> str:
    if name is None or (isinstance(name, float) and pd.isna(name)):
        return name
    return ODDS_TEAM_ALIASES.get(str(name).strip(), str(name).strip())


def process_eloratings_snapshot() -> Path | None:
    world_path = RAW / "eloratings_world.tsv"
    teams_path = RAW / "eloratings_en_teams.tsv"
    if not world_path.exists() or not teams_path.exists():
        return None

    code_to_name: dict[str, str] = {}
    with teams_path.open(newline="", encoding="utf-8") as f:
        for row in csv.reader(f, delimiter="\t"):
            if not row:
                continue
            code = row[0].strip()
            names = [c.strip() for c in row[1:] if c and c.strip()]
            if code and names:
                code_to_name[code] = names[-1]

    world = pd.read_csv(world_path, sep="\t", header=None)
    out = pd.DataFrame(
        {
            "rank": world[0].astype(int),
            "team_code": world[2].astype(str),
            "elo": world[3].astype(float),
            "team": world[2].astype(str).map(lambda c: code_to_name.get(c, c)),
        }
    )
    out["team"] = out["team"].replace(ELORATINGS_NAME_ALIASES)
    out = out.sort_values("rank").reset_index(drop=True)
    dest = PROCESSED / "eloratings_world_snapshot.csv"
    out.to_csv(dest, index=False)
    print(f"Wrote {dest.name} ({len(out)} teams)")
    return dest


def export_wc_odds(xlsx_path: Path) -> list[Path]:
    """Flatten World Cup odds sheets into tidy CSVs under data/odds/."""
    xl = pd.ExcelFile(xlsx_path)
    written: list[Path] = []
    sheet_map = {
        "WorldCup2018": "wc_2018_odds.csv",
        "WorldCup2022": "wc_2022_odds.csv",
        "WorldCup2014": "wc_2014_odds.csv",
        "WorldCup2026": "wc_2026_odds.csv",
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
        if "home_team" in df.columns:
            df["home_team"] = df["home_team"].map(normalize_team_name)
        if "away_team" in df.columns:
            df["away_team"] = df["away_team"].map(normalize_team_name)
        if "match_date" in df.columns:
            df["match_date"] = pd.to_datetime(df["match_date"]).dt.date.astype(str)
        # Implied probabilities from avg decimal odds (overround removed)
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
    fifa_cnc8_path = RAW / "fifa_ranking_cnc8_2020.csv"
    odds_xlsx = ODDS / "WorldCup2026.xlsx"
    elo_world = RAW / "eloratings_world.tsv"
    elo_teams = RAW / "eloratings_en_teams.tsv"

    if not args.skip_download:
        download(RESULTS_URL, results_path)
        download(SHOOTOUTS_URL, shootouts_path)
        download(FIFA_RANK_URL, fifa_path)
        download(FIFA_RANK_CNC8_URL, fifa_cnc8_path)
        download(WC_ODDS_URL, odds_xlsx)
        download(ELORATINGS_WORLD_URL, elo_world)
        download(ELORATINGS_TEAMS_URL, elo_teams)
        for name in (
            "worldcup.json",
            "worldcup.groups.json",
            "worldcup.teams.json",
            "worldcup.stadiums.json",
        ):
            download(f"{OPENFOOTBALL_BASE}/{name}", RAW / f"wc2026_openfootball_{name}")

    results = pd.read_csv(results_path)
    matches = to_model_schema(results)
    matches.to_csv(PROCESSED / "matches_all.csv", index=False)
    print(f"Wrote matches_all.csv ({len(matches)} rows)")

    # Legacy 2010+ slice kept for experimentation; decisions use 2020+.
    recent_2010 = matches[matches["match_date"] >= "2010-01-01"]
    recent_2010.to_csv(PROCESSED / "matches_2010_plus.csv", index=False)
    print(f"Wrote matches_2010_plus.csv ({len(recent_2010)} rows)")

    decision = matches[matches["match_date"] >= DECISION_START]
    decision.to_csv(PROCESSED / "matches_2020_plus.csv", index=False)
    print(
        f"Wrote matches_2020_plus.csv ({len(decision)} rows) "
        f"[DECISION WINDOW from {DECISION_START}]"
    )

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

    # FIFA rankings (full + 2020+ filter)
    fifa = pd.read_csv(fifa_path)
    fifa = fifa.sort_values(["date", "total_points"], ascending=[True, False])
    fifa.to_csv(PROCESSED / "fifa_rankings.csv", index=False)
    fifa_2020 = fifa[fifa["date"] >= DECISION_START]
    fifa_2020.to_csv(PROCESSED / "fifa_rankings_2020_plus.csv", index=False)
    print(f"Wrote fifa_rankings.csv ({len(fifa)} rows)")
    print(f"Wrote fifa_rankings_2020_plus.csv ({len(fifa_2020)} rows)")

    if fifa_cnc8_path.exists():
        cnc8 = pd.read_csv(fifa_cnc8_path)
        cnc8.to_csv(PROCESSED / "fifa_rankings_cnc8_snapshot.csv", index=False)
        print(f"Wrote fifa_rankings_cnc8_snapshot.csv ({len(cnc8)} rows)")

    process_eloratings_snapshot()

    if odds_xlsx.exists():
        export_wc_odds(odds_xlsx)

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
        )

    (PROCESSED / "manifest.json").write_text(
        json.dumps(
            {
                "decision_start": DECISION_START,
                "decision_matches": "data/processed/matches_2020_plus.csv",
                "editions": manifest,
            },
            indent=2,
        )
    )
    print("Wrote processed/manifest.json")


if __name__ == "__main__":
    main()
