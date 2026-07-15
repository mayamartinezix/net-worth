"""Prediction and simulation endpoints.

Simulations default to small N for interactive demos.
Production tournament odds should be served from precomputed
`simulation_results` rows, not live 50k-path runs.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import (
    CompetitionInfo,
    CompetitionsResponse,
    FieldTeamsResponse,
    FinalFourResponse,
    FinalFourTeam,
    JointRoundOdds,
    MatchPredictRequest,
    MatchPredictionResponse,
    ScorelineProb,
    SemifinalPreview,
    SimulationResponse,
    TeamOdds,
    TeamRoundOdds,
    TeamRoundOddsResponse,
)
from app.services.final_four import compare_final_four
from app.services.poisson_model import PoissonMatchModel, PoissonModelConfig
from app.services.simulator import TournamentSimulator, build_demo_world_cup_groups
from app.services.tournament_fields import build_euro2024_groups, build_wc2026_groups

router = APIRouter(tags=["predictions"])

COMPETITIONS = {
    "world_cup_2026": {
        "label": "FIFA World Cup 2026",
        "format_key": "world_cup_48",
        "n_teams": 48,
        "builder": build_wc2026_groups,
    },
    "euros_2024": {
        "label": "UEFA Euro 2024",
        "format_key": "euros_24",
        "n_teams": 24,
        "builder": build_euro2024_groups,
    },
}


def _resolve_competition(competition: str) -> tuple[str, str, str, dict]:
    if competition == "world_cup_32_legacy":
        return (
            "world_cup_32_legacy",
            "world_cup_32",
            "World Cup 32 (legacy demo)",
            build_demo_world_cup_groups(),
        )
    if competition in COMPETITIONS:
        meta = COMPETITIONS[competition]
        return (
            competition,
            meta["format_key"],
            meta["label"],
            meta["builder"](),
        )
    raise HTTPException(
        status_code=400,
        detail=f"Unknown competition '{competition}'. "
        f"Use one of: {', '.join([*COMPETITIONS, 'world_cup_32_legacy'])}",
    )


@router.get("/competitions", response_model=CompetitionsResponse)
def list_competitions() -> CompetitionsResponse:
    return CompetitionsResponse(
        competitions=[
            CompetitionInfo(
                id=cid,
                label=meta["label"],
                format_key=meta["format_key"],
                n_teams=meta["n_teams"],
            )
            for cid, meta in COMPETITIONS.items()
        ]
    )


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
    competition: str = Query(
        "world_cup_2026",
        description="world_cup_2026 | euros_2024 | world_cup_32_legacy",
    ),
    n_sims: int = Query(250, ge=10, le=5_000),
    seed: int = Query(42),
) -> SimulationResponse:
    competition, format_key, label, groups = _resolve_competition(competition)

    sim = TournamentSimulator(format_key=format_key, rng_seed=seed)
    result = sim.run(groups, n_sims=n_sims)
    teams = [
        TeamOdds(
            team_id=r["team_id"],
            p_champion=r["p_champion"],
            p_final=r["p_final"],
            p_semifinal=r["p_semifinal"],
            p_quarterfinal=r["p_quarterfinal"],
            p_r16=r["p_r16"],
            p_r32=r.get("p_r32", 0.0),
            p_group_exit=r["p_group_exit"],
            se_champion=r["se_champion"],
        )
        for r in sorted(result.to_records(), key=lambda x: -x["p_champion"])
    ]
    return SimulationResponse(
        competition=competition,
        format_key=format_key,
        label=label,
        n_sims=n_sims,
        rng_seed=seed,
        teams=teams,
    )


@router.get("/competitions/{competition_id}/teams", response_model=FieldTeamsResponse)
def list_field_teams(competition_id: str) -> FieldTeamsResponse:
    competition, _format_key, label, groups = _resolve_competition(competition_id)
    teams = sorted({t.team_id for group in groups.values() for t in group})
    return FieldTeamsResponse(competition=competition, label=label, teams=teams)


@router.get("/odds/teams", response_model=TeamRoundOddsResponse)
def team_round_odds(
    team: list[str] = Query(
        ...,
        min_length=1,
        max_length=2,
        description="One or two team names from the competition field",
    ),
    competition: str = Query(
        "world_cup_2026",
        description="world_cup_2026 | euros_2024 | world_cup_32_legacy",
    ),
    n_sims: int = Query(1_000, ge=50, le=10_000),
    seed: int = Query(42),
) -> TeamRoundOddsResponse:
    """Round-reach probabilities for one or two selected teams."""
    selected = list(dict.fromkeys(team))  # preserve order, drop dupes
    if len(selected) > 2:
        raise HTTPException(status_code=400, detail="Select at most two teams.")

    competition, format_key, label, groups = _resolve_competition(competition)
    field_teams = {t.team_id for group in groups.values() for t in group}
    unknown = [t for t in selected if t not in field_teams]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown team(s) for {competition}: {unknown}",
        )

    sim = TournamentSimulator(format_key=format_key, rng_seed=seed)
    try:
        result = sim.run(groups, n_sims=n_sims, watch=selected)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    teams_out = [
        TeamRoundOdds(
            team_id=tid,
            p_quarterfinal=result.p_quarterfinal[tid],
            p_semifinal=result.p_semifinal[tid],
            p_final=result.p_final[tid],
            p_champion=result.p_champion[tid],
        )
        for tid in selected
    ]
    joint = None
    if len(selected) == 2 and result.joint_both_quarterfinal is not None:
        joint = JointRoundOdds(
            p_both_quarterfinal=result.joint_both_quarterfinal,
            p_both_semifinal=result.joint_both_semifinal or 0.0,
            p_both_final=result.joint_both_final or 0.0,
        )

    return TeamRoundOddsResponse(
        competition=competition,
        label=label,
        n_sims=n_sims,
        rng_seed=seed,
        teams=teams_out,
        joint=joint,
    )


@router.get("/final-four/world_cup_2026", response_model=FinalFourResponse)
def world_cup_2026_final_four(
    n_sims: int = Query(3_000, ge=100, le=50_000),
    seed: int = Query(42),
) -> FinalFourResponse:
    """Compare the confirmed World Cup 2026 semifinalists."""
    raw = compare_final_four(n_sims=n_sims, seed=seed)
    return FinalFourResponse(
        edition=raw["edition"],
        label=raw["label"],
        as_of=raw["as_of"],
        n_sims=raw["n_sims"],
        rng_seed=raw["rng_seed"],
        semifinals=[SemifinalPreview(**s) for s in raw["semifinals"]],
        teams=[FinalFourTeam(**t) for t in raw["teams"]],
        notes=raw["notes"],
    )
