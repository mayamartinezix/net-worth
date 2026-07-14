"""Pydantic schemas for API responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ScorelineProb(BaseModel):
    score: str
    probability: float


class MatchPredictionResponse(BaseModel):
    home_team: str
    away_team: str
    home_elo: float
    away_elo: float
    p_home: float
    p_draw: float
    p_away: float
    lambda_home: float
    lambda_away: float
    top_scorelines: list[ScorelineProb]


class MatchPredictRequest(BaseModel):
    home_team: str
    away_team: str
    home_elo: float = Field(..., description="Elo rating for home/side A")
    away_elo: float = Field(..., description="Elo rating for away/side B")
    home_form: float = 0.0
    away_form: float = 0.0
    is_neutral: bool = True
    home_confederation: str | None = None
    away_confederation: str | None = None
    use_confederation_adjustment: bool = False


class TeamOdds(BaseModel):
    team_id: str
    p_champion: float
    p_final: float
    p_semifinal: float
    p_quarterfinal: float
    p_r16: float
    p_r32: float = 0.0
    p_group_exit: float
    se_champion: float


class SimulationResponse(BaseModel):
    competition: str
    format_key: str
    label: str
    n_sims: int
    rng_seed: int | None
    teams: list[TeamOdds]


class CompetitionInfo(BaseModel):
    id: str
    label: str
    format_key: str
    n_teams: int


class CompetitionsResponse(BaseModel):
    competitions: list[CompetitionInfo]


class HealthResponse(BaseModel):
    status: str
    app: str
