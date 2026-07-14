from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


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


def test_simulate_demo_small():
    r = client.get("/api/v1/simulate/demo", params={"n_sims": 50, "seed": 1})
    assert r.status_code == 200
    body = r.json()
    assert body["n_sims"] == 50
    assert len(body["teams"]) == 32
    assert abs(sum(t["p_champion"] for t in body["teams"]) - 1.0) < 1e-6
