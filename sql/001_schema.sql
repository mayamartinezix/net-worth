-- Soccer Tournament Prediction Schema
-- World Cup + UEFA Euros Monte Carlo platform

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- Reference / dimension tables
-- ---------------------------------------------------------------------------

CREATE TABLE teams (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fifa_code       VARCHAR(3) NOT NULL UNIQUE,   -- e.g. BRA, FRA
    name            TEXT NOT NULL,
    confederation   VARCHAR(16) NOT NULL,          -- UEFA, CONMEBOL, CAF, AFC, CONCACAF, OFC
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE competitions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            VARCHAR(32) NOT NULL UNIQUE,   -- world_cup | euros
    name            TEXT NOT NULL,
    governing_body  TEXT NOT NULL
);

CREATE TABLE tournament_editions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    competition_id      UUID NOT NULL REFERENCES competitions(id),
    year                SMALLINT NOT NULL,
    host_team_id        UUID REFERENCES teams(id),
    format_config_key   TEXT NOT NULL,             -- maps to config/tournaments/*.json
    start_date          DATE,
    end_date            DATE,
    status              VARCHAR(16) NOT NULL DEFAULT 'scheduled'
                        CHECK (status IN ('scheduled', 'in_progress', 'completed')),
    UNIQUE (competition_id, year)
);

-- ---------------------------------------------------------------------------
-- Match results (historical + live)
-- ---------------------------------------------------------------------------

CREATE TABLE matches (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_edition_id   UUID REFERENCES tournament_editions(id),  -- NULL = friendlies / qualifiers
    competition_id          UUID REFERENCES competitions(id),
    match_date              DATE NOT NULL,
    stage                   VARCHAR(32) NOT NULL,  -- group, round_of_16, quarter, semi, final, ...
    group_name              VARCHAR(8),            -- A, B, ... when applicable
    home_team_id            UUID NOT NULL REFERENCES teams(id),
    away_team_id            UUID NOT NULL REFERENCES teams(id),
    home_goals              SMALLINT,
    away_goals              SMALLINT,
    home_goals_et           SMALLINT,              -- after extra time (nullable)
    away_goals_et           SMALLINT,
    home_penalties          SMALLINT,
    away_penalties          SMALLINT,
    is_neutral_venue        BOOLEAN NOT NULL DEFAULT FALSE,
    is_completed            BOOLEAN NOT NULL DEFAULT FALSE,
    source                  TEXT,                  -- data provenance
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (home_team_id <> away_team_id)
);

CREATE INDEX idx_matches_date ON matches (match_date);
CREATE INDEX idx_matches_edition ON matches (tournament_edition_id);
CREATE INDEX idx_matches_teams ON matches (home_team_id, away_team_id);

-- ---------------------------------------------------------------------------
-- Ratings history (Elo snapshots used as model features)
-- ---------------------------------------------------------------------------

CREATE TABLE team_ratings_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_id         UUID NOT NULL REFERENCES teams(id),
    as_of_date      DATE NOT NULL,
    elo_rating      DOUBLE PRECISION NOT NULL,
    matches_played  INTEGER NOT NULL DEFAULT 0,
    model_version   TEXT NOT NULL DEFAULT 'elo_v1',
    UNIQUE (team_id, as_of_date, model_version)
);

CREATE INDEX idx_ratings_as_of ON team_ratings_history (as_of_date);

-- ---------------------------------------------------------------------------
-- Model registry + batch simulation cache
-- ---------------------------------------------------------------------------

CREATE TABLE model_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name      TEXT NOT NULL,                 -- e.g. bivariate_poisson_v1
    model_version   TEXT NOT NULL,
    trained_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    train_end_date  DATE,                          -- last match date in training window
    params_json     JSONB NOT NULL DEFAULT '{}',
    metrics_json    JSONB NOT NULL DEFAULT '{}',    -- backtest / calibration summaries
    notes           TEXT
);

CREATE TABLE simulation_runs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tournament_edition_id   UUID NOT NULL REFERENCES tournament_editions(id),
    model_run_id            UUID REFERENCES model_runs(id),
    n_sims                  INTEGER NOT NULL,
    as_of_match_id          UUID REFERENCES matches(id),  -- condition on results through this match
    config_snapshot         JSONB NOT NULL,               -- tournament format + model knobs
    started_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at             TIMESTAMPTZ,
    status                  VARCHAR(16) NOT NULL DEFAULT 'running'
                            CHECK (status IN ('running', 'completed', 'failed')),
    rng_seed                BIGINT,
    notes                   TEXT
);

CREATE TABLE simulation_results (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    simulation_run_id   UUID NOT NULL REFERENCES simulation_runs(id) ON DELETE CASCADE,
    team_id             UUID NOT NULL REFERENCES teams(id),
    -- Round-reached probabilities (0–1). Null stages unused by format are left NULL.
    p_group_exit        DOUBLE PRECISION,
    p_r32               DOUBLE PRECISION,
    p_r16               DOUBLE PRECISION,
    p_quarterfinal      DOUBLE PRECISION,
    p_semifinal         DOUBLE PRECISION,
    p_final             DOUBLE PRECISION,
    p_champion          DOUBLE PRECISION NOT NULL,
    -- Monte Carlo standard errors (optional, for convergence diagnostics)
    se_champion         DOUBLE PRECISION,
    UNIQUE (simulation_run_id, team_id)
);

CREATE INDEX idx_sim_results_run ON simulation_results (simulation_run_id);

-- Optional: store favorite matchup probability matrices for the UI
CREATE TABLE match_predictions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_run_id        UUID NOT NULL REFERENCES model_runs(id),
    home_team_id        UUID NOT NULL REFERENCES teams(id),
    away_team_id        UUID NOT NULL REFERENCES teams(id),
    as_of_date          DATE NOT NULL,
    p_home              DOUBLE PRECISION NOT NULL,
    p_draw              DOUBLE PRECISION NOT NULL,
    p_away              DOUBLE PRECISION NOT NULL,
    lambda_home         DOUBLE PRECISION,
    lambda_away         DOUBLE PRECISION,
    scoreline_json      JSONB,                     -- {(hg,ag): prob, ...} truncated
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (model_run_id, home_team_id, away_team_id, as_of_date)
);

COMMENT ON TABLE simulation_results IS
  'Batch-computed Monte Carlo aggregates; never computed live at request time.';
COMMENT ON TABLE team_ratings_history IS
  'Point-in-time Elo ratings; join as_of_date <= match_date for leakage-safe features.';
