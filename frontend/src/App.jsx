import { useEffect, useState, useTransition } from "react";

const API = "/api/v1";

const COMPETITIONS = [
  { id: "world_cup_2026", label: "World Cup 2026" },
  { id: "euros_2024", label: "Euro 2024" },
];

export default function App() {
  const [health, setHealth] = useState(null);
  const [competition, setCompetition] = useState("world_cup_2026");
  const [odds, setOdds] = useState(null);
  const [error, setError] = useState(null);
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    fetch(`${API}/health`)
      .then((r) => r.json())
      .then(setHealth)
      .catch(() => setHealth({ status: "offline" }));
  }, []);

  useEffect(() => {
    runSim(competition);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [competition]);

  function runSim(comp) {
    setError(null);
    startTransition(async () => {
      try {
        const r = await fetch(
          `${API}/simulate/demo?competition=${encodeURIComponent(comp)}&n_sims=200&seed=42`
        );
        if (!r.ok) throw new Error(await r.text());
        setOdds(await r.json());
      } catch (e) {
        setError(String(e.message || e));
      }
    });
  }

  const teams = odds?.teams ?? [];
  const showR32 = competition === "world_cup_2026";

  return (
    <div className="page">
      <header className="top">
        <div className="top-inner">
          <p className="brand">PitchPath</p>
          <h1>Tournament odds, simply.</h1>
          <p className="lede">
            Monte Carlo paths for World Cup and Euros — champion, final, semi, and quarter probabilities.
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
                disabled={pending}
              >
                {c.label}
              </button>
            ))}
          </div>

          <p className="status">
            {odds?.label ?? "Loading"} · N={odds?.n_sims ?? "…"} · API {health?.status ?? "…"}
            {pending ? " · simulating…" : ""}
          </p>
        </div>
      </header>

      {error && <p className="error">{error}</p>}

      <section className="section" aria-labelledby="odds-heading">
        <div className="section-head">
          <h2 id="odds-heading">Round likelihoods</h2>
          <button type="button" className="text-btn" onClick={() => runSim(competition)} disabled={pending}>
            Re-run
          </button>
        </div>

        {teams.length ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Team</th>
                  {showR32 && <th>R32</th>}
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
                    <td>{pct(t.p_quarterfinal)}</td>
                    <td>{pct(t.p_semifinal)}</td>
                    <td>{pct(t.p_final)}</td>
                    <td className="win">
                      <span className="win-bar" style={{ width: `${Math.max(t.p_champion * 100, 1.5)}%` }} />
                      <span>{pct(t.p_champion)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="placeholder">{pending ? "Simulating…" : "No results yet."}</p>
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
