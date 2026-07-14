# Vectorization Note

## Claim
Scoreline sampling for Monte Carlo paths should be vectorized in numpy, not drawn in a pure Python loop.

## Measurement
```bash
PYTHONPATH=backend python backend/scripts/vectorization_benchmark.py
```

Output: `artifacts/vectorization_benchmark.json`.

## Expected pattern
| Method | Pattern | Role |
|--------|---------|------|
| Naive loop | `for i in range(N): rng.poisson(...)` | Baseline |
| Vectorized | Build PMF once → `rng.choice` on flattened grid | Production helper |

Speedups are typically **tens to hundreds of times** at N=50k for a single matchup PMF, which matters when every tournament path plays ~50–70 matches.

## Risk-modeling parallel
This is the same instinct as replacing per-scenario Python P&L loops with array shocks × loadings in a VaR engine: clarity of the model math first, then remove interpreter overhead on the hot path without rewriting in a systems language.
