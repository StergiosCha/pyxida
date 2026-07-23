import { useState } from "react";
import { Link } from "react-router-dom";
import { api, EligibilityResp } from "../lib/api";
import { useAsync, ErrorBox } from "../lib/hooks";
import { fmtMoria, fmtPct } from "../lib/format";

// subjects relevant per field (mirrors backend FIELD_WEIGHTS keys)
const FIELD_SUBJECTS: Record<string, string[]> = {
  "1ο": ["NG", "ANC", "HIST", "LAT"],
  "2ο": ["NG", "MATH", "PHYS", "CHEM"],
  "3ο": ["NG", "PHYS", "CHEM", "BIO"],
  "4ο": ["NG", "MATH", "ECON", "AOTH"],
};

export default function Calculator() {
  const { data: meta } = useAsync(() => api.meta(), []);
  const subjLabel = new Map((meta?.subjects ?? []).map((s) => [s.id, s.label]));
  const [field, setField] = useState("3ο");
  const [grades, setGrades] = useState<Record<string, string>>({});
  const [result, setResult] = useState<EligibilityResp | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const subjects = FIELD_SUBJECTS[field] ?? [];

  async function calc() {
    setBusy(true); setError(null);
    try {
      const g: Record<string, number> = {};
      for (const s of subjects) if (grades[s] !== undefined && grades[s] !== "") g[s] = Number(grades[s]);
      const r = await api.eligibility({ grades: g, field_id: field, year: 2025, include_ineligible: true });
      setResult(r);
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  }

  return (
    <>
      <div className="card">
        <h2>Υπολογιστής μορίων & επιλεξιμότητας</h2>
        <p className="muted small">
          Δώστε βαθμούς (κλίμακα 0–20) στα μαθήματα του πεδίου. Υπολογίζουμε τα μόρια και εφαρμόζουμε την
          <strong> ΕΒΕ ως αυστηρό κατώφλι</strong>: αν ο μέσος όρος πεδίου δεν καλύπτει την ΕΒΕ ενός τμήματος,
          το τμήμα αποκλείεται — ανεξαρτήτως μορίων.
        </p>
        <div className="field" style={{ maxWidth: 360 }}>
          <label>Επιστημονικό πεδίο</label>
          <select value={field} onChange={(e) => { setField(e.target.value); setResult(null); }}>
            {(meta?.fields ?? []).map((f) => <option key={f.id} value={f.id}>{f.label}</option>)}
          </select>
        </div>
        <div className="grid cols-4">
          {subjects.map((s) => (
            <div className="field" key={s}>
              <label>{subjLabel.get(s) ?? s}</label>
              <input type="number" min={0} max={20} step={0.1} value={grades[s] ?? ""}
                onChange={(e) => setGrades((g) => ({ ...g, [s]: e.target.value }))} />
            </div>
          ))}
        </div>
        <button className="btn" disabled={busy} onClick={calc}>{busy ? "Υπολογισμός…" : "Υπολογισμός επιλεξιμότητας"}</button>
      </div>

      {error && <ErrorBox error={error} />}

      {result && (
        <>
          <div className="grid cols-4">
            <div className="card stat"><div className="num">{fmtMoria(result.profile.moria)}</div><div className="lbl">μόρια</div></div>
            <div className="card stat"><div className="num">{result.profile.field_average.toFixed(2)}</div><div className="lbl">μ.ό. πεδίου (/20)</div></div>
            <div className="card stat"><div className="num">{result.n_eligible}</div><div className="lbl">επιλέξιμα τμήματα</div></div>
            <div className="card stat"><div className="num" style={{ color: "#2e8b57" }}>{result.n_likely}</div><div className="lbl">πιθανή εισαγωγή*</div></div>
          </div>

          {!result.profile.complete && (
            <div className="disclaimer">Ελλιπείς βαθμοί — τα μόρια υπολογίστηκαν αναλογικά στα διαθέσιμα μαθήματα.</div>
          )}

          <div className="card">
            <h3>Επιλέξιμα τμήματα <span className="muted small">(περνούν την ΕΒΕ, ταξινομημένα κατά περιθώριο ασφαλείας)</span></h3>
            <table>
              <thead><tr>
                <th>Τμήμα</th><th>Ίδρυμα</th>
                <th className="num">Βάση 2025</th><th className="num">Μόριά σας</th>
                <th className="num">Περιθώριο</th><th>Πρόγνωση</th>
              </tr></thead>
              <tbody>
                {result.eligible.slice(0, 60).map((e) => (
                  <tr key={e.dept_code}>
                    <td><Link to={`/tmima/${e.dept_code}`}>{e.name}</Link></td>
                    <td className="small">{e.institution}</td>
                    <td className="num">{fmtMoria(e.base_last)}</td>
                    <td className="num">{fmtMoria(e.your_moria)}</td>
                    <td className="num" style={{ color: (e.margin ?? 0) >= 0 ? "#2e8b57" : "#c0392b" }}>
                      {e.margin != null ? (e.margin >= 0 ? "+" : "") + fmtMoria(e.margin) : "—"}</td>
                    <td>{e.likely_admit
                      ? <span className="badge ok">πιθανή</span>
                      : <span className="badge ebe">οριακή</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {result.eligible.length > 60 && <p className="small muted">…και {result.eligible.length - 60} ακόμη.</p>}
          </div>

          {result.blocked_by_ebe.length > 0 && (
            <div className="card">
              <h3>Αποκλεισμένα λόγω ΕΒΕ <span className="muted small">({result.blocked_by_ebe.length} τμήματα)</span></h3>
              <p className="small muted">Δεν καλύπτετε το κατώφλι ΕΒΕ σε αυτά τα τμήματα, οπότε αποκλείονται ανεξαρτήτως μορίων.</p>
              <table>
                <thead><tr><th>Τμήμα</th><th>Ίδρυμα</th><th className="num">ΕΒΕ (/20)</th><th className="num">μ.ό. σας</th></tr></thead>
                <tbody>
                  {result.blocked_by_ebe.slice(0, 20).map((e) => (
                    <tr key={e.dept_code}>
                      <td><Link to={`/tmima/${e.dept_code}`}>{e.name}</Link></td>
                      <td className="small">{e.institution}</td>
                      <td className="num">{e.ebe_threshold?.toFixed(2) ?? "—"}</td>
                      <td className="num" style={{ color: "#c0392b" }}>{e.your_field_avg.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="disclaimer">
            * «Πιθανή εισαγωγή» σημαίνει ότι τα μόριά σας ξεπερνούν τη <strong>περσινή</strong> βάση — δεν είναι εγγύηση.
            Οι βάσεις μεταβάλλονται κάθε χρόνο· το μηχανογραφικό παραμένει δική σας απόφαση.
          </div>
        </>
      )}
    </>
  );
}
