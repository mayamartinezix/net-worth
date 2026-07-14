import { useEffect, useRef, useState } from "react";

const API = "/api/v1";

const COMPETITIONS = [
  { id: "world_cup_2026", label: "World Cup 2026" },
  { id: "euros_2024", label: "Euro 2024" },
];

export default function App() {
  const [health, setHealth] = useState(null);
  const [competition, setCompetition] = useState("world_cup_2026");
  const [odds, setOdds] = useState(null);
  const [finalFour, setFinalFour] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [ffLoading, setFfLoading] = useState(false);
  const reqId = useRef(0);

  useEffect(() => {
    fetch(`${API}/health`)
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth({ status: "offline" }));
  }, []);

  useEffect(() => {
    runSim(competition);
  }, [competition]);

  useEffect(() => {
    if (competition === "world_cup_2026") {
      loadFinalFour();
    } else {
      setFinalFour(null);
    }
  }, [competition]);

  async function runSim(comp) {
    const id = ++reqId.current;
    setError(null);
    setLoading(true);
    try {
      const r = await fetch(
        `${API}/simulate/demo?competition=${encodeURIComponent(comp)}&n_sims=200&seed=42`
      );
      if (!r.ok) throw new Error(await r.text());
      const body = await r.json();
      if (id === reqId.current) setOdds(body);
    } catch (e) {
      if (id === reqId.current) setError(String(e.message || e));
    } finally {
      if (id === reqId.current) setLoading(false);
    }
  }

  async function loadFinalFour() {
    setFfLoading(true);
    try {
      const r = await fetch(`${API}/final-four/world_cup_2026?n_sims=4000&seed=7`);
      if (!r.ok) throw new Error(await r.text());
      setFinalFour(await r.json());
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setFfLoading(false);
    }
  }

  const teams = odds?.teams ?? [];
  const showR32 = competition === "world_cup_2026";
  const showOdds = odds?.competition === competition;

  return (
    <div className="page">
      <header className="top">
        <div className="top-inner">
          <p className="brand">PitchPath</p>
          <h1>Tournament odds, simply.</h1>
          <p className="lede">
            Monte Carlo paths for World Cup and Euros — round-reached and title probabilities.
          </p>

          <div className="seg" role="tablist" aria-label="Competition">
            {COMPETITIONS.map((c) => (
              <button
                key={c.id}
                type="button"
                role="tab"
                aria-selected={competition === c.id}
                className={competition === c.id ? "seg-btn active" : "seg-btn"}
                onClick={() => setCompetition(c.id)}
                disabled={loading}
              >
                {c.label}
              </button>
            ))}
          </div>

          <p className="status">
            {showOdds ? odds.label : "Loading"} · N={showOdds ? odds.n_sims : "…"} · API{" "}
            {health?.status ?? "…"}
            {loading ? " · simulating…" : ""}
          </p>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      {competition === "world_cup_2026" && (
        <section className="section" aria-labelledby="ff-heading">
          <div className="section-head">
            <h2 id="ff-heading">Final Four comparison</h2>
            <button type="button" className="text-btn" onClick={loadFinalFour} disabled={ffLoading}>
              Refresh
            </button>
          </div>
          <p className="section-note">
            Conditional on France, Spain, England, and Argentina reaching the semis. Only the
            remaining path (2 semis + final) is simulated.
          </p>

          {ffLoading && !finalFour ? (
            <p className="placeholder">Comparing final four…</p>
          ) : finalFour ? (
            <>
              <div className="semi-grid">
                {finalFour.semifinals.map((s) => (
                  <article key={`${s.home}-${s.away}`} className="semi-card">
                    <p className="semi-date">{s.date}</p>
                    <h3>
                      {s.home} <span className="vs">vs</span> {s.away}
                    </h3>
                    <div className="advance">
                      <div>
                        <span className="adv-label">{s.home} advance</span>
                        <strong>{pct(s.p_home_advance)}</strong>
                      </div>
                      <div>
                        <span className="adv-label">{s.away} advance</span>
                        <strong>{pct(s.p_away_advance)}</strong>
                      </div>
                    </div>
                    <p className="meta">
                      Elo {Math.round(s.home_elo)}–{Math.round(s.away_elo)} · λ{" "}
                      {s.lambda_home.toFixed(2)} / {s.lambda_away.toFixed(2)} · reg. draw{" "}
                      {pct(s.p_draw_regulation)}
                    </p>
                  </article>
                ))}
              </div>

              <div className="table-wrap tight">
                <table>
                  <thead>
                    <tr>
                      <th>Team</th>
                      <th>Elo</th>
                      <th>P(Final)</th>
                      <th>P(Champion)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {finalFour.teams.map((t) => (
                      <tr key={t.team_id}>
                        <td className="team">{t.team_id}</td>
                        <td>{Math.round(t.elo)}</td>
                        <td>{pct(t.p_final)}</td>
                        <td className="win">
                          <span
                            className="win-bar"
                            style={{ width: `${Math.max(t.p_champion * 100, 2)}%` }}
                          />
                          <span>
                            {pct(t.p_champion)} ±{(t.se_champion * 100).toFixed(1)}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="placeholder">Final four unavailable.</p>
          )}
        </section>
      )}

      <section className="section" aria-labelledby="odds-heading">
        <div className="section-head">
          <h2 id="odds-heading">Full-field round likelihoods</h2>
          <button
            type="button"
            className="text-btn"
            onClick={() => runSim(competition)}
            disabled={loading}
          >
            Re-run
          </button>
        </div>
        <p className="section-note">
          Probabilities are cumulative “reach this round or further.” Full group stage is
          re-simulated from kickoff (not conditioned on completed matches).
        </p>

        {showOdds && teams.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Team</th>
                  {showR32 && <th>R32</th>}
                  <th>R16</th>
                  <th>QF</th>
                  <th>SF</th>
                  <th>Final</th>
                  <th>Win</th>
                </tr>
              </thead>
              <tbody>
                {teams.map((t) => (
                  <tr key={t.team_id}>
                    <td className="team">{t.team_id}</td>
                    {showR32 && <td>{pct(t.p_r32)}</td>}
                    <td>{pct(t.p_r16)}</td>
                    <td>{pct(t.p_quarterfinal)}</td>
                    <td>{pct(t.p_semifinal)}</td>
                    <td>{pct(t.p_final)}</td>
                    <td className="win">
                      <span
                        className="win-bar"
                        style={{ width: `${Math.max(t.p_champion * 100, 1.5)}%` }}
                      />
                      <span>{pct(t.p_champion)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="placeholder">{loading ? "Simulating…" : "No results yet."}</p>
        )}
      </section>

      <footer className="footer">
        <a href="/docs" target="_blank" rel="noreferrer">
          API
        </a>
        <span>·</span>
        <a href="https://github.com/mayamartinezix/net-worth/blob/main/docs/MODEL_VALIDATION.md">
          Validation memo
        </a>
      </footer>
    </div>
  );
}

function pct(v) {
  return `${((v || 0) * 100).toFixed(1)}%`;
}
