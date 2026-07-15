from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_competitions():
    r = client.get("/api/v1/competitions")
    assert r.status_code == 200
    ids = {c["id"] for c in r.json()["competitions"]}
    assert "world_cup_2026" in ids
    assert "euros_2024" in ids


def test_predict_match():
    r = client.post(
        "/api/v1/predict/match",
        json={
            "home_team": "BRA",
            "away_team": "GHA",
            "home_elo": 2100,
            "away_elo": 1600,
            "is_neutral": True,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["p_home"] > body["p_away"]
    assert abs(body["p_home"] + body["p_draw"] + body["p_away"] - 1.0) < 1e-6


def test_simulate_demo_euros():
    r = client.get(
        "/api/v1/simulate/demo",
        params={"competition": "euros_2024", "n_sims": 40, "seed": 1},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["competition"] == "euros_2024"
    assert len(body["teams"]) == 24
    assert abs(sum(t["p_champion"] for t in body["teams"]) - 1.0) < 1e-6
    assert "p_semifinal" in body["teams"][0]
    assert "p_quarterfinal" in body["teams"][0]
    assert "p_final" in body["teams"][0]


def test_simulate_demo_wc2026():
    r = client.get(
        "/api/v1/simulate/demo",
        params={"competition": "world_cup_2026", "n_sims": 30, "seed": 2},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["format_key"] == "world_cup_48"
    assert len(body["teams"]) == 48
    assert abs(sum(t["p_champion"] for t in body["teams"]) - 1.0) < 1e-6
    assert max(t["p_r32"] for t in body["teams"]) > 0.2


def test_final_four_wc2026():
    r = client.get("/api/v1/final-four/world_cup_2026", params={"n_sims": 500, "seed": 3})
    assert r.status_code == 200
    body = r.json()
    assert len(body["teams"]) == 4
    assert len(body["semifinals"]) == 2
    names = {t["team_id"] for t in body["teams"]}
    assert names == {"France", "Spain", "England", "Argentina"}
    assert abs(sum(t["p_champion"] for t in body["teams"]) - 1.0) < 1e-6
    # Each SF winner is in the final → sum of p_final ≈ 2
    assert abs(sum(t["p_final"] for t in body["teams"]) - 2.0) < 1e-6
    for s in body["semifinals"]:
        assert abs(s["p_home_advance"] + s["p_away_advance"] - 1.0) < 1e-6


def test_list_field_teams():
    r = client.get("/api/v1/competitions/world_cup_2026/teams")
    assert r.status_code == 200
    body = r.json()
    assert body["competition"] == "world_cup_2026"
    assert len(body["teams"]) == 48
    assert "France" in body["teams"]


def test_team_round_odds_single():
    r = client.get(
        "/api/v1/odds/teams",
        params={"team": "France", "competition": "euros_2024", "n_sims": 80, "seed": 5},
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["teams"]) == 1
    assert body["teams"][0]["team_id"] == "France"
    assert body["joint"] is None
    t = body["teams"][0]
    assert t["p_final"] <= t["p_semifinal"] <= t["p_quarterfinal"] + 1e-9


def test_team_round_odds_pair():
    r = client.get(
        "/api/v1/odds/teams",
        params={
            "team": ["France", "Spain"],
            "competition": "world_cup_2026",
            "n_sims": 60,
            "seed": 9,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["teams"]) == 2
    assert body["joint"] is not None
    j = body["joint"]
    assert j["p_both_final"] <= j["p_both_semifinal"] <= j["p_both_quarterfinal"] + 1e-9


def test_team_round_odds_unknown():
    r = client.get(
        "/api/v1/odds/teams",
        params={"team": "Atlantis", "competition": "euros_2024", "n_sims": 50},
    )
    assert r.status_code == 400
