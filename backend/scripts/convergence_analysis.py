"""Convergence analysis for Monte Carlo title probabilities.

Demonstrates the classic Monte Carlo SE scaling: SE ∝ 1/√N.

Run:
  PYTHONPATH=backend python backend/scripts/convergence_analysis.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.simulator import TournamentSimulator, build_demo_world_cup_groups  # noqa: E402

ARTIFACTS = ROOT / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)


def bernoulli_se(p: float, n: int) -> float:
    return float(np.sqrt(p * (1.0 - p) / n))


def main() -> None:
    # Use one long run as the "truth" proxy, then subsample conceptual N grid
    # via independent runs at each N (cleaner for demos than circular
    # subsample of a single stream).
    ns = [1_000, 5_000, 10_000, 25_000]
    groups = build_demo_world_cup_groups()

    favorite = "BRA"
    # Relative outsider vs favorite (deep minnows can be exactly 0 under wide Elo gaps)
    longshot = "CRO"

    rows = []
    for n in ns:
        sim = TournamentSimulator(format_key="world_cup_32", rng_seed=10_000 + n)
        agg = sim.run(groups, n_sims=n)
        rows.append(
            {
                "n": n,
                "favorite": favorite,
                "p_favorite": agg.p_champion[favorite],
                "se_favorite": agg.se_champion[favorite],
                "longshot": longshot,
                "p_longshot": agg.p_champion[longshot],
                "se_longshot": agg.se_champion[longshot],
                "theory_se_favorite": bernoulli_se(agg.p_champion[favorite], n),
                "theory_se_longshot": bernoulli_se(agg.p_champion[longshot], n),
            }
        )
        print(
            f"N={n:,}  {favorite}={agg.p_champion[favorite]:.4f}±{agg.se_champion[favorite]:.4f}  "
            f"{longshot}={agg.p_champion[longshot]:.4f}±{agg.se_champion[longshot]:.4f}"
        )

    out_json = ARTIFACTS / "convergence_results.json"
    out_json.write_text(json.dumps(rows, indent=2))

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharex=True)
    ns_arr = [r["n"] for r in rows]

    for ax, key_p, key_se, title in [
        (axes[0], "p_favorite", "se_favorite", f"Favorite ({favorite})"),
        (axes[1], "p_longshot", "se_longshot", f"Long shot ({longshot})"),
    ]:
        p = np.array([r[key_p] for r in rows])
        se = np.array([r[key_se] for r in rows])
        ax.errorbar(ns_arr, p, yerr=1.96 * se, fmt="o-", capsize=4, color="#1a5f4a")
        ax.set_xscale("log")
        ax.set_xlabel("N simulations")
        ax.set_ylabel("P(champion)")
        ax.set_title(title)
        ax.grid(True, alpha=0.3)

    fig.suptitle("Monte Carlo convergence — title probability vs N", fontsize=12)
    fig.tight_layout()
    fig_path = ARTIFACTS / "convergence_plot.png"
    fig.savefig(fig_path, dpi=140)
    print(f"Wrote {out_json}")
    print(f"Wrote {fig_path}")

    # Relative SE note: long shots have larger CV at low N
    rel = []
    for r in rows:
        rel.append(
            {
                "n": r["n"],
                "cv_favorite": r["se_favorite"] / max(r["p_favorite"], 1e-12),
                "cv_longshot": r["se_longshot"] / max(r["p_longshot"], 1e-12),
            }
        )
    (ARTIFACTS / "convergence_cv.json").write_text(json.dumps(rel, indent=2))


if __name__ == "__main__":
    main()
