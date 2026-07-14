"""Config-driven Monte Carlo tournament simulator.

Conceptual parallel (risk modeling)
-----------------------------------
This is the same machinery as a Monte Carlo VaR / portfolio loss engine:
  1. specify a risk-factor → outcome model (here: Elo → Poisson goals),
  2. draw many scenarios,
  3. apply a path-dependent payoff function (here: group standings →
     knockout bracket → champion),
  4. aggregate the empirical distribution (title odds ≡ P(loss > threshold)
     analog).

Vectorization note
------------------
Scorelines for a fixed matchup are drawn in a single numpy choice call
(see PoissonMatchModel.sample_scorelines). Group-stage standings still
use Python loops over teams because N_teams is tiny (24–32); the
expensive part is match sampling, which is vectorized across sims when
batching identical matchups.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.services.poisson_model import PoissonMatchModel


ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "config" / "tournaments"


def load_tournament_config(key: str) -> dict[str, Any]:
    path = CONFIG_DIR / f"{key}.json"
    if not path.exists():
        raise FileNotFoundError(f"Tournament config not found: {path}")
    with path.open() as f:
        return json.load(f)


@dataclass
class TeamState:
    team_id: str
    elo: float
    form: float = 0.0
    confederation: str | None = None
    group: str | None = None


@dataclass
class StandingsRow:
    team_id: str
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    gf: int = 0
    ga: int = 0
    points: int = 0

    @property
    def gd(self) -> int:
        return self.gf - self.ga

    def sort_key(self) -> tuple:
        return (self.points, self.gd, self.gf)


@dataclass
class SimulationAggregate:
    n_sims: int
    team_ids: list[str]
    p_champion: dict[str, float]
    p_final: dict[str, float]
    p_semifinal: dict[str, float]
    p_quarterfinal: dict[str, float]
    p_r16: dict[str, float]
    p_group_exit: dict[str, float]
    se_champion: dict[str, float] = field(default_factory=dict)

    def to_records(self) -> list[dict[str, Any]]:
        rows = []
        for tid in self.team_ids:
            rows.append(
                {
                    "team_id": tid,
                    "p_champion": self.p_champion.get(tid, 0.0),
                    "p_final": self.p_final.get(tid, 0.0),
                    "p_semifinal": self.p_semifinal.get(tid, 0.0),
                    "p_quarterfinal": self.p_quarterfinal.get(tid, 0.0),
                    "p_r16": self.p_r16.get(tid, 0.0),
                    "p_group_exit": self.p_group_exit.get(tid, 0.0),
                    "se_champion": self.se_champion.get(tid, 0.0),
                }
            )
        return rows


class TournamentSimulator:
    def __init__(
        self,
        format_key: str,
        match_model: PoissonMatchModel | None = None,
        rng_seed: int | None = 42,
    ):
        self.config = load_tournament_config(format_key)
        self.model = match_model or PoissonMatchModel()
        self.rng = np.random.default_rng(rng_seed)
        self.rng_seed = rng_seed

    # ------------------------------------------------------------------
    # Match sampling
    # ------------------------------------------------------------------

    def play_match(
        self,
        home: TeamState,
        away: TeamState,
        *,
        knockout: bool = False,
        is_neutral: bool = True,
    ) -> tuple[int, int, str]:
        """Return (home_goals_reg, away_goals_reg, winner_id).

        For knockout draws: coin-flip winner after 'penalties' (design decision).
        Regulation goals still returned for GD bookkeeping if needed.
        """
        scores = self.model.sample_scorelines(
            1,
            home_elo=home.elo,
            away_elo=away.elo,
            home_form=home.form,
            away_form=away.form,
            is_neutral=is_neutral,
            home_confed=home.confederation,
            away_confed=away.confederation,
            rng=self.rng,
        )[0]
        hg, ag = int(scores[0]), int(scores[1])

        if hg > ag:
            return hg, ag, home.team_id
        if ag > hg:
            return hg, ag, away.team_id

        if not knockout:
            return hg, ag, "draw"

        # Penalty model: coin flip (documented)
        winner = home.team_id if self.rng.random() < 0.5 else away.team_id
        return hg, ag, winner

    # ------------------------------------------------------------------
    # Group stage
    # ------------------------------------------------------------------

    def _empty_standings(self, teams: list[TeamState]) -> dict[str, StandingsRow]:
        return {t.team_id: StandingsRow(team_id=t.team_id) for t in teams}

    def _apply_result(
        self, table: dict[str, StandingsRow], home_id: str, away_id: str, hg: int, ag: int
    ) -> None:
        th, ta = table[home_id], table[away_id]
        th.played += 1
        ta.played += 1
        th.gf += hg
        th.ga += ag
        ta.gf += ag
        ta.ga += hg
        if hg > ag:
            th.wins += 1
            ta.losses += 1
            th.points += self.config["group_stage"]["points"]["win"]
            ta.points += self.config["group_stage"]["points"]["loss"]
        elif ag > hg:
            ta.wins += 1
            th.losses += 1
            ta.points += self.config["group_stage"]["points"]["win"]
            th.points += self.config["group_stage"]["points"]["loss"]
        else:
            th.draws += 1
            ta.draws += 1
            th.points += self.config["group_stage"]["points"]["draw"]
            ta.points += self.config["group_stage"]["points"]["draw"]

    def simulate_group(self, teams: list[TeamState]) -> list[StandingsRow]:
        assert len(teams) == self.config["group_stage"]["teams_per_group"]
        table = self._empty_standings(teams)
        # Round-robin
        for i in range(len(teams)):
            for j in range(i + 1, len(teams)):
                a, b = teams[i], teams[j]
                hg, ag, _ = self.play_match(a, b, knockout=False, is_neutral=True)
                self._apply_result(table, a.team_id, b.team_id, hg, ag)
        ranked = sorted(table.values(), key=lambda r: r.sort_key(), reverse=True)
        # Attach team objects order
        return ranked

    def simulate_group_stage(
        self, groups: dict[str, list[TeamState]]
    ) -> tuple[list[TeamState], list[TeamState], dict[str, list[StandingsRow]]]:
        """Return (qualified teams in bracket order seeds, eliminated, tables)."""
        gs = self.config["group_stage"]
        qualify = gs["qualify_per_group"]
        best_thirds_n = gs.get("best_thirds_advance", 0)

        winners: list[TeamState] = []
        runners: list[TeamState] = []
        thirds: list[tuple[StandingsRow, TeamState, str]] = []
        tables: dict[str, list[StandingsRow]] = {}
        team_lookup = {
            t.team_id: t for group_teams in groups.values() for t in group_teams
        }

        for gname, teams in sorted(groups.items()):
            ranked = self.simulate_group(teams)
            tables[gname] = ranked
            winners.append(team_lookup[ranked[0].team_id])
            if qualify >= 2:
                runners.append(team_lookup[ranked[1].team_id])
            if best_thirds_n and len(ranked) >= 3:
                thirds.append((ranked[2], team_lookup[ranked[2].team_id], gname))

        qualified: list[TeamState] = []
        # Standard seeding placeholder: winners then runners then best thirds
        # Bracket wiring is format-specific; for probability aggregation we only
        # need the qualified set + a deterministic pairing rule.
        if self.config["key"] == "world_cup_32":
            # R16 pairs: 1A/2B, 1B/2A, 1C/2D, 1D/2C, ...
            order = []
            group_names = sorted(groups.keys())
            w_map = {gn: winners[i] for i, gn in enumerate(group_names)}
            r_map = {gn: runners[i] for i, gn in enumerate(group_names)}
            # Classic WC R16 pairing pattern (1A/2B, 1C/2D, ...)
            classic = [
                (w_map["A"], r_map["B"]),
                (w_map["C"], r_map["D"]),
                (w_map["E"], r_map["F"]),
                (w_map["G"], r_map["H"]),
                (w_map["B"], r_map["A"]),
                (w_map["D"], r_map["C"]),
                (w_map["F"], r_map["E"]),
                (w_map["H"], r_map["G"]),
            ]
            for home, away in classic:
                order.extend([home, away])
            qualified = order
        else:
            # Euros 24: top 2 + 4 best thirds
            thirds_sorted = sorted(thirds, key=lambda x: x[0].sort_key(), reverse=True)
            best_thirds = [t[1] for t in thirds_sorted[:best_thirds_n]]
            qualified = winners + runners + best_thirds

        qualified_ids = {t.team_id for t in qualified}
        eliminated = [
            t
            for group_teams in groups.values()
            for t in group_teams
            if t.team_id not in qualified_ids
        ]
        return qualified, eliminated, tables

    # ------------------------------------------------------------------
    # Knockout
    # ------------------------------------------------------------------

    def simulate_knockout(
        self, seeded: list[TeamState]
    ) -> dict[str, set[str]]:
        """Return sets of team_ids reaching each stage, plus champion singleton."""
        stages = self.config["knockout"]["stages"]
        reached: dict[str, set[str]] = {s: set() for s in stages}
        reached["champion"] = set()

        # First knockout stage includes all seeded teams
        current = list(seeded)
        stage_names = stages
        # Infer starting stage by bracket size
        n = len(current)
        if n == 16:
            stage_idx = stage_names.index("round_of_16")
        elif n == 8:
            stage_idx = stage_names.index("quarterfinal")
        elif n == 4:
            stage_idx = stage_names.index("semifinal")
        elif n == 2:
            stage_idx = stage_names.index("final")
        else:
            # Pad / trim not supported — caller must seed correctly
            raise ValueError(f"Unsupported bracket size: {n}")

        for si in range(stage_idx, len(stage_names)):
            stage = stage_names[si]
            for t in current:
                reached[stage].add(t.team_id)
            nxt: list[TeamState] = []
            for i in range(0, len(current), 2):
                home, away = current[i], current[i + 1]
                _, _, winner_id = self.play_match(home, away, knockout=True, is_neutral=True)
                nxt.append(home if winner_id == home.team_id else away)
            current = nxt

        if len(current) != 1:
            raise RuntimeError("Knockout did not produce a single champion")
        reached["champion"].add(current[0].team_id)
        return reached

    # ------------------------------------------------------------------
    # Full tournament Monte Carlo
    # ------------------------------------------------------------------

    def run(
        self,
        groups: dict[str, list[TeamState]],
        n_sims: int = 10_000,
    ) -> SimulationAggregate:
        all_teams = [t for g in groups.values() for t in g]
        team_ids = [t.team_id for t in all_teams]

        counts = {
            "champion": defaultdict(int),
            "final": defaultdict(int),
            "semifinal": defaultdict(int),
            "quarterfinal": defaultdict(int),
            "r16": defaultdict(int),
            "group_exit": defaultdict(int),
        }

        for _ in range(n_sims):
            qualified, eliminated, _ = self.simulate_group_stage(groups)
            for t in eliminated:
                counts["group_exit"][t.team_id] += 1
            for t in qualified:
                # Reached at least R16 / first KO stage
                counts["r16"][t.team_id] += 1

            reached = self.simulate_knockout(qualified)
            for tid in reached.get("round_of_16", set()):
                counts["r16"][tid] += 0  # already counted
            for tid in reached.get("quarterfinal", set()):
                counts["quarterfinal"][tid] += 1
            for tid in reached.get("semifinal", set()):
                counts["semifinal"][tid] += 1
            for tid in reached.get("final", set()):
                counts["final"][tid] += 1
            for tid in reached["champion"]:
                counts["champion"][tid] += 1

        def probs(counter: dict[str, int]) -> dict[str, float]:
            return {tid: counter.get(tid, 0) / n_sims for tid in team_ids}

        p_champ = probs(counts["champion"])
        # Bernoulli SE: sqrt(p(1-p)/N) — core Monte Carlo error scaling
        se = {
            tid: float(np.sqrt(p * (1.0 - p) / n_sims)) for tid, p in p_champ.items()
        }

        return SimulationAggregate(
            n_sims=n_sims,
            team_ids=team_ids,
            p_champion=p_champ,
            p_final=probs(counts["final"]),
            p_semifinal=probs(counts["semifinal"]),
            p_quarterfinal=probs(counts["quarterfinal"]),
            p_r16=probs(counts["r16"]),
            p_group_exit=probs(counts["group_exit"]),
            se_champion=se,
        )


def build_demo_world_cup_groups() -> dict[str, list[TeamState]]:
    """Illustrative Elo-seeded 32-team field for smoke tests / demos."""
    field = {
        "A": [("QAT", 1450, "AFC"), ("ECU", 1700, "CONMEBOL"), ("SEN", 1720, "CAF"), ("NED", 1920, "UEFA")],
        "B": [("ENG", 2000, "UEFA"), ("IRN", 1620, "AFC"), ("USA", 1750, "CONCACAF"), ("WAL", 1680, "UEFA")],
        "C": [("ARG", 2080, "CONMEBOL"), ("KSA", 1500, "AFC"), ("MEX", 1700, "CONCACAF"), ("POL", 1720, "UEFA")],
        "D": [("FRA", 2050, "UEFA"), ("AUS", 1600, "AFC"), ("DEN", 1800, "UEFA"), ("TUN", 1580, "CAF")],
        "E": [("ESP", 1980, "UEFA"), ("CRC", 1480, "CONCACAF"), ("GER", 1960, "UEFA"), ("JPN", 1740, "AFC")],
        "F": [("BEL", 1900, "UEFA"), ("CAN", 1580, "CONCACAF"), ("MAR", 1760, "CAF"), ("CRO", 1820, "UEFA")],
        "G": [("BRA", 2100, "CONMEBOL"), ("SRB", 1700, "UEFA"), ("SUI", 1780, "UEFA"), ("CMR", 1600, "CAF")],
        "H": [("POR", 1940, "UEFA"), ("GHA", 1620, "CAF"), ("URU", 1800, "CONMEBOL"), ("KOR", 1660, "AFC")],
    }
    groups: dict[str, list[TeamState]] = {}
    for g, rows in field.items():
        groups[g] = [
            TeamState(team_id=code, elo=elo, confederation=conf, group=g)
            for code, elo, conf in rows
        ]
    return groups
