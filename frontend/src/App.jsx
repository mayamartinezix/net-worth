import { useEffect, useState, useTransition } from "react";

const API = "/api/v1";

export default function App() {
  const [health, setHealth] = useState(null);
  const [match, setMatch] = useState(null);
  const [odds, setOdds] = useState(null);
  const [error, setError] = useState(null);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    fetch(`${API}/health`)
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth({ status: "offline" }));
  }, []);

  function runMatchPredict() {
    setError(null);
    startTransition(async () => {
      try {
        const r = await fetch(`${API}/predict/match`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            home_team: "BRA",
            away_team: "GHA",
            home_elo: 2100,
            away_elo: 1620,
            is_neutral: true,
          }),
        });
        if (!r.ok) throw new Error(await r.text());
        setMatch(await r.json());
      } catch (e) {
        setError(String(e.message || e));
      }
    });
  }

  function runDemoSim() {
    setError(null);
    startTransition(async () => {
      try {
        const r = await fetch(`${API}/simulate/demo?n_sims=300&seed=42`);
        if (!r.ok) throw new Error(await r.text());
        setOdds(await r.json());
      } catch (e) {
        setError(String(e.message || e));
      }
    });
  }

  const topOdds = odds?.teams?.slice(0, 8) ?? [];

  return (
    <div className="page">
      <header className="hero">
        <div className="hero-bg" aria-hidden="true" />
        <div className="hero-content">
          <p className="brand">PitchPath</p>
          <h1>Tournament odds from Monte Carlo paths</h1>
          <p className="lede">
            Elo → Poisson scorelines → config-driven World Cup &amp; Euros simulation.
            Built as a risk-modeling portfolio piece, not a betting tip sheet.
          </p>
          <div className="cta-row">
            <button type="button" onClick={runMatchPredict} disabled={pending}>
              Predict BRA vs GHA
            </button>
            <button type="button" className="ghost" onClick={runDemoSim} disabled={pending}>
              Run demo tournament (N=300)
            </button>
          </div>
          <p className="status">
            API: {health?.status ?? "…"}
            {pending ? " · running…" : ""}
          </p>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      <section className="section" aria-labelledby="match-heading">
        <h2 id="match-heading">Match prediction</h2>
        <p className="section-lede">Win / draw / loss from the independent Poisson goal model.</p>
        {match ? (
          <div className="prob-row">
            <Prob label={`${match.home_team} win`} value={match.p_home} />
            <Prob label="Draw" value={match.p_draw} />
            <Prob label={`${match.away_team} win`} value={match.p_away} />
            <p className="meta">
              λ<sub>home</sub>={match.lambda_home.toFixed(2)} · λ<sub>away</sub>=
              {match.lambda_away.toFixed(2)}
            </p>
          </div>
        ) : (
          <p className="placeholder">Run a matchup to see probabilities.</p>
        )}
      </section>

      <section className="section" aria-labelledby="odds-heading">
        <h2 id="odds-heading">Title odds (demo field)</h2>
        <p className="section-lede">
          Cached-style demo at small N for interactivity. Production odds are batch-simulated.
        </p>
        {topOdds.length ? (
          <ol className="odds-list">
            {topOdds.map((t) => (
              <li key={t.team_id}>
                <span className="code">{t.team_id}</span>
                <span className="bar-wrap">
                  <span className="bar" style={{ width: `${t.p_champion * 100}%` }} />
                </span>
                <span className="pct">{(t.p_champion * 100).toFixed(1)}%</span>
              </li>
            ))}
          </ol>
        ) : (
          <p className="placeholder">Run the demo tournament simulation.</p>
        )}
      </section>

      <footer className="footer">
        <a href="/docs" target="_blank" rel="noreferrer">
          API docs
        </a>
        <span>·</span>
        <a href="https://github.com/mayamartinezix/net-worth/blob/cursor/soccer-tournament-prediction-b74c/docs/MODEL_VALIDATION.md">
          Model validation memo
        </a>
        <span>·</span>
        <span>SE ∝ 1/√N</span>
      </footer>
    </div>
  );
}

function Prob({ label, value }) {
  return (
    <div className="prob">
      <span className="prob-label">{label}</span>
      <span className="prob-value">{(value * 100).toFixed(1)}%</span>
    </div>
  );
}
