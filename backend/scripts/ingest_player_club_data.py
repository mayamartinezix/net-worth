#!/usr/bin/env python3
"""Download squad / club-performance inputs and build squad_strength_wc2026.csv."""

from __future__ import annotations

import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "players"

URLS = {
    "rt_squads.csv": "https://raw.githubusercontent.com/risingtransfers/world-cup-2026-data/main/data/squads.csv",
    "rt_per90.csv": "https://raw.githubusercontent.com/risingtransfers/world-cup-2026-data/main/data/per90_stats.csv",
    "wc2026_squads_players.csv": "https://raw.githubusercontent.com/mominullptr/FIFA-World-Cup-2026-Dataset/main/squads_and_players.csv",
    "wc2026_player_stats.csv": "https://raw.githubusercontent.com/mominullptr/FIFA-World-Cup-2026-Dataset/main/player_stats.csv",
    "wc2026_teams.csv": "https://raw.githubusercontent.com/mominullptr/FIFA-World-Cup-2026-Dataset/main/teams.csv",
    "clubelo_latest.csv": "http://api.clubelo.com/2026-06-01",
}


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, url in URLS.items():
        dest = RAW / name
        print(f"Downloading {url} -> {dest}")
        urllib.request.urlretrieve(url, dest)

    import sys

    sys.path.insert(0, str(ROOT / "backend"))
    from app.services.squad_strength import write_squad_strength

    out = write_squad_strength()
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
