"""Independent / bivariate Poisson match outcome model.

Why Poisson (model choice rationale)
------------------------------------
Football scores are non-negative integer counts. A Poisson GLM maps
covariates (Elo differential, home advantage, form, optional
confederation effects) onto expected goals λ_home / λ_away in a way that:
  1. respects the support of the outcome,
  2. induces a full scoreline distribution P(H=h, A=a),
  3. marginalizes cleanly to win / draw / loss probabilities.

Alternatives considered and rejected for v1
-------------------------------------------
- Multinomial logistic on {H, D, A}: simpler, but throws away scoreline
  information needed for group-stage goal-difference tiebreakers in the
  tournament simulator.
- Negative binomial: useful if overdispersion is material; empirical
  national-team tournament samples are small enough that NB variance
  parameters are noisy — deferred to a later validation cycle.
- Dixon–Coles low-score adjustment: known improvement for club leagues;
  included as a togglable option below, default off until backtest
  justification is stronger for internationals.

Independence assumption
-----------------------
Default model: H ~ Poisson(λ_h), A ~ Poisson(λ_a) independent.
Optional Dixon–Coles correlation tweak for (0,0),(1,0),(0,1),(1,1).
True bivariate Poisson (shared latent) is stubbed for future work.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import poisson


@dataclass
class PoissonModelConfig:
    max_goals: int = 8
    use_dixon_coles: bool = False
    dixon_coles_rho: float = -0.05
    home_advantage_log: float = 0.20  # ~22% lift in λ_home at neutral=False
    elo_coef: float = 0.35            # log-λ sensitivity to Elo diff / 100
    form_coef: float = 0.15
    confederation_adjustment: bool = False
    confederation_effects: dict[str, float] = field(
        default_factory=lambda: {
            "UEFA": 0.05,
            "CONMEBOL": 0.05,
            "CAF": -0.05,
            "AFC": -0.03,
            "CONCACAF": -0.04,
            "OFC": -0.10,
        }
    )
    base_lambda: float = 1.25


@dataclass
class MatchPrediction:
    p_home: float
    p_draw: float
    p_away: float
    lambda_home: float
    lambda_away: float
    scoreline_probs: dict[tuple[int, int], float]

    def as_dict(self) -> dict[str, Any]:
        return {
            "p_home": self.p_home,
            "p_draw": self.p_draw,
            "p_away": self.p_away,
            "lambda_home": self.lambda_home,
            "lambda_away": self.lambda_away,
            "scoreline_probs": {
                f"{h}-{a}": p for (h, a), p in self.scoreline_probs.items()
            },
        }


class PoissonMatchModel:
    """Feature → λ → scoreline distribution → W/D/L probabilities."""

    def __init__(self, config: PoissonModelConfig | None = None):
        self.config = config or PoissonModelConfig()
        self.is_fitted = False
        self.params_: dict[str, float] = {}

    def _lambda_pair(
        self,
        *,
        home_elo: float,
        away_elo: float,
        home_form: float = 0.0,
        away_form: float = 0.0,
        is_neutral: bool = True,
        home_confed: str | None = None,
        away_confed: str | None = None,
    ) -> tuple[float, float]:
        cfg = self.config
        elo_diff = (home_elo - away_elo) / 100.0
        form_diff = home_form - away_form

        log_lh = np.log(cfg.base_lambda) + cfg.elo_coef * elo_diff + cfg.form_coef * form_diff
        log_la = np.log(cfg.base_lambda) - cfg.elo_coef * elo_diff - cfg.form_coef * form_diff

        if not is_neutral:
            log_lh += cfg.home_advantage_log

        if cfg.confederation_adjustment:
            effects = cfg.confederation_effects
            if home_confed:
                log_lh += effects.get(home_confed, 0.0)
            if away_confed:
                log_la += effects.get(away_confed, 0.0)

        # Allow fitted overrides if calibrate() was run
        if self.is_fitted:
            log_lh = (
                self.params_.get("intercept_home", np.log(cfg.base_lambda))
                + self.params_.get("elo_coef", cfg.elo_coef) * elo_diff
                + self.params_.get("form_coef", cfg.form_coef) * form_diff
            )
            log_la = (
                self.params_.get("intercept_away", np.log(cfg.base_lambda))
                - self.params_.get("elo_coef", cfg.elo_coef) * elo_diff
                - self.params_.get("form_coef", cfg.form_coef) * form_diff
            )
            if not is_neutral:
                log_lh += self.params_.get("home_advantage_log", cfg.home_advantage_log)

        return float(np.exp(log_lh)), float(np.exp(log_la))

    def _dixon_coles_tau(self, h: int, a: int, lh: float, la: float) -> float:
        rho = self.config.dixon_coles_rho
        if h == 0 and a == 0:
            return 1.0 - lh * la * rho
        if h == 0 and a == 1:
            return 1.0 + lh * rho
        if h == 1 and a == 0:
            return 1.0 + la * rho
        if h == 1 and a == 1:
            return 1.0 - rho
        return 1.0

    def scoreline_matrix(self, lambda_home: float, lambda_away: float) -> np.ndarray:
        g = self.config.max_goals
        ph = poisson.pmf(np.arange(g + 1), lambda_home)
        pa = poisson.pmf(np.arange(g + 1), lambda_away)
        # Independence: outer product
        mat = np.outer(ph, pa)

        if self.config.use_dixon_coles:
            for h in range(min(2, g + 1)):
                for a in range(min(2, g + 1)):
                    mat[h, a] *= self._dixon_coles_tau(h, a, lambda_home, lambda_away)

        total = mat.sum()
        if total <= 0:
            raise ValueError("scoreline probabilities summed to zero")
        return mat / total

    def predict(
        self,
        *,
        home_elo: float,
        away_elo: float,
        home_form: float = 0.0,
        away_form: float = 0.0,
        is_neutral: bool = True,
        home_confed: str | None = None,
        away_confed: str | None = None,
    ) -> MatchPrediction:
        lh, la = self._lambda_pair(
            home_elo=home_elo,
            away_elo=away_elo,
            home_form=home_form,
            away_form=away_form,
            is_neutral=is_neutral,
            home_confed=home_confed,
            away_confed=away_confed,
        )
        mat = self.scoreline_matrix(lh, la)
        # home win: lower triangle below diag? mat[h,a] — home goals = row
        p_home = float(np.tril(mat, k=-1).sum())
        p_draw = float(np.trace(mat))
        p_away = float(np.triu(mat, k=1).sum())

        # Keep top scorelines for storage / UI
        flat = [
            ((h, a), float(mat[h, a]))
            for h in range(mat.shape[0])
            for a in range(mat.shape[1])
        ]
        flat.sort(key=lambda x: x[1], reverse=True)
        top = dict(flat[:20])

        return MatchPrediction(
            p_home=p_home,
            p_draw=p_draw,
            p_away=p_away,
            lambda_home=lh,
            lambda_away=la,
            scoreline_probs=top,
        )

    def sample_scorelines(
        self,
        n: int,
        *,
        home_elo: float,
        away_elo: float,
        rng: np.random.Generator | None = None,
        is_neutral: bool = True,
        **kwargs: Any,
    ) -> np.ndarray:
        """Vectorized scoreline draws. Shape (n, 2) → [home_goals, away_goals]."""
        rng = rng or np.random.default_rng()
        pred = self.predict(
            home_elo=home_elo,
            away_elo=away_elo,
            is_neutral=is_neutral,
            **kwargs,
        )
        mat = self.scoreline_matrix(pred.lambda_home, pred.lambda_away)
        g = self.config.max_goals
        probs = mat.ravel()
        idx = rng.choice(probs.size, size=n, p=probs)
        home_goals = idx // (g + 1)
        away_goals = idx % (g + 1)
        return np.column_stack([home_goals, away_goals])

    def calibrate_from_matches(self, df: pd.DataFrame) -> dict[str, float]:
        """Lightweight GLM-style calibration using average goal rates + Elo.

        Required columns: home_goals, away_goals, home_elo, away_elo,
        is_neutral_venue (optional), home_form/away_form (optional).

        Full statsmodels GLM fitting is available in notebooks; this keeps
        the production path dependency-light and readable.
        """
        required = {"home_goals", "away_goals", "home_elo", "away_elo"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"calibration frame missing: {sorted(missing)}")

        elo_diff = (df["home_elo"] - df["away_elo"]) / 100.0
        # Method of moments: regress log(goals+eps) on elo_diff
        eps = 0.25
        y_h = np.log(df["home_goals"].astype(float) + eps)
        y_a = np.log(df["away_goals"].astype(float) + eps)

        # Simple OLS via normal equations for [1, elo_diff]
        x = np.column_stack([np.ones(len(df)), elo_diff.to_numpy()])
        coef_h, _, _, _ = np.linalg.lstsq(x, y_h.to_numpy(), rcond=None)
        coef_a, _, _, _ = np.linalg.lstsq(x, y_a.to_numpy(), rcond=None)

        # Symmetrize Elo sensitivity
        elo_coef = float(0.5 * (coef_h[1] - coef_a[1]))
        intercept_home = float(coef_h[0])
        intercept_away = float(coef_a[0])

        home_adv = 0.0
        if "is_neutral_venue" in df.columns:
            non_neutral = df["is_neutral_venue"] == False  # noqa: E712
            if non_neutral.any():
                ratio = (
                    df.loc[non_neutral, "home_goals"].mean()
                    / max(df.loc[non_neutral, "away_goals"].mean(), 1e-6)
                )
                home_adv = float(np.log(max(ratio, 1e-6)))

        self.params_ = {
            "intercept_home": intercept_home,
            "intercept_away": intercept_away,
            "elo_coef": elo_coef,
            "form_coef": self.config.form_coef,
            "home_advantage_log": home_adv if home_adv else self.config.home_advantage_log,
        }
        self.is_fitted = True
        return self.params_


def recent_form(results: list[float], half_life: float = 4.0) -> float:
    """Exponentially weighted mean of recent match scores in {-1,0,1} or points."""
    if not results:
        return 0.0
    w = np.array([0.5 ** (i / half_life) for i in range(len(results))][::-1])
    r = np.asarray(results, dtype=float)
    return float(np.dot(w, r) / w.sum())
