# Model Validation Memo — Bivariate / Independent Poisson Match Model + Tournament MC

**Model ID:** `poisson_elo_v1` + `tournament_mc_v1`  
**Scope:** FIFA World Cup & UEFA European Championship  
**Audience:** Portfolio / hiring review (analyst-who-codes framing)  
**Status:** Template populated with methodology; historical backtest numbers to be filled after Phase 4 data pull  

---

## 1. Purpose and scope

### Predicts
- Match-level win / draw / loss probabilities and scoreline distributions for international fixtures.
- Tournament-level probabilities: round reached and champion, via Monte Carlo simulation of the full competition format.

### Explicitly does **not** predict
- In-game (live) win probability after minute *t*.
- Player-level availability, red cards, or tactical matchups beyond team ratings.
- Betting edge / recommended stakes (no Kelly overlay; no odds API trading loop).
- Club competitions or women's tournaments (out of scope for v1).

---

## 2. Methodology summary

| Layer | Method | Output |
|-------|--------|--------|
| Team strength | Elo (sequential) | Point-in-time rating |
| Match outcomes | Independent Poisson (optional Dixon–Coles) | P(H,D,A) + scoreline grid |
| Tournament | Config-driven Monte Carlo | Empirical title / round odds |

**Why Poisson (not multinomial W/D/L logistic)?**  
Goals are count data. Tournament group tiebreakers depend on goal difference and goals scored; collapsing to a three-way classifier discards the scoreline distribution the simulator needs. A logistic classifier is retained as a *baseline comparator* in backtests, not as the production path model.

**Why Monte Carlo (not analytic bracket probabilities)?**  
Group-stage path dependence, best-third ranking (Euros), and tiebreakers make closed-form propagation intractable. MC is the same pattern used for portfolio loss distributions with path-dependent payoffs.

---

## 3. Assumptions

1. **Conditional independence of matches** given pre-match ratings / form. No explicit momentum, tournament fatigue, or revenge effects.
2. **Stable Elo → goals mapping** within a tournament window (ratings frozen or slow-updated; re-simulation after completed matches).
3. **Penalty shootouts ≈ coin flip** after a knockout draw in regulation (+ ET not separately modeled as a second Poisson). Rationale: small sample, weak skill signal at national-team level after conditioning on reaching a shootout.
4. **Neutral venue** for tournament matches unless host advantage is toggled on.
5. **Confederation strength adjustment off by default** — easy to overfit on sparse inter-confederation samples; toggle exists for sensitivity runs.
6. **Simulation error** scales as \(1/\sqrt{N}\). Production odds use N large enough that SE on favorites is small vs. decision thresholds (see convergence artifact).

---

## 4. Data sources and known limitations

| Source | Use | Location | Caveat |
|--------|-----|----------|--------|
| Historical international results | Elo fit + Poisson calibration | `data/raw/results.csv` → `data/processed/` | Friendly motivation varies; down-weighted K |
| Tournament editions (WC/Euros) | Backtest windows | `data/processed/matches_{wc,euro}_*.csv` | Euro 2020 staged in 2021 |
| FIFA rankings | Naive baseline | `data/processed/fifa_rankings.csv` | Slow-moving vs Elo |
| Betting-market odds (WC) | External benchmark | `data/odds/wc_2018_odds.csv`, `wc_2022_odds.csv` | Avg decimal odds; overround removed in ingest |
| Betting-market odds (Euros) | External benchmark | **Drop into** `data/odds/euro_*_odds.csv` | Not in the free WC workbook — optional |

Refresh instructions: [DATA.md](DATA.md).

**Sample-size caveat:** A World Cup has 64 matches; one tournament is not a large IID sample. Backtests must pool across multiple editions and treat calibration bins carefully.

**Survivorship / selection:** Teams that repeatedly qualify are stronger on average; ratings use all internationals where possible to reduce qualifier-only selection bias.

---

## 5. Backtest plan (fill results here)

Tournaments:
- World Cup: 2018, 2022  
- Euros: 2016, 2020, 2024  

### Metrics
- **Match level:** log-loss, Brier score on {H,D,A}; ranked probability score.
- **Tournament level:** average rank of true champion in predicted title odds; realized round vs. predicted P(reach round).
- **Baselines:** (i) FIFA ranking ordinal logit / Elo-diff only multinomial, (ii) betting-market implied probabilities where archived.

### Results table (placeholder)

| Tournament | Model log-loss | FIFA-baseline log-loss | Market log-loss | Notes |
|------------|----------------|------------------------|-----------------|-------|
| WC 2018 | _TBD_ | _TBD_ | _TBD_ | |
| WC 2022 | _TBD_ | _TBD_ | _TBD_ | |
| Euro 2016 | _TBD_ | _TBD_ | _TBD_ | |
| Euro 2020 | _TBD_ | _TBD_ | _TBD_ | |
| Euro 2024 | _TBD_ | _TBD_ | _TBD_ | |

---

## 6. Calibration check

Bucket predicted win probabilities into deciles (or fixed bins: 0–10%, …, 90–100%) and plot **predicted mid-bin probability vs. observed win frequency**.

- Well-calibrated model sits on the 45° line.
- This is the same artifact used in PD model validation / probability-of-default monitoring.

Script target: `backend/scripts/calibration_plot.py` (Phase 4).  
Artifact target: `artifacts/calibration_plot.png`.

---

## 7. Monte Carlo diagnostics

See `artifacts/convergence_plot.png` and `artifacts/convergence_results.json` from:

```bash
PYTHONPATH=backend python backend/scripts/convergence_analysis.py
```

Expectation:
- Favorite title probability stabilizes faster in *relative* terms than a long shot at low N.
- Absolute SE is \(\sqrt{p(1-p)/N}\); for rare events, CV \(=\sqrt{(1-p)/(Np)}\) stays large longer — same reason low-default portfolios need more scenarios for tail quantiles.

Vectorization timing: `backend/scripts/vectorization_benchmark.py` → `artifacts/vectorization_benchmark.json`.

---

## 8. Known weaknesses (honest)

1. **Shootouts** — intentionally near-random; knockout variance is understated if a team is systematically strong/weak at penalties.
2. **Sparse upsets** — Poisson with Elo can understate heavy-tailed upset rates early in tournaments; Dixon–Coles / NB remediations are sensitivity options, not proven wins for internationals yet.
3. **Roster shocks** — injuries to primary creators are not modeled; post-match Elo updates partially absorb results but not *ex ante* absences.
4. **Format sensitivity** — Euros best-thirds bracket chart is approximated; exact UEFA pairing tables should be fully encoded before claiming edition-accurate path odds.
5. **Does not beat closing markets** — expected for a public-info Elo/Poisson stack. Value for this project is *process quality* (validation, convergence, assumptions), not claimed alpha.

---

## 9. Design decisions log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Penalty model | Fair coin | Empirical near-50/50; avoids fake precision |
| Confederation adj. | Default off | Overfit risk; toggle for sensitivity |
| Re-simulation | After each completed tournament match (batch job) | Matches risk-engine batch recalcs after market moves; no live 50k on page load |
| Storage | Cache `simulation_results` | Same pattern as precomputed scenario sets |
| Independent vs bivariate Poisson | Independent default | Parsimony; correlation optional via Dixon–Coles |

---

## 10. Sign-off checklist (portfolio review)

- [ ] Assumptions listed and challenged  
- [ ] Baseline comparison present  
- [ ] Calibration plot generated on held-out internationals  
- [ ] Convergence curve for favorite + long shot  
- [ ] Limitations section non-empty and specific  
- [ ] Config-driven formats (no hardcoded WC-only logic in engine core)  

---

*This memo is a first-class deliverable of the project, not documentation afterthought. In interview settings, walk through §3 → §6 → §8 before UI screenshots.*
