import { useEffect, useState } from "react";

const API = "/api/v1";

const COMPETITIONS = [
  { id: "world_cup_2026", label: "World Cup 2026" },
  { id: "euros_2024", label: "Euro 2024" },
];

export default function StagingApp() {
  const [competition, setCompetition] = useState("world_cup_2026");
  const [fieldTeams, setFieldTeams] = useState([]);
  const [teamA, setTeamA] = useState("");
  const [teamB, setTeamB] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setError(null);
    setResult(null);
    fetch(`${API}/competitions/${encodeURIComponent(competition)}/teams`)
      .then(async (r) => {
        if (!r.ok) throw new Error(await r.text());
        return r.json();
      })
      .then((body) => {
        setFieldTeams(body.teams);
        setTeamA(body.teams[0] ?? "");
        setTeamB("");
      })
      .catch((e) => setError(String(e.message || e)));
  }, [competition]);

  async function runLookup() {
    if (!teamA) return;
    setError(null);
    setLoading(true);
    try {
      const params = new URLSearchParams({
        competition,
        n_sims: "1200",
        seed: "42",
      });
      params.append("team", teamA);
      if (teamB && teamB !== teamA) {
        params.append("team", teamB);
      }
      const r = await fetch(`${API}/odds/teams?${params}`);
      if (!r.ok) throw new Error(await r.text());
      setResult(await r.json());
    } catch (e) {
      setError(String(e.message || e));
    } finally {
      setLoading(false);
    }
  }

  const secondOptions = fieldTeams.filter((t) => t !== teamA);

  return (
    <div className="page staging">
      <header className="hero">
        <p className="badge">Staging</p>
        <p className="brand">PitchPath</p>
        <p className="lede">Pick one or two teams and see quarter-, semi-, and final odds.</p>
      </header>

      <section className="block">
        <h2>Competition</h2>
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
      </section>

      <section className="block">
        <h2>Teams</h2>
        <div className="pickers">
          <label className="picker">
            <span>Team 1</span>
            <select value={teamA} onChange={(e) => setTeamA(e.target.value)} disabled={!fieldTeams.length}>
              {fieldTeams.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label className="picker">
            <span>Team 2 (optional)</span>
            <select value={teamB} onChange={(e) => setTeamB(e.target.value)}>
              <option value="">— none —</option>
              {secondOptions.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
        </div>
        <button type="button" className="primary" onClick={runLookup} disabled={loading || !teamA}>
          {loading ? "Simulating…" : "Get round odds"}
        </button>
      </section>

      {error && <p className="error">{error}</p>}

      {result && (
        <section className="block">
          <h2>Results</h2>
          <p className="hint">
            {result.label} · N={result.n_sims} · reach round or further
          </p>
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th>Team</th>
                  <th>QF</th>
                  <th>SF</th>
                  <th>Final</th>
                  <th>Win</th>
                </tr>
              </thead>
              <tbody>
                {result.teams.map((t) => (
                  <tr key={t.team_id}>
                    <td className="team">{t.team_id}</td>
                    <td>{pct(t.p_quarterfinal)}</td>
                    <td>{pct(t.p_semifinal)}</td>
                    <td>{pct(t.p_final)}</td>
                    <td className="win">{pct(t.p_champion)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {result.joint && (
            <>
              <h3 className="subhead">Both teams advance</h3>
              <ul className="joint">
                <li>
                  <span>Both reach QF</span>
                  <strong>{pct(result.joint.p_both_quarterfinal)}</strong>
                </li>
                <li>
                  <span>Both reach SF</span>
                  <strong>{pct(result.joint.p_both_semifinal)}</strong>
                </li>
                <li>
                  <span>Both reach Final</span>
                  <strong>{pct(result.joint.p_both_final)}</strong>
                </li>
              </ul>
            </>
          )}
        </section>
      )}

      <footer className="footer">
        <a href="/">Production UI</a>
        <span>·</span>
        <a href="/docs" target="_blank" rel="noreferrer">
          API
        </a>
      </footer>
    </div>
  );
}

function pct(v) {
  return `${((v || 0) * 100).toFixed(1)}%`;
}
