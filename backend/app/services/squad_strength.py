"""Squad-level strength from club performances of national-team players.

Idea
----
National-team Elo summarizes international results. Adding how well a squad's
players perform *at their clubs* captures form/talent that hasn't fully shown
up in internationals yet — analogous to using granular factor exposures that
are not spanned by the first principal component.

Data used (2025/26 season / WC 2026 squads)
-------------------------------------------
- risingtransfers per-90 club league stats (goals, assists, shots, key passes, …)
- squad market values (risingtransfers + mominullptr)
- ClubElo ratings of each player's club (api.clubelo.com)
- openfootball / mominullptr squad rosters for club membership

Primary output is a team-level composite ``squad_index`` (mean 0 within the
tournament field), fed into the Poisson λ layer as a small additive feature.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
RAW_PLAYERS = ROOT / "data" / "raw" / "players"
PROCESSED = ROOT / "data" / "processed" / "players"

COUNTRY_ALIASES = {
    "Cape Verde Islands": "Cape Verde",
    "Congo DR": "DR Congo",
    "Côte d'Ivoire": "Ivory Coast",
    "Cote d'Ivoire": "Ivory Coast",
    "Curacao": "Curaçao",
    "South Korea": "South Korea",
    "Korea Republic": "South Korea",
    "Türkiye": "Turkey",
    "Turkey": "Turkey",
    "USA": "United States",
    "United States of America": "United States",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
}


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def _norm_club(name: str) -> str:
    s = _strip_accents(str(name)).lower()
    s = re.sub(r"\b(fc|cf|sc|ac|afc|fk|sk|cd|rc|ssc|as|us|calcio|club)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _norm_country(name: str) -> str:
    name = str(name).strip()
    return COUNTRY_ALIASES.get(name, name)


def _clubelo_lookup(clubelo: pd.DataFrame) -> dict[str, float]:
    """Map normalized club name → Elo (prefer top-level clubs)."""
    out: dict[str, float] = {}
    for row in clubelo.itertuples(index=False):
        key = _norm_club(row.Club)
        elo = float(row.Elo)
        # keep max elo if duplicates
        out[key] = max(out.get(key, 0.0), elo)
    return out


def _match_club_elo(club_name: str, lookup: dict[str, float]) -> float | None:
    key = _norm_club(club_name)
    if not key:
        return None
    if key in lookup:
        return lookup[key]
    # substring fallback (e.g. "psv eindhoven" ↔ "psv")
    parts = key.split()
    candidates = []
    for k, elo in lookup.items():
        if key in k or k in key:
            candidates.append((abs(len(k) - len(key)), elo))
        elif parts and parts[0] == k.split()[0] and len(parts[0]) > 3:
            candidates.append((5 + abs(len(k) - len(key)), elo))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][1]


def build_squad_strength_table() -> pd.DataFrame:
    """Aggregate player club stats → national-team squad strength features."""
    squads = pd.read_csv(RAW_PLAYERS / "rt_squads.csv")
    per90 = pd.read_csv(RAW_PLAYERS / "rt_per90.csv")
    clubelo = pd.read_csv(RAW_PLAYERS / "clubelo_latest.csv")
    value_src = pd.read_csv(RAW_PLAYERS / "wc2026_squads_players.csv")
    teams = pd.read_csv(RAW_PLAYERS / "wc2026_teams.csv")

    squads = squads.copy()
    squads["country"] = squads["country"].map(_norm_country)
    per90 = per90.copy()

    elo_lookup = _clubelo_lookup(clubelo)
    squads["club_elo"] = squads["club"].map(lambda c: _match_club_elo(c, elo_lookup))

    # Attack contribution from club league per-90 (outfield-ish)
    p90 = per90[
        [
            "player_id",
            "minutes",
            "goals_per90",
            "assists_per90",
            "shots_per90",
            "key_passes_per90",
            "rating",
        ]
    ].copy()
    p90["attack_per90"] = (
        p90["goals_per90"].fillna(0)
        + p90["assists_per90"].fillna(0)
        + 0.15 * p90["shots_per90"].fillna(0)
        + 0.20 * p90["key_passes_per90"].fillna(0)
    )
    # Weight by minutes (capped)
    p90["w"] = np.clip(p90["minutes"].fillna(0) / 900.0, 0.25, 1.5)

    merged = squads.merge(p90[["player_id", "attack_per90", "w", "minutes"]], on="player_id", how="left")
    merged["attack_per90"] = merged["attack_per90"].fillna(0.0)
    merged["w"] = merged["w"].fillna(0.35)

    # Market values from mominullptr via team name
    id_to_name = dict(zip(teams["team_id"], teams["team_name"].map(_norm_country)))
    value_src = value_src.copy()
    value_src["country"] = value_src["team_id"].map(id_to_name)
    value_by_team = (
        value_src.groupby("country")["market_value_eur"]
        .agg(squad_market_value_eur="sum", squad_avg_value_eur="mean", n_valued="count")
        .reset_index()
    )

    def wavg(g: pd.DataFrame, col: str) -> float:
        ww = g["w"].to_numpy()
        xx = g[col].to_numpy(dtype=float)
        if ww.sum() <= 0:
            return float(np.nanmean(xx)) if len(xx) else 0.0
        return float(np.average(xx, weights=ww))

    rows = []
    for country, g in merged.groupby("country"):
        club_elos = g["club_elo"].dropna()
        rows.append(
            {
                "team": country,
                "n_players": int(len(g)),
                "n_with_club_elo": int(club_elos.shape[0]),
                "avg_club_elo": float(club_elos.mean()) if len(club_elos) else np.nan,
                "median_club_elo": float(club_elos.median()) if len(club_elos) else np.nan,
                "avg_attack_per90": wavg(g, "attack_per90"),
                "rt_value_estimate_eur": float(g["rt_value_estimate_eur"].fillna(0).sum()),
            }
        )
    out = pd.DataFrame(rows)
    out = out.merge(value_by_team, left_on="team", right_on="country", how="left")
    out = out.drop(columns=["country"], errors="ignore")

    # Composite index — standardized within available field
    def z(series: pd.Series) -> pd.Series:
        s = series.astype(float)
        mu, sd = s.mean(), s.std(ddof=0)
        if sd is None or sd < 1e-9 or np.isnan(sd):
            return pd.Series(np.zeros(len(s)), index=s.index)
        return (s - mu) / sd

    out["z_club_elo"] = z(out["avg_club_elo"].fillna(out["avg_club_elo"].median()))
    out["z_attack"] = z(out["avg_attack_per90"].fillna(0))
    out["z_value"] = z(np.log1p(out["squad_avg_value_eur"].fillna(out["rt_value_estimate_eur"] / np.maximum(out["n_players"], 1))))
    # Weight: club level + individual attack + market value
    out["squad_index"] = (
        0.45 * out["z_club_elo"] + 0.35 * out["z_attack"] + 0.20 * out["z_value"]
    )
    out = out.sort_values("squad_index", ascending=False).reset_index(drop=True)
    return out


def write_squad_strength(path: Path | None = None) -> Path:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    path = path or (PROCESSED / "squad_strength_wc2026.csv")
    table = build_squad_strength_table()
    table.to_csv(path, index=False)
    return path


_SQUAD_CACHE: dict[str, float] | None = None


def load_squad_index_map() -> dict[str, float]:
    global _SQUAD_CACHE
    if _SQUAD_CACHE is not None:
        return _SQUAD_CACHE
    path = PROCESSED / "squad_strength_wc2026.csv"
    if not path.exists():
        try:
            write_squad_strength(path)
        except FileNotFoundError:
            _SQUAD_CACHE = {}
            return _SQUAD_CACHE
    df = pd.read_csv(path)
    _SQUAD_CACHE = {str(r.team): float(r.squad_index) for r in df.itertuples(index=False)}
    return _SQUAD_CACHE


def squad_index_for(team: str) -> float:
    return float(load_squad_index_map().get(team, 0.0))
