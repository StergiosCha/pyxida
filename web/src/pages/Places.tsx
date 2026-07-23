import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, PlacesOptions, PlacesCompareResp } from "../lib/api";
import { ErrorBox, Loading } from "../lib/hooks";
import { fmtInt, fmtPct } from "../lib/format";

// «Σύγκριση πόλεων & ιδρυμάτων» — ΠΟΤΕ ακατέργαστοι μέσοι όροι: μόνο κοινές
// οικογένειες προγραμμάτων, ζευγαρωτά, + αποκαλυμμένες προτιμήσεις (μηχανογραφικό
// 2024, εντός του ίδιου υποψηφίου) ώστε μόρια και αντικείμενο να μένουν σταθερά.
export default function Places() {
  const [opts, setOpts] = useState<PlacesOptions | null>(null);
  const [kind, setKind] = useState<"city" | "institution">("city");
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const [resp, setResp] = useState<PlacesCompareResp | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { api.placesOptions().then(setOpts).catch((e) => setError(String(e))); }, []);
  useEffect(() => { setA(""); setB(""); setResp(null); }, [kind]);

  useEffect(() => {
    if (!a || !b || a === b) { setResp(null); return; }
    setBusy(true); setError(null);
    api.placesCompare(kind, a, b)
      .then(setResp).catch((e) => setError(String(e)))
      .finally(() => setBusy(false));
  }, [kind, a, b]);

  const options = kind === "city"
    ? (opts?.cities ?? []).map((c) => ({ value: c.label, label: `${c.label} (${c.n})` }))
    : (opts?.institutions ?? []).map((i) => ({ value: i.label, label: `${i.label} (${i.n})` }));

  const s = resp?.summary;
  const prefA = s?.pref_total ? s.pref_total.a_share : null;

  return (
    <>
      <div className="card">
        <h2>Σύγκριση πόλεων & ιδρυμάτων</h2>
        <p className="muted small">
          Δίκαιη σύγκριση: μετράμε <strong>μόνο κοινές οικογένειες προγραμμάτων</strong> (ζευγαρωτά) και τις
          <strong> αποκαλυμμένες προτιμήσεις</strong> των ίδιων των υποψηφίων (μηχανογραφικό 2024 — πόσο συχνά,
          μέσα στη λίστα του ίδιου υποψηφίου, η μία πλευρά μπήκε πάνω από την άλλη στο ίδιο πρόγραμμα).
          Ποτέ ακατέργαστοι μέσοι όροι — αυτοί μετρούν σύνθεση προγραμμάτων, όχι τόπο.
        </p>
        <div className="grid cols-3">
          <div className="field">
            <label>Είδος σύγκρισης</label>
            <select value={kind} onChange={(e) => setKind(e.target.value as any)}>
              <option value="city">Πόλη vs Πόλη</option>
              <option value="institution">Ίδρυμα vs Ίδρυμα</option>
            </select>
          </div>
          <div className="field">
            <label>Α</label>
            <select value={a} onChange={(e) => setA(e.target.value)}>
              <option value="">— επιλέξτε —</option>
              {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
          <div className="field">
            <label>Β</label>
            <select value={b} onChange={(e) => setB(e.target.value)}>
              <option value="">— επιλέξτε —</option>
              {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </div>
        </div>
      </div>

      {error && <ErrorBox error={error} />}
      {busy && <Loading />}

      {resp && s && s.n_shared_families === 0 && (
        <div className="card">
          <p className="small">
            Οι δύο πλευρές δεν προσφέρουν <strong>κανένα κοινό πρόγραμμα</strong> — άμεση σύγκριση δεν ορίζεται
            (π.χ. οι πανεπιστημιουπόλεις Ρεθύμνου/Ηρακλείου έχουν ξένα αντικείμενα). Παρακάτω, η σύγκριση γίνεται
            <strong> μέσω κοινών αντιπάλων</strong>: το ποσοστό προτίμησης κάθε πλευράς απέναντι σε τρίτες πόλεις,
            στα δικά της κοινά προγράμματα.
          </p>
        </div>
      )}

      {resp && s && (
        <>
          <div className="grid cols-3">
            <div className="card stat">
              <div className="num">{s.n_shared_families}</div>
              <div className="lbl">κοινές οικογένειες προγραμμάτων</div>
            </div>
            <div className="card stat">
              <div className="num">
                {prefA !== null ? `${Math.round(prefA * 100)}% – ${Math.round((1 - prefA) * 100)}%` : "—"}
              </div>
              <div className="lbl">
                προτίμηση υποψηφίων {s.a} – {s.b}
                {s.pref_total && <> ({fmtInt(s.pref_total.a_wins + s.pref_total.b_wins)} συγκρίσεις)</>}
              </div>
            </div>
            <div className="card stat">
              <div className="num">{s.a_higher_base_count} – {s.b_higher_base_count}</div>
              <div className="lbl">οικογένειες όπου υψηλότερη βάση 2025 έχει {s.a} – {s.b}</div>
            </div>
          </div>

          {s.triangulation && s.triangulation.length > 0 && (
            <div className="card">
              <h3>Μέσω κοινών αντιπάλων <span className="muted small">(% προτίμησης απέναντι στην ίδια τρίτη πόλη)</span></h3>
              <table>
                <thead><tr>
                  <th>Κοινός αντίπαλος</th>
                  <th className="num">{s.a}</th>
                  <th className="num">{s.b}</th>
                  <th className="num">υπεροχή</th>
                </tr></thead>
                <tbody>
                  {s.triangulation.map((t) => (
                    <tr key={t.opponent}>
                      <td>{t.opponent}</td>
                      <td className="num">{Math.round(t.a_share * 100)}% <span className="muted small">(n={fmtInt(t.a_n)})</span></td>
                      <td className="num">{Math.round(t.b_share * 100)}% <span className="muted small">(n={fmtInt(t.b_n)})</span></td>
                      <td className="num" style={{ fontWeight: 700,
                        color: t.a_share > t.b_share ? "var(--ok)" : t.a_share < t.b_share ? "var(--risk-high)" : undefined }}>
                        {t.a_share > t.b_share ? s.a : t.a_share < t.b_share ? s.b : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {resp.families.length > 0 && (
          <div className="card">
            <h3>Ανά κοινή οικογένεια προγράμματος</h3>
            <table>
              <thead><tr>
                <th>Οικογένεια</th>
                <th className="num">Βάση 2025 ({s.a})</th>
                <th className="num">Βάση 2025 ({s.b})</th>
                <th className="num">Δ</th>
                <th className="num">Κενές 2025 ({s.a})</th>
                <th className="num">Κενές 2025 ({s.b})</th>
                <th className="num">Προτίμηση {s.a}</th>
              </tr></thead>
              <tbody>
                {resp.families.map((f) => {
                  const tot = (f.pref_wins_a ?? 0) + (f.pref_wins_b ?? 0);
                  return (
                    <tr key={f.family}>
                      <td className="small">
                        <Link to={`/tmima/${f.a.dept_code}`}>{f.family}</Link>
                      </td>
                      <td className="num">{f.a.base_2025 !== null ? fmtInt(f.a.base_2025) : "—"}</td>
                      <td className="num">{f.b.base_2025 !== null ? fmtInt(f.b.base_2025) : "—"}</td>
                      <td className="num" style={{ fontWeight: 700,
                        color: (f.d_base_2025 ?? 0) > 0 ? "var(--ok)" : (f.d_base_2025 ?? 0) < 0 ? "var(--risk-high)" : undefined }}>
                        {f.d_base_2025 !== null ? (f.d_base_2025 > 0 ? "+" : "") + fmtInt(f.d_base_2025) : "—"}
                      </td>
                      <td className="num">{f.a.vacancy_rate_2025 !== null ? fmtPct(f.a.vacancy_rate_2025) : "—"}</td>
                      <td className="num">{f.b.vacancy_rate_2025 !== null ? fmtPct(f.b.vacancy_rate_2025) : "—"}</td>
                      <td className="num">
                        {tot > 0 ? `${Math.round(100 * (f.pref_wins_a ?? 0) / tot)}% (n=${fmtInt(tot)})` : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <p className="small muted">
              «Προτίμηση»: {s.pref_source}. Δ = βάση {s.a} − βάση {s.b}. Πηγές: data.gov.gr —
              κάθε αριθμός ιχνηλατήσιμος σε αρχείο και έτος.
            </p>
          </div>
          )}
        </>
      )}
    </>
  );
}
