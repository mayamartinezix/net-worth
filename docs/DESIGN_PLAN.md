# Design Plan: Soccer Tournament Prediction Web App

### Scope: FIFA World Cup + UEFA Euros
### Framed as a portfolio project for quant/risk-analyst roles (analyst-who-codes leaning)

See the repository README for implementation status. This document captures the original product design intent.

---

## 0. Why this framing matters

This project's real value, beyond being a working app, is that it's a small, self-contained demonstration of Monte Carlo simulation methodology — the same conceptual machinery used in Monte Carlo VaR, CVA, and portfolio loss distribution modeling. Priority order:

1. **Model reasoning and validation** — highest weight
2. **Clear, readable code that shows your thinking**
3. **Engineering robustness at scale** — lowest priority

---

## 1. Product Overview

Predicts match outcomes and tournament-wide probabilities (round reached, tournament winner) for the FIFA World Cup and UEFA Euros, using a statistical match model combined with Monte Carlo tournament simulation.

**Core features (v1):**
- Match prediction: win/draw/loss probabilities + scoreline distribution
- Tournament dashboard: title odds and round-reached odds
- Live-updating predictions after each real match (batch re-sim)
- Bracket visualization
- **Model validation write-up** as a first-class deliverable (`docs/MODEL_VALIDATION.md`)

---

## 2–7. Architecture, stack, model, simulation

Implemented under `sql/`, `config/tournaments/`, `backend/app/services/`, and documented in the README. Key additions:

- **7.1 Convergence analysis** — `backend/scripts/convergence_analysis.py`
- **7.2 Vectorization write-up** — `docs/VECTORIZATION.md` + benchmark script

---

## 8. Model validation

See `docs/MODEL_VALIDATION.md`.

---

## 9. Build order

Tracked in the README status table.

---

## 10. Open design decisions

Locked for v1 in `docs/DESIGN_DECISIONS.md`.
