import { useParams, Link } from "react-router-dom";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ReferenceLine, Legend,
} from "recharts";
import { api } from "../lib/api";
import { useAsync, Loading, ErrorBox } from "../lib/hooks";
import { fmtMoria, fmtInt, fmtPct } from "../lib/format";

export default function DepartmentPage() {
  const { code } = useParams();
  const { data, error, loading } = useAsync(() => api.department(code!), [code]);
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;
  const d = data.department as any;
  // build series; mark the 2020–2023 gap explicitly (null breaks the line)
  const years = [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025];
  const byYear = new Map(data.history.map((h) => [h.year, h]));
  const series = years.map((y) => {
    const h = byYear.get(y);
    return {
      year: y,
      base: h?.base_last ?? null,
      first: h?.grade_first ?? null,
      ebe: h?.ebe_threshold ?? null,
    };
  });
  const latest = data.history[data.history.length - 1];

  return (
    <>
      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
          <div>
            <h2 style={{ marginBottom: 4 }}>{d.name}</h2>
            <div className="muted">{d.institution} · {d.city ?? "—"} · κωδικός {d.dept_code}
              {d.scientific_field ? ` · ${d.scientific_field} πεδίο` : ""}</div>
          </div>
          <Link to="/anazitisi" className="small">← πίσω στην αναζήτηση</Link>
        </div>
      </div>

      <div className="grid cols-4">
        <div className="card stat"><div className="num">{fmtMoria(latest?.base_last)}</div><div className="lbl">βάση {latest?.year}</div></div>
        <div className="card stat"><div className="num">{fmtInt(latest?.seats_offered)}</div><div className="lbl">θέσεις</div></div>
        <div className="card stat"><div className="num">{fmtPct(latest?.fill_rate)}</div><div className="lbl">πληρότητα</div></div>
        <div className="card stat">
          <div className="num">{latest?.ebe_coefficient?.toFixed(2) ?? "—"}</div>
          <div className="lbl">συντελεστής ΕΒΕ</div>
        </div>
      </div>

      <div className="card">
        <h3>Ιστορικό βάσης (2015–2025)</h3>
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={series} margin={{ top: 10, right: 20, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eef2f6" />
            <XAxis dataKey="year" />
            <YAxis domain={["auto", "auto"]} tickFormatter={(v) => fmtInt(v)} width={64} />
            <Tooltip formatter={(v: any) => fmtMoria(v)} labelFormatter={(l) => `Έτος ${l}`} />
            <Legend />
            <ReferenceLine x={2021} stroke="#c0392b" strokeDasharray="4 3"
              label={{ value: "ΕΒΕ 2021", position: "top", fill: "#c0392b", fontSize: 11 }} />
            <Line type="monotone" dataKey="base" name="Βάση (τελευταίου)" stroke="#1f5fa8"
              strokeWidth={2.5} connectNulls={false} dot={{ r: 3 }} />
            <Line type="monotone" dataKey="first" name="Βαθμός πρώτου" stroke="#8fb3d9"
              strokeWidth={1.5} connectNulls={false} dot={false} />
            <Line type="monotone" dataKey="ebe" name="Κατώφλι ΕΒΕ" stroke="#e08214"
              strokeWidth={1.5} strokeDasharray="5 3" connectNulls={false} dot={false} />
          </LineChart>
        </ResponsiveContainer>
        <p className="small muted">Το κενό 2020–2023 αντιστοιχεί σε έτη που απουσιάζουν από τα επίσημα ανοικτά δεδομένα.</p>
      </div>

      {data.demand && data.demand.length > 0 && (
        <div className="card">
          <h3>Ζήτηση <span className="muted small">(πρώτες προτιμήσεις μηχανογραφικού)</span></h3>
          <table>
            <thead><tr>
              <th>Έτος</th><th className="num">1η προτίμηση</th><th className="num">2η</th>
              <th className="num">3η</th><th className="num">Σύνολο δηλώσεων</th>
            </tr></thead>
            <tbody>
              {data.demand.map((d) => (
                <tr key={d.year}>
                  <td>{d.year}</td>
                  <td className="num" style={{ fontWeight: 700 }}>{fmtInt(d.pref1)}</td>
                  <td className="num">{fmtInt(d.pref2)}</td>
                  <td className="num">{fmtInt(d.pref3)}</td>
                  <td className="num">{fmtInt(d.pref_total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="small muted" style={{ marginTop: 8 }}>
            Πόσοι υποψήφιοι δήλωσαν το τμήμα ως 1η/2η/3η προτίμηση — η <b>ζήτηση</b>, ανεξάρτητα
            από το ποιος τελικά εισήχθη. Χαμηλή ζήτηση συνδέεται με υψηλές κενές θέσεις.{" "}
            Πηγή: data.gov.gr, Στατιστικά Μηχανογραφικών Δελτίων.
          </p>
        </div>
      )}

      <div className="card">
        <h3>Αναλυτικά ανά έτος</h3>
        <table>
          <thead><tr>
            <th>Έτος</th><th className="num">Βάση</th><th className="num">Πρώτου</th>
            <th className="num">Θέσεις</th><th className="num">Εισαχθ.</th>
            <th className="num">Κενές</th><th className="num">Πληρότητα</th>
            <th className="num">ΕΒΕ συντ.</th><th>Πηγή</th>
          </tr></thead>
          <tbody>
            {data.history.map((h) => (
              <tr key={h.year}>
                <td>{h.year}</td>
                <td className="num">{fmtMoria(h.base_last)}</td>
                <td className="num">{fmtMoria(h.grade_first)}</td>
                <td className="num">{fmtInt(h.seats_offered)}</td>
                <td className="num">{fmtInt(h.admitted)}</td>
                <td className="num">{fmtInt(h.vacancies)}</td>
                <td className="num">{fmtPct(h.fill_rate)}</td>
                <td className="num">{h.ebe_coefficient?.toFixed(2) ?? "—"}</td>
                <td className="provenance">{h.provenance_note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.aliases.length > 0 && (
        <div className="card">
          <h3>Ιστορικές ονομασίες / συγχωνεύσεις</h3>
          <table>
            <thead><tr><th>Κωδ.</th><th>Παλαιά ονομασία</th><th>Σχέση</th><th>Εμπιστοσύνη</th></tr></thead>
            <tbody>
              {data.aliases.map((a) => (
                <tr key={a.alias_code}>
                  <td>{a.alias_code}</td><td className="small">{a.alias_name}</td>
                  <td><span className="chip">{a.relation === "tei_absorption" ? "απορρόφηση ΤΕΙ" : a.relation}</span></td>
                  <td>{a.confidence}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
