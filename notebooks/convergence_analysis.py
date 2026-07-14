"""
# Convergence analysis notebook (Python script twin)

Prefer the script for CI / cloud agents:

```bash
PYTHONPATH=backend python backend/scripts/convergence_analysis.py
```

This notebook mirrors that workflow for interactive exploration.

## Setup
"""

# %%
import json
from pathlib import Path

import matplotlib.pyplot as plt
import sys

ROOT = Path("..").resolve()
sys.path.insert(0, str(ROOT / "backend"))

from app.services.simulator import TournamentSimulator, build_demo_world_cup_groups

# %%
ns = [1000, 5000, 10000]
groups = build_demo_world_cup_groups()
favorite, longshot = "BRA", "QAT"
rows = []
for n in ns:
    agg = TournamentSimulator("world_cup_32", rng_seed=n).run(groups, n_sims=n)
    rows.append(
        {
            "n": n,
            "p_favorite": agg.p_champion[favorite],
            "se_favorite": agg.se_champion[favorite],
            "p_longshot": agg.p_champion[longshot],
            "se_longshot": agg.se_champion[longshot],
        }
    )
rows

# %%
fig, ax = plt.subplots()
ax.errorbar(
    [r["n"] for r in rows],
    [r["p_favorite"] for r in rows],
    yerr=[1.96 * r["se_favorite"] for r in rows],
    label=favorite,
)
ax.set_xscale("log")
ax.set_xlabel("N")
ax.set_ylabel("P(champion)")
ax.legend()
fig
