"""Fit Elo ratings from a match CSV and write a snapshot.

Example:
  PYTHONPATH=backend python backend/scripts/fit_elo.py \\
    --matches data/sample/matches_sample.csv \\
    --out artifacts/elo_snapshot.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from app.services.elo import EloEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit Elo from match results CSV")
    parser.add_argument("--matches", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("artifacts/elo_snapshot.csv"))
    args = parser.parse_args()

    df = pd.read_csv(args.matches)
    engine = EloEngine()
    engine.fit(df)
    snap = engine.rating_snapshot().sort_values("elo_rating", ascending=False)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    snap.to_csv(args.out, index=False)
    hist = engine.history_frame()
    hist_path = args.out.with_name(args.out.stem + "_history.csv")
    hist.to_csv(hist_path, index=False)
    print(f"Wrote {args.out} ({len(snap)} teams)")
    print(f"Wrote {hist_path} ({len(hist)} rows)")


if __name__ == "__main__":
    main()
