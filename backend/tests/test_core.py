"""Unit tests for Elo, Poisson model, and tournament simulator."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from app.services.elo import EloEngine, expected_score
from app.services.poisson_model import PoissonMatchModel, PoissonModelConfig
from app.services.simulator import TournamentSimulator, build_demo_world_cup_groups


def test_expected_score_symmetric():
    assert expected_score(1500, 1500) == pytest.approx(0.5)
    e = expected_score(1700, 1500)
    assert e > 0.5
    assert expected_score(1500, 1700) == pytest.approx(1 - e)


def test_elo_updates_on_upset():
    eng = EloEngine()
    before_a = eng.state.get("A")
    before_b = eng.state.get("B")
    # Ensure initialized
    eng.ensure_team("A")
    eng.ensure_team("B")
    eng.state.ratings["A"] = 1800
    eng.state.ratings["B"] = 1500
    eng.update_match(
        home_id="A",
        away_id="B",
        home_goals=0,
        away_goals=1,
        match_date=__import__("datetime").date(2022, 1, 1),
        is_neutral=True,
    )
    assert eng.state.ratings["A"] < 1800
    assert eng.state.ratings["B"] > 1500


def test_elo_fit_history():
    df = pd.DataFrame(
        {
            "match_date": ["2022-01-01", "2022-01-08"],
            "home_team_id": ["A", "B"],
            "away_team_id": ["B", "C"],
            "home_goals": [2, 1],
            "away_goals": [0, 1],
            "is_neutral_venue": [True, True],
        }
    )
    eng = EloEngine()
    eng.fit(df)
    hist = eng.history_frame()
    assert len(hist) == 4
    assert set(eng.state.ratings) == {"A", "B", "C"}


def test_poisson_probs_sum_to_one():
    model = PoissonMatchModel()
    pred = model.predict(home_elo=1800, away_elo=1700, is_neutral=True)
    assert pred.p_home + pred.p_draw + pred.p_away == pytest.approx(1.0, abs=1e-9)
    assert pred.lambda_home > 0 and pred.lambda_away > 0


def test_favorite_has_higher_win_prob():
    model = PoissonMatchModel()
    pred = model.predict(home_elo=2100, away_elo=1500, is_neutral=True)
    assert pred.p_home > pred.p_away
    assert pred.p_home > pred.p_draw


def test_sample_scorelines_shape():
    model = PoissonMatchModel()
    rng = np.random.default_rng(0)
    s = model.sample_scorelines(1000, home_elo=1600, away_elo=1600, rng=rng)
    assert s.shape == (1000, 2)
    assert s.min() >= 0


def test_calibrate_sets_params():
    rng = np.random.default_rng(1)
    n = 200
    elo_h = rng.normal(1600, 150, n)
    elo_a = rng.normal(1600, 150, n)
    # synthetic goals
    diff = (elo_h - elo_a) / 100
    lh = np.exp(0.2 + 0.3 * diff)
    la = np.exp(0.2 - 0.3 * diff)
    df = pd.DataFrame(
        {
            "home_elo": elo_h,
            "away_elo": elo_a,
            "home_goals": rng.poisson(lh),
            "away_goals": rng.poisson(la),
            "is_neutral_venue": True,
        }
    )
    model = PoissonMatchModel()
    params = model.calibrate_from_matches(df)
    assert model.is_fitted
    assert "elo_coef" in params


def test_simulator_probabilities_sum_to_one():
    sim = TournamentSimulator(format_key="world_cup_32", rng_seed=123)
    groups = build_demo_world_cup_groups()
    agg = sim.run(groups, n_sims=200)
    total = sum(agg.p_champion.values())
    assert total == pytest.approx(1.0, abs=1e-9)
    assert len(agg.team_ids) == 32
    # SE formula check for one team
    tid = agg.team_ids[0]
    p = agg.p_champion[tid]
    assert agg.se_champion[tid] == pytest.approx(math.sqrt(p * (1 - p) / 200), rel=1e-9)


def test_dixon_coles_toggle():
    m1 = PoissonMatchModel(PoissonModelConfig(use_dixon_coles=False))
    m2 = PoissonMatchModel(PoissonModelConfig(use_dixon_coles=True, dixon_coles_rho=-0.1))
    p1 = m1.predict(home_elo=1600, away_elo=1600)
    p2 = m2.predict(home_elo=1600, away_elo=1600)
    # Both valid distributions
    assert abs((p1.p_home + p1.p_draw + p1.p_away) - 1) < 1e-9
    assert abs((p2.p_home + p2.p_draw + p2.p_away) - 1) < 1e-9
