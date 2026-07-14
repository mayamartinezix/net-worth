# PitchPath — Monte Carlo Soccer Tournament Predictor

Portfolio project for **quant / risk-analyst (analyst-who-codes)** roles.

Predicts match outcomes and tournament probabilities for the **FIFA World Cup** and **UEFA Euros** using:

1. **Elo** team strength  
2. **Poisson** scoreline model  
3. **Config-driven Monte Carlo** tournament simulation  

This is the same conceptual stack as Monte Carlo VaR / portfolio loss modeling: risk factors → scenario generation → path-dependent payoff → empirical distribution.

---

## Why this project is framed this way

| Priority | Focus |
|----------|--------|
| 1 (highest) | Model reasoning & validation |
| 2 | Clear code that shows thinking |
| 3 (lowest) | Production infra polish |

Start with the [**model validation memo**](docs/MODEL_VALIDATION.md) — that is the primary portfolio artifact.

Also read:
- [Design decisions](docs/DESIGN_DECISIONS.md) (penalties, confederation toggle, re-sim frequency)
- [Vectorization note](docs/VECTORIZATION.md)

---

## Architecture

```
Data (results) → Postgres → Elo + Poisson (batch)
                           → Monte Carlo simulator (batch, config JSON)
                           → FastAPI (serves cached / demo results)
                           → React UI (bracket + odds)
```

Live page loads do **not** run 50k simulations. Odds are batch-computed and stored in `simulation_results`.

---

## Repository map

```
sql/001_schema.sql          Postgres DDL
config/tournaments/         WC + Euros format configs
backend/app/services/       Elo, Poisson, simulator
backend/app/api/            FastAPI routes
backend/scripts/            Convergence + vectorization analyses
docs/MODEL_VALIDATION.md    Validation memo (first-class deliverable)
frontend/                   React dashboard scaffold
data/sample/                Tiny sample CSVs for smoke tests
```

---

## Quickstart

### Backend

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# API
PYTHONPATH=backend uvicorn app.main:app --reload --app-dir backend --port 8000
```

- Health: `GET /api/v1/health`  
- Match predict: `POST /api/v1/predict/match`  
- Demo tournament MC: `GET /api/v1/simulate/demo?n_sims=500`

### Tests

```bash
PYTHONPATH=backend pytest backend/tests -q
```

### Analyses (portfolio artifacts)

```bash
PYTHONPATH=backend python backend/scripts/vectorization_benchmark.py
PYTHONPATH=backend python backend/scripts/convergence_analysis.py
```

Writes to `artifacts/`.

### Frontend

```bash
cd frontend && npm install && npm run dev
```

### Database

```bash
psql "$DATABASE_URL" -f sql/001_schema.sql
```

---

## Model sketch

**Match layer:**  
\(\lambda_h, \lambda_a\) from Elo differential (+ optional home / form / confederation).  
Scorelines \((H,A)\) ~ independent Poisson (optional Dixon–Coles tweak).  
Win/draw/loss by summing the scoreline grid — needed for group GD tiebreakers.

**Tournament layer:**  
JSON format config → group RR → seeding → knockout (ET skipped; penalties = coin flip) → aggregate over \(N\) paths.

**Monte Carlo error:**  
\(\mathrm{SE}(p)=\sqrt{p(1-p)/N}\). Convergence script compares a favorite vs a long shot.

---

## Build order (status)

| Phase | Status |
|-------|--------|
| 1 Data & ratings (Elo + schema) | Scaffolded |
| 2 Match model (Poisson + rationale) | Implemented |
| 3 Simulation engine + convergence / vectorization | Implemented |
| 4 Full validation memo + historical backtests | Memo template + hooks; backtest numbers TBD with real data pull |
| 5 FastAPI | Demo endpoints live |
| 6 Frontend | Dashboard scaffold |
| 7 Portfolio polish | This README + docs |

---

## Interview talking points

1. Why Poisson over a W/D/L classifier (scorelines feed tiebreakers).  
2. Why MC over analytic brackets (path dependence / best-thirds).  
3. Show calibration + convergence artifacts (model risk instinct).  
4. Config-driven formats ≈ instrument/portfolio parameterization in a risk engine.  
5. Honest limitations: shootouts, sparse upsets, not beating closing markets.
