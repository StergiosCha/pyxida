import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useAsync, Loading, ErrorBox } from "../lib/hooks";
import { fmtMoria, fmtPct, FIELD_COLORS } from "../lib/format";

export default function Search() {
  const { data: meta } = useAsync(() => api.meta(), []);
  const { data: cities } = useAsync(() => api.statsCities(), []);
  const [q, setQ] = useState("");
  const [field, setField] = useState("");
  const [city, setCity] = useState("");
  const [moriaMin, setMoriaMin] = useState("");
  const [moriaMax, setMoriaMax] = useState("");
  const [year, setYear] = useState(2025);
  const [applied, setApplied] = useState(0);

  const params = { q, field, city, moria_min: moriaMin, moria_max: moriaMax, year, limit: 200 };
  const { data, error, loading } = useAsync(() => api.departments(params), [applied, year]);

  return (
    <>
      <div className="card">
        <h2>Αναζήτηση τμημάτων</h2>
        <div className="grid" style={{ gridTemplateColumns: "2fr 1fr 1fr 1fr 1fr auto", alignItems: "end" }}>
          <div className="field"><label>Όνομα ή ίδρυμα</label>
            <input type="text" value={q} placeholder="π.χ. Πληροφορικής, ΕΚΠΑ" onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && setApplied((x) => x + 1)} /></div>
          <div className="field"><label>Πεδίο</label>
            <select value={field} onChange={(e) => setField(e.target.value)}>
              <option value="">Όλα</option>
              {(meta?.fields ?? []).map((f) => <option key={f.id} value={f.id}>{f.id}</option>)}
            </select></div>
          <div className="field"><label>Πόλη</label>
            <select value={city} onChange={(e) => { setCity(e.target.value); setApplied((x) => x + 1); }}>
              <option value="">Όλες</option>
              {(cities ?? []).map((cst) => (
                <option key={cst.city} value={cst.city}>{cst.city} ({cst.n_depts})</option>
              ))}
            </select></div>
          <div className="field"><label>Μόρια από</label>
            <input type="number" value={moriaMin} onChange={(e) => setMoriaMin(e.target.value)} /></div>
          <div className="field"><label>έως</label>
            <input type="number" value={moriaMax} onChange={(e) => setMoriaMax(e.target.value)} /></div>
          <div className="field"><button className="btn" onClick={() => setApplied((x) => x + 1)}>Αναζήτηση</button></div>
        </div>
        <div className="small muted">Έτος: {" "}
          <select value={year} onChange={(e) => setYear(Number(e.target.value))}
            style={{ width: "auto", display: "inline-block" }}>
            {(meta?.years ?? []).map((y) => <option key={y} value={y}>{y}</option>)}
          </select> · κατηγορία ΓΕΛ 90%
        </div>
      </div>

      {loading && <Loading />}
      {error && <ErrorBox error={error} />}
      {data && (
        <div className="card">
          <h3>{data.total} τμήματα</h3>
          <table>
            <thead><tr>
              <th>Τμήμα</th><th>Ίδρυμα</th><th>Πόλη</th><th>Πεδίο</th>
              <th className="num">Βάση</th><th className="num">Θέσεις</th>
              <th className="num">Πληρότητα</th><th className="num">ΕΒΕ συντ.</th>
            </tr></thead>
            <tbody>
              {data.items.map((d) => (
                <tr key={d.dept_code}>
                  <td><Link to={`/tmima/${d.dept_code}`}>{d.name}</Link></td>
                  <td className="small">{d.institution}</td>
                  <td className="small">{d.city ?? "—"}</td>
                  <td>{d.scientific_field
                    ? <span className="chip" style={{ background: (FIELD_COLORS[d.scientific_field] ?? "#888") + "22" }}>{d.scientific_field}</span>
                    : "—"}</td>
                  <td className="num">{fmtMoria(d.base_last)}</td>
                  <td className="num">{d.seats_offered ?? "—"}</td>
                  <td className="num">{fmtPct(d.fill_rate)}</td>
                  <td className="num">{d.ebe_coefficient?.toFixed(2) ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
