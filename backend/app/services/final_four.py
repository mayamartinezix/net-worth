"""Final-four (semifinal) comparison for the live World Cup 2026 stage.

As of the SF slate: France vs Spain, England vs Argentina.
We condition on these four teams already being in the semis and Monte Carlo
only the remaining path (2 semis + final) — the VaR analog of conditioning
on a scenario path that has already realized up to a horizon.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from app.services.poisson_model import PoissonMatchModel
from app.services.tournament_fields import _load_elo_map
from app.services.simulator import TeamState


# Discovered from completed QF results in data/raw (France, Spain, England, Argentina)
WC2026_FINAL_FOUR = {
    "edition": "world_cup_2026",
    "label": "World Cup 2026 — Final Four",
    "as_of": "2026-07-14",
    "semifinals": [
        {"home": "France", "away": "Spain", "date": "2026-07-14"},
        {"home": "England", "away": "Argentina", "date": "2026-07-15"},
    ],
}


@dataclass
class SemiPreview:
    home: str
    away: str
    date: str
    home_elo: float
    away_elo: float
    p_home: float
    p_draw_regulation: float
    p_away: float
    # Knockout win probs after coin-flip on draw
    p_home_advance: float
    p_away_advance: float
    lambda_home: float
    lambda_away: float


def _team(name: str, elo_map: dict[str, float]) -> TeamState:
    return TeamState(
        team_id=name,
        elo=float(elo_map.get(name, 1500.0)),
    )


def compare_final_four(
    *,
    n_sims: int = 5_000,
    seed: int = 42,
    model: PoissonMatchModel | None = None,
) -> dict[str, Any]:
    """Return matchup previews + conditional title odds among the last four."""
    model = model or PoissonMatchModel()
    rng = np.random.default_rng(seed)
    elo_map = _load_elo_map(WC2026_FINAL_FOUR["as_of"])

    teams = {
        name: _team(name, elo_map)
        for semi in WC2026_FINAL_FOUR["semifinals"]
        for name in (semi["home"], semi["away"])
    }

    semi_previews: list[SemiPreview] = []
    for semi in WC2026_FINAL_FOUR["semifinals"]:
        home, away = teams[semi["home"]], teams[semi["away"]]
        pred = model.predict(home_elo=home.elo, away_elo=away.elo, is_neutral=True)
        # Knockout: regulation draw → 50/50 advance
        p_home_adv = pred.p_home + 0.5 * pred.p_draw
        p_away_adv = pred.p_away + 0.5 * pred.p_draw
        semi_previews.append(
            SemiPreview(
                home=home.team_id,
                away=away.team_id,
                date=semi["date"],
                home_elo=home.elo,
                away_elo=away.elo,
                p_home=pred.p_home,
                p_draw_regulation=pred.p_draw,
                p_away=pred.p_away,
                p_home_advance=p_home_adv,
                p_away_advance=p_away_adv,
                lambda_home=pred.lambda_home,
                lambda_away=pred.lambda_away,
            )
        )

    # Monte Carlo remaining: SF1, SF2, Final
    champ = {t: 0 for t in teams}
    final_apps = {t: 0 for t in teams}
    sf1 = WC2026_FINAL_FOUR["semifinals"][0]
    sf2 = WC2026_FINAL_FOUR["semifinals"][1]

    for _ in range(n_sims):
        w1 = _play_ko(model, teams[sf1["home"]], teams[sf1["away"]], rng)
        w2 = _play_ko(model, teams[sf2["home"]], teams[sf2["away"]], rng)
        final_apps[w1] += 1
        final_apps[w2] += 1
        champion = _play_ko(model, teams[w1], teams[w2], rng)
        champ[champion] += 1

    standings = []
    for name, t in teams.items():
        standings.append(
            {
                "team_id": name,
                "elo": t.elo,
                "p_final": final_apps[name] / n_sims,
                "p_champion": champ[name] / n_sims,
                "se_champion": float(
                    np.sqrt(
                        (champ[name] / n_sims)
                        * (1 - champ[name] / n_sims)
                        / n_sims
                    )
                ),
            }
        )
    standings.sort(key=lambda r: -r["p_champion"])

    return {
        "edition": WC2026_FINAL_FOUR["edition"],
        "label": WC2026_FINAL_FOUR["label"],
        "as_of": WC2026_FINAL_FOUR["as_of"],
        "n_sims": n_sims,
        "rng_seed": seed,
        "semifinals": [
            {
                "home": s.home,
                "away": s.away,
                "date": s.date,
                "home_elo": s.home_elo,
                "away_elo": s.away_elo,
                "p_home_regulation": s.p_home,
                "p_draw_regulation": s.p_draw_regulation,
                "p_away_regulation": s.p_away,
                "p_home_advance": s.p_home_advance,
                "p_away_advance": s.p_away_advance,
                "lambda_home": s.lambda_home,
                "lambda_away": s.lambda_away,
            }
            for s in semi_previews
        ],
        "teams": standings,
        "notes": (
            "Conditional on the confirmed final four. Only remaining matches "
            "(2 semis + final) are simulated. Regulation draws resolve via coin-flip."
        ),
    }


def _play_ko(
    model: PoissonMatchModel,
    home: TeamState,
    away: TeamState,
    rng: np.random.Generator,
) -> str:
    score = model.sample_scorelines(
        1, home_elo=home.elo, away_elo=away.elo, is_neutral=True, rng=rng
    )[0]
    hg, ag = int(score[0]), int(score[1])
    if hg > ag:
        return home.team_id
    if ag > hg:
        return away.team_id
    return home.team_id if rng.random() < 0.5 else away.team_id
