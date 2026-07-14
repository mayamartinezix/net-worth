"""Naive Python loop vs numpy vectorized scoreline sampling timing.

Run:
  PYTHONPATH=backend python backend/scripts/vectorization_benchmark.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.stats import poisson

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.poisson_model import PoissonMatchModel  # noqa: E402

ARTIFACTS = ROOT / "artifacts"
ARTIFACTS.mkdir(exist_ok=True)


def naive_loop_sample(lh: float, la: float, n: int, max_goals: int, rng: np.random.Generator):
    """Intentionally slow baseline: Python loop + rejection-style CDF inversion."""
    out = np.empty((n, 2), dtype=int)
    for i in range(n):
        # Independent Poisson via scipy one-at-a-time (pessimistic baseline)
        out[i, 0] = min(int(rng.poisson(lh)), max_goals)
        out[i, 1] = min(int(rng.poisson(la)), max_goals)
    return out


def vectorized_choice_sample(lh: float, la: float, n: int, max_goals: int, rng: np.random.Generator):
    ph = poisson.pmf(np.arange(max_goals + 1), lh)
    pa = poisson.pmf(np.arange(max_goals + 1), la)
    mat = np.outer(ph, pa)
    mat /= mat.sum()
    probs = mat.ravel()
    idx = rng.choice(probs.size, size=n, p=probs)
    return np.column_stack([idx // (max_goals + 1), idx % (max_goals + 1)])


def main() -> None:
    model = PoissonMatchModel()
    pred = model.predict(home_elo=2000, away_elo=1700, is_neutral=True)
    lh, la = pred.lambda_home, pred.lambda_away
    max_goals = model.config.max_goals
    n = 50_000

    rng1 = np.random.default_rng(0)
    t0 = time.perf_counter()
    naive_loop_sample(lh, la, n, max_goals, rng1)
    t_naive = time.perf_counter() - t0

    rng2 = np.random.default_rng(0)
    t0 = time.perf_counter()
    vectorized_choice_sample(lh, la, n, max_goals, rng2)
    t_vec = time.perf_counter() - t0

    # Also time the model helper
    rng3 = np.random.default_rng(0)
    t0 = time.perf_counter()
    model.sample_scorelines(n, home_elo=2000, away_elo=1700, rng=rng3)
    t_model = time.perf_counter() - t0

    result = {
        "n": n,
        "lambda_home": lh,
        "lambda_away": la,
        "seconds_naive_loop": t_naive,
        "seconds_vectorized_choice": t_vec,
        "seconds_model_helper": t_model,
        "speedup_vs_naive": t_naive / t_vec if t_vec > 0 else None,
        "notes": (
            "Naive baseline draws Poisson margins in a Python for-loop. "
            "Vectorized path builds the scoreline PMF once and samples with numpy choice. "
            "This is the analog of vectorizing risk-factor shocks in a VaR engine."
        ),
    }
    out = ARTIFACTS / "vectorization_benchmark.json"
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
