"""Elo rating engine for international teams.

Design notes (portfolio framing)
--------------------------------
Elo is a sequential Bayesian-flavoured rating for pairwise contests.
We use it as a *feature* into the Poisson goal model, not as the
final predictor — analogous to using a factor exposure as an input
to a loss distribution rather than equating the factor with P&L itself.

Known limitations
-----------------
- Ignores roster turnover between windows.
- Tournament matches and friendlies share the same K by default
  (optionally configurable).
- No home/away Elo variant; home advantage enters at the Poisson layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass
class EloConfig:
    initial_rating: float = 1500.0
    k_factor: float = 40.0
    k_friendly: float = 20.0
    home_advantage_elo: float = 0.0  # kept at Poisson layer by default
    scale: float = 400.0


@dataclass
class EloState:
    ratings: dict[str, float] = field(default_factory=dict)
    matches_played: dict[str, int] = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)

    def get(self, team_id: str, default: float = 1500.0) -> float:
        return self.ratings.get(team_id, default)


def expected_score(rating_a: float, rating_b: float, scale: float = 400.0) -> float:
    """Probability that A outperforms B under the Elo logistic."""
    return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / scale))


def result_score(home_goals: int, away_goals: int) -> tuple[float, float]:
    if home_goals > away_goals:
        return 1.0, 0.0
    if home_goals < away_goals:
        return 0.0, 1.0
    return 0.5, 0.5


class EloEngine:
    def __init__(self, config: EloConfig | None = None):
        self.config = config or EloConfig()
        self.state = EloState()

    def ensure_team(self, team_id: str) -> None:
        if team_id not in self.state.ratings:
            self.state.ratings[team_id] = self.config.initial_rating
            self.state.matches_played[team_id] = 0

    def update_match(
        self,
        *,
        home_id: str,
        away_id: str,
        home_goals: int,
        away_goals: int,
        match_date: date,
        is_friendly: bool = False,
        is_neutral: bool = False,
    ) -> tuple[float, float]:
        self.ensure_team(home_id)
        self.ensure_team(away_id)

        rh = self.state.ratings[home_id]
        ra = self.state.ratings[away_id]
        if not is_neutral:
            rh_adj = rh + self.config.home_advantage_elo
        else:
            rh_adj = rh

        eh = expected_score(rh_adj, ra, self.config.scale)
        ea = 1.0 - eh
        sh, sa = result_score(home_goals, away_goals)

        k = self.config.k_friendly if is_friendly else self.config.k_factor
        new_rh = rh + k * (sh - eh)
        new_ra = ra + k * (sa - ea)

        self.state.ratings[home_id] = new_rh
        self.state.ratings[away_id] = new_ra
        self.state.matches_played[home_id] += 1
        self.state.matches_played[away_id] += 1

        self.state.history.append(
            {
                "as_of_date": match_date,
                "team_id": home_id,
                "elo_rating": new_rh,
                "matches_played": self.state.matches_played[home_id],
            }
        )
        self.state.history.append(
            {
                "as_of_date": match_date,
                "team_id": away_id,
                "elo_rating": new_ra,
                "matches_played": self.state.matches_played[away_id],
            }
        )
        return new_rh, new_ra

    def fit(self, matches: pd.DataFrame) -> EloState:
        """Fit sequentially on a match frame.

        Required columns: match_date, home_team_id, away_team_id,
        home_goals, away_goals. Optional: is_friendly, is_neutral_venue.
        """
        required = {
            "match_date",
            "home_team_id",
            "away_team_id",
            "home_goals",
            "away_goals",
        }
        missing = required - set(matches.columns)
        if missing:
            raise ValueError(f"matches missing columns: {sorted(missing)}")

        df = matches.sort_values("match_date").copy()
        for row in df.itertuples(index=False):
            is_friendly = bool(getattr(row, "is_friendly", False))
            is_neutral = bool(getattr(row, "is_neutral_venue", False))
            self.update_match(
                home_id=str(row.home_team_id),
                away_id=str(row.away_team_id),
                home_goals=int(row.home_goals),
                away_goals=int(row.away_goals),
                match_date=pd.Timestamp(row.match_date).date(),
                is_friendly=is_friendly,
                is_neutral=is_neutral,
            )
        return self.state

    def history_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.state.history)

    def rating_snapshot(self, team_ids: Iterable[str] | None = None) -> pd.DataFrame:
        ids = list(team_ids) if team_ids is not None else list(self.state.ratings)
        return pd.DataFrame(
            {
                "team_id": ids,
                "elo_rating": [self.state.get(t, self.config.initial_rating) for t in ids],
                "matches_played": [self.state.matches_played.get(t, 0) for t in ids],
            }
        )


def elo_diff_feature(home_elo: float, away_elo: float) -> float:
    """Standardized Elo differential used by the Poisson design matrix."""
    return (home_elo - away_elo) / 100.0


def rating_to_strength(elo: float, baseline: float = 1500.0) -> float:
    """Map Elo to a multiplicative attack/defense proxy around 1.0."""
    return float(np.exp((elo - baseline) / 400.0))
