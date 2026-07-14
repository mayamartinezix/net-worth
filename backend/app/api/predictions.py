"""Prediction and simulation endpoints.

Simulations are intentionally small by default for interactive demos.
Production tournament odds should be served from precomputed
`simulation_results` rows, not live 50k-path runs.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    MatchPredictRequest,
    MatchPredictionResponse,
    ScorelineProb,
    SimulationResponse,
    TeamOdds,
)
from app.services.poisson_model import PoissonMatchModel, PoissonModelConfig
from app.services.simulator import TournamentSimulator, build_demo_world_cup_groups

router = APIRouter(tags=["predictions"])


@router.post("/predict/match", response_model=MatchPredictionResponse)
def predict_match(body: MatchPredictRequest) -> MatchPredictionResponse:
    cfg = PoissonModelConfig(confederation_adjustment=body.use_confederation_adjustment)
    model = PoissonMatchModel(cfg)
    pred = model.predict(
        home_elo=body.home_elo,
        away_elo=body.away_elo,
        home_form=body.home_form,
        away_form=body.away_form,
        is_neutral=body.is_neutral,
        home_confed=body.home_confederation,
        away_confed=body.away_confederation,
    )
    top = [
        ScorelineProb(score=f"{h}-{a}", probability=p)
        for (h, a), p in pred.scoreline_probs.items()
    ]
    return MatchPredictionResponse(
        home_team=body.home_team,
        away_team=body.away_team,
        home_elo=body.home_elo,
        away_elo=body.away_elo,
        p_home=pred.p_home,
        p_draw=pred.p_draw,
        p_away=pred.p_away,
        lambda_home=pred.lambda_home,
        lambda_away=pred.lambda_away,
        top_scorelines=top,
    )


@router.get("/simulate/demo", response_model=SimulationResponse)
def simulate_demo(
    n_sims: int = Query(500, ge=10, le=20_000),
    format_key: str = Query("world_cup_32"),
    seed: int = Query(42),
) -> SimulationResponse:
    if format_key != "world_cup_32":
        raise HTTPException(
            status_code=400,
            detail="Demo endpoint currently ships a World Cup 32-team field only.",
        )
    sim = TournamentSimulator(format_key=format_key, rng_seed=seed)
    groups = build_demo_world_cup_groups()
    result = sim.run(groups, n_sims=n_sims)
    teams = [
        TeamOdds(
            team_id=r["team_id"],
            p_champion=r["p_champion"],
            p_final=r["p_final"],
            p_semifinal=r["p_semifinal"],
            p_quarterfinal=r["p_quarterfinal"],
            p_r16=r["p_r16"],
            p_group_exit=r["p_group_exit"],
            se_champion=r["se_champion"],
        )
        for r in sorted(result.to_records(), key=lambda x: -x["p_champion"])
    ]
    return SimulationResponse(
        format_key=format_key,
        n_sims=n_sims,
        rng_seed=seed,
        teams=teams,
    )
