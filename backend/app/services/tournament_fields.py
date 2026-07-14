"""Tournament fields used by the interactive demo API.

World Cup 2026 groups come from the official draw (playoff winners filled from
actual 2026 results). Elo ratings are fit on internationals before kickoff when
the processed match history is available; otherwise static priors are used.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.services.elo import EloEngine
from app.services.simulator import TeamState

ROOT = Path(__file__).resolve().parents[3]
MATCHES_PATH = ROOT / "data" / "processed" / "matches_2010_plus.csv"

# Approximate confederation map for demo teams
CONFED = {
    "Mexico": "CONCACAF",
    "South Africa": "CAF",
    "South Korea": "AFC",
    "Czech Republic": "UEFA",
    "Canada": "CONCACAF",
    "Switzerland": "UEFA",
    "Qatar": "AFC",
    "Bosnia and Herzegovina": "UEFA",
    "Brazil": "CONMEBOL",
    "Morocco": "CAF",
    "Scotland": "UEFA",
    "Haiti": "CONCACAF",
    "United States": "CONCACAF",
    "Paraguay": "CONMEBOL",
    "Australia": "AFC",
    "Turkey": "UEFA",
    "Germany": "UEFA",
    "Ivory Coast": "CAF",
    "Ecuador": "CONMEBOL",
    "Curaçao": "CONCACAF",
    "Netherlands": "UEFA",
    "Japan": "AFC",
    "Tunisia": "CAF",
    "Sweden": "UEFA",
    "Belgium": "UEFA",
    "Egypt": "CAF",
    "Iran": "AFC",
    "New Zealand": "OFC",
    "Spain": "UEFA",
    "Saudi Arabia": "AFC",
    "Uruguay": "CONMEBOL",
    "Cape Verde": "CAF",
    "France": "UEFA",
    "Senegal": "CAF",
    "Norway": "UEFA",
    "Iraq": "AFC",
    "Argentina": "CONMEBOL",
    "Algeria": "CAF",
    "Austria": "UEFA",
    "Jordan": "AFC",
    "Portugal": "UEFA",
    "Uzbekistan": "AFC",
    "Colombia": "CONMEBOL",
    "DR Congo": "CAF",
    "England": "UEFA",
    "Croatia": "UEFA",
    "Ghana": "CAF",
    "Panama": "CONCACAF",
    # Euro 2024
    "Germany": "UEFA",
    "Scotland": "UEFA",
    "Hungary": "UEFA",
    "Switzerland": "UEFA",
    "Spain": "UEFA",
    "Croatia": "UEFA",
    "Italy": "UEFA",
    "Albania": "UEFA",
    "Slovenia": "UEFA",
    "Denmark": "UEFA",
    "Serbia": "UEFA",
    "England": "UEFA",
    "Poland": "UEFA",
    "Netherlands": "UEFA",
    "Austria": "UEFA",
    "France": "UEFA",
    "Belgium": "UEFA",
    "Slovakia": "UEFA",
    "Romania": "UEFA",
    "Ukraine": "UEFA",
    "Turkey": "UEFA",
    "Georgia": "UEFA",
    "Portugal": "UEFA",
    "Czech Republic": "UEFA",
}

# Official WC 2026 groups (martj42 naming)
WC2026_GROUPS: dict[str, list[str]] = {
    "A": ["Mexico", "South Africa", "South Korea", "Czech Republic"],
    "B": ["Canada", "Switzerland", "Qatar", "Bosnia and Herzegovina"],
    "C": ["Brazil", "Morocco", "Scotland", "Haiti"],
    "D": ["United States", "Paraguay", "Australia", "Turkey"],
    "E": ["Germany", "Ivory Coast", "Ecuador", "Curaçao"],
    "F": ["Netherlands", "Japan", "Tunisia", "Sweden"],
    "G": ["Belgium", "Egypt", "Iran", "New Zealand"],
    "H": ["Spain", "Saudi Arabia", "Uruguay", "Cape Verde"],
    "I": ["France", "Senegal", "Norway", "Iraq"],
    "J": ["Argentina", "Algeria", "Austria", "Jordan"],
    "K": ["Portugal", "Uzbekistan", "Colombia", "DR Congo"],
    "L": ["England", "Croatia", "Ghana", "Panama"],
}

# UEFA Euro 2024 groups
EURO2024_GROUPS: dict[str, list[str]] = {
    "A": ["Germany", "Scotland", "Hungary", "Switzerland"],
    "B": ["Spain", "Croatia", "Italy", "Albania"],
    "C": ["Slovenia", "Denmark", "Serbia", "England"],
    "D": ["Poland", "Netherlands", "Austria", "France"],
    "E": ["Belgium", "Slovakia", "Romania", "Ukraine"],
    "F": ["Turkey", "Georgia", "Portugal", "Czech Republic"],
}

# Static prior Elos when history fit is unavailable
PRIOR_ELO = {
    "Argentina": 2080,
    "France": 2050,
    "Brazil": 2030,
    "Spain": 2020,
    "England": 2000,
    "Portugal": 1980,
    "Netherlands": 1960,
    "Germany": 1950,
    "Belgium": 1920,
    "Uruguay": 1860,
    "Croatia": 1840,
    "Colombia": 1820,
    "Morocco": 1800,
    "United States": 1780,
    "Mexico": 1760,
    "Japan": 1750,
    "Senegal": 1740,
    "Switzerland": 1730,
    "Denmark": 1720,
    "Austria": 1700,
    "Italy": 1690,
    "Turkey": 1680,
    "Canada": 1660,
    "Iran": 1640,
    "South Korea": 1630,
    "Australia": 1620,
    "Ecuador": 1610,
    "Paraguay": 1600,
    "Norway": 1590,
    "Sweden": 1580,
    "Egypt": 1570,
    "Algeria": 1560,
    "Tunisia": 1550,
    "Ivory Coast": 1540,
    "Ghana": 1530,
    "Scotland": 1520,
    "Czech Republic": 1510,
    "Hungary": 1500,
    "Poland": 1495,
    "Serbia": 1490,
    "Ukraine": 1485,
    "Romania": 1480,
    "Slovakia": 1475,
    "Slovenia": 1470,
    "Georgia": 1465,
    "Albania": 1460,
    "Qatar": 1450,
    "Saudi Arabia": 1440,
    "Uzbekistan": 1430,
    "Jordan": 1420,
    "Iraq": 1410,
    "South Africa": 1400,
    "Cape Verde": 1390,
    "Panama": 1380,
    "Haiti": 1360,
    "New Zealand": 1350,
    "Curaçao": 1340,
    "DR Congo": 1455,
    "Bosnia and Herzegovina": 1505,
}


_ELO_CACHE: dict[str, dict[str, float]] = {}


def _load_elo_map(as_of: str) -> dict[str, float]:
    if as_of in _ELO_CACHE:
        return _ELO_CACHE[as_of]
    if not MATCHES_PATH.exists():
        _ELO_CACHE[as_of] = dict(PRIOR_ELO)
        return _ELO_CACHE[as_of]
    df = pd.read_csv(MATCHES_PATH)
    df = df[df["match_date"] < as_of]
    if df.empty:
        _ELO_CACHE[as_of] = dict(PRIOR_ELO)
        return _ELO_CACHE[as_of]
    engine = EloEngine()
    engine.fit(df)
    ratings = dict(PRIOR_ELO)
    ratings.update(engine.state.ratings)
    _ELO_CACHE[as_of] = ratings
    return ratings


def _groups_to_team_states(
    groups: dict[str, list[str]], elo_map: dict[str, float]
) -> dict[str, list[TeamState]]:
    out: dict[str, list[TeamState]] = {}
    for gname, teams in groups.items():
        out[gname] = [
            TeamState(
                team_id=name,
                elo=float(elo_map.get(name, PRIOR_ELO.get(name, 1500.0))),
                confederation=CONFED.get(name),
                group=gname,
            )
            for name in teams
        ]
    return out


def build_wc2026_groups() -> dict[str, list[TeamState]]:
    elo = _load_elo_map("2026-06-11")
    return _groups_to_team_states(WC2026_GROUPS, elo)


def build_euro2024_groups() -> dict[str, list[TeamState]]:
    elo = _load_elo_map("2024-06-14")
    return _groups_to_team_states(EURO2024_GROUPS, elo)
