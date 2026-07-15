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
      <header className="hero">
        <p className="brand">PitchPath</p>
        <p className="lede">Tournament odds from Monte Carlo paths.</p>

        <nav className="tabs" role="tablist" aria-label="Competition">
          {COMPETITIONS.map((c) => (
            <button
              key={c.id}
              type="button"
              role="tab"
              aria-selected={competition === c.id}
              className={competition === c.id ? "tab on" : "tab"}
              onClick={() => setCompetition(c.id)}
              disabled={loading}
            >
              {c.label}
            </button>
          ))}
        </nav>

        <p className="status">
          {loading ? "Simulating…" : showOdds ? odds.label : "Loading"}
          {health?.status ? ` · ${health.status}` : ""}
        </p>
      </header>

      {error && <p className="error">{error}</p>}

      {competition === "world_cup_2026" && (
        <section className="block" aria-labelledby="ff-heading">
          <div className="block-head">
            <h2 id="ff-heading">Final Four</h2>
            <button type="button" className="linkish" onClick={loadFinalFour} disabled={ffLoading}>
              Refresh
            </button>
          </div>
          <p className="hint">Semis onward only — France, Spain, England, Argentina.</p>

          {ffLoading && !finalFour ? (
            <p className="empty">Loading…</p>
          ) : finalFour ? (
            <>
              <ul className="semis">
                {finalFour.semifinals.map((s) => (
                  <li key={`${s.home}-${s.away}`}>
                    <span className="semi-match">
                      {s.home} <em>vs</em> {s.away}
                    </span>
                    <span className="semi-odds">
                      {pct(s.p_home_advance)} / {pct(s.p_away_advance)}
                    </span>
                  </li>
                ))}
              </ul>

              <div className="scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Team</th>
                      <th>Final</th>
                      <th>Win</th>
                    </tr>
                  </thead>
                  <tbody>
                    {finalFour.teams.map((t) => (
                      <tr key={t.team_id}>
                        <td className="team">{t.team_id}</td>
                        <td>{pct(t.p_final)}</td>
                        <td className="win">{pct(t.p_champion)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="empty">Unavailable.</p>
          )}
        </section>
      )}

      <section className="block" aria-labelledby="odds-heading">
        <div className="block-head">
          <h2 id="odds-heading">Field</h2>
          <button
            type="button"
            className="linkish"
            onClick={() => runSim(competition)}
            disabled={loading}
          >
            Re-run
          </button>
        </div>
        <p className="hint">Chance of reaching each round or further.</p>

        {showOdds && teams.length ? (
          <div className="scroll">
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
                    <td className="win">{pct(t.p_champion)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="empty">{loading ? "Simulating…" : "No results yet."}</p>
        )}
      </section>

      <footer className="footer">
        <a href="/staging">Team odds (staging)</a>
        <span>·</span>
        <a href="/docs" target="_blank" rel="noreferrer">
          API
        </a>
        <span>·</span>
        <a href="https://github.com/mayamartinezix/net-worth/blob/main/docs/MODEL_VALIDATION.md">
          Memo
        </a>
      </footer>
    </div>
  );
}

function pct(v) {
  return `${((v || 0) * 100).toFixed(1)}%`;
}
