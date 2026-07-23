import { useState } from "react";
import { Link } from "react-router-dom";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend,
  ScatterChart, Scatter, ZAxis,
} from "recharts";
import { api } from "../lib/api";
import { useAsync, Loading, ErrorBox } from "../lib/hooks";
import { fmtInt, fmtPct, FIELD_COLORS, riskColor } from "../lib/format";

function VacancyHeatmap({ byYear }: { byYear: { year: number; vacancy_rate: number; vacancies: number }[] }) {
  const max = Math.max(...byYear.map((r) => r.vacancy_rate), 0.01);
  return (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
      {byYear.map((r) => {
        const t = r.vacancy_rate / max;
        const bg = `rgba(192,57,43,${0.12 + 0.8 * t})`;
        return (
          <div key={r.year} title={`${fmtInt(r.vacancies)} κενές`} style={{
            flex: "1 0 90px", background: bg, borderRadius: 8, padding: "12px 8px",
            textAlign: "center", color: t > 0.5 ? "#fff" : "#5b1b14", border: "1px solid #f0dede",
          }}>
            <div style={{ fontWeight: 700 }}>{r.year}</div>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{fmtPct(r.vacancy_rate)}</div>
            <div style={{ fontSize: 11 }}>{fmtInt(r.vacancies)} κενές</div>
          </div>
        );
      })}
    </div>
  );
}

export default function Dashboard() {
  const fields = useAsync(() => api.statsFields(), []);
  const vac = useAsync(() => api.statsVacancies(), []);
  const risk = useAsync(() => api.statsRisk({ all: true }), []);
  const demand = useAsync(() => api.statsDemand(2025), []);
  const [showAllRisk, setShowAllRisk] = useState(true);

  // demand scatter: log(1+pref1) vs vacancy%
  const demandPts = (demand.data?.rows ?? []).map((r) => ({
    x: Math.log1p(r.pref1),
    y: (r.vacancy_rate ?? 0) * 100,
    name: r.name, city: r.city, pref1: r.pref1,
  }));

  // pivot field stats -> [{year, "1ο":.., "2ο":..}]
  let fieldSeries: any[] = [];
  if (fields.data) {
    const byYear = new Map<number, any>();
    for (const r of fields.data) {
      if (!byYear.has(r.year)) byYear.set(r.year, { year: r.year });
      byYear.get(r.year)[r.field] = r.median_base;
    }
    fieldSeries = [...byYear.values()].sort((a, b) => a.year - b.year);
  }
  const fieldKeys = ["1ο", "2ο", "3ο", "4ο"];

  return (
    <>
      <div className="card">
        <h2>Στατιστικά & τάσεις</h2>
        <p className="muted small">Κατηγορία ΓΕΛ 90% ημερήσια — ο βασικός αναλυτικός κορμός.</p>
      </div>

      <div className="card">
        <h3>Διάμεση βάση ανά επιστημονικό πεδίο</h3>
        {fields.loading && <Loading />}
        {fields.error && <ErrorBox error={fields.error} />}
        {fieldSeries.length > 0 && (
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={fieldSeries}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eef2f6" />
              <XAxis dataKey="year" />
              <YAxis tickFormatter={(v) => fmtInt(v)} width={64} />
              <Tooltip formatter={(v: any) => fmtInt(v)} labelFormatter={(l) => `Έτος ${l}`} />
              <Legend />
              {fieldKeys.map((k) => (
                <Line key={k} type="monotone" dataKey={k} name={`${k} πεδίο`}
                  stroke={FIELD_COLORS[k]} strokeWidth={2} connectNulls={false} dot={{ r: 2 }} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      <div className="card">
        <h3>Κενές θέσεις ανά έτος (heatmap)</h3>
        {vac.loading && <Loading />}
        {vac.error && <ErrorBox error={vac.error} />}
        {vac.data && (
          <>
            <VacancyHeatmap byYear={vac.data.by_year} />
            <p className="small muted" style={{ marginTop: 10 }}>
              Το ποσοστό κενών θέσεων εκτοξεύεται από &lt;1% (2015–2019) σε ~17% (2024–2025) —
              η υπογραφή του καθεστώτος ΕΒΕ. Το 2025 καταγράφηκαν {fmtInt(vac.data.by_year.find((r) => r.year === 2025)?.vacancies)} κενές
              θέσεις ΓΕΛ (έκθεση: 10.636).
            </p>
          </>
        )}
      </div>

      <div className="card">
        <h3>Ζήτηση εναντίον κενών θέσεων <span className="muted small">(πρώτες προτιμήσεις 2025)</span></h3>
        {demand.loading && <Loading />}
        {demand.error && <ErrorBox error={demand.error} />}
        {demand.data && !demand.data.available && (
          <p className="small muted">{demand.data.note}</p>
        )}
        {demand.data && demand.data.available && (
          <>
            <ResponsiveContainer width="100%" height={320}>
              <ScatterChart margin={{ top: 10, right: 20, bottom: 30, left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
                <XAxis type="number" dataKey="x" name="log(πρώτες προτιμήσεις)"
                  domain={[0, "dataMax"]} tick={{ fontSize: 11 }}
                  label={{ value: "log(1 + πρώτες προτιμήσεις)", position: "bottom", fontSize: 11 }} />
                <YAxis type="number" dataKey="y" name="κενές %" unit="%"
                  domain={[0, 100]} tick={{ fontSize: 11 }} />
                <ZAxis range={[30, 30]} />
                <Tooltip cursor={{ strokeDasharray: "3 3" }}
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const d: any = payload[0].payload;
                    return (
                      <div style={{ background: "#fff", border: "1px solid #ddd", borderRadius: 6, padding: "6px 9px", fontSize: 12 }}>
                        <div style={{ fontWeight: 700 }}>{d.name}</div>
                        <div className="muted">{d.city}</div>
                        <div>{fmtInt(d.pref1)} πρώτες προτιμήσεις · {d.y.toFixed(0)}% κενές</div>
                      </div>
                    );
                  }} />
                <Scatter data={demandPts} fill="#c0392b" fillOpacity={0.5} />
              </ScatterChart>
            </ResponsiveContainer>
            <p className="small muted" style={{ marginTop: 8 }}>
              Κάθε σημείο = ένα τμήμα ({demand.data.n} συνολικά, ΓΕΛ90 2025). Οι πρώτες προτιμήσεις
              δείχνουν τι <b>θέλουν</b> οι υποψήφιοι, ανεξάρτητα από το ποιος εισήχθη. Τα τμήματα που
              κανείς δεν δηλώνει πρώτα είναι αυτά που αδειάζουν: συσχέτιση r ≈ −0,65 (μερικός r ≈ −0,61
              ελέγχοντας για τη βάση του 2019). <b>Συσχέτιση, όχι απόδειξη αιτιότητας.</b>{" "}
              Πηγή: data.gov.gr, Στατιστικά Μηχανογραφικών Δελτίων.
            </p>
          </>
        )}
      </div>

      <div className="card">
        <h3>Τμήματα σε κίνδυνο <span className="muted small">(χαμηλή ζήτηση + υψηλές κενές + σήμα συγχώνευσης)</span></h3>
        {risk.data && (
          <p className="small muted">
            {risk.data.items.length} τμήματα, ταξινομημένα κατά φθίνοντα δείκτη.{" "}
            <a style={{ cursor: "pointer" }} onClick={() => setShowAllRisk((v) => !v)}>
              {showAllRisk ? "εμφάνιση top 25" : "εμφάνιση όλων"}
            </a>
          </p>
        )}
        {risk.loading && <Loading />}
        {risk.error && <ErrorBox error={risk.error} />}
        {risk.data && (
          <table>
            <thead><tr>
              <th>#</th><th>Τμήμα</th><th>Ίδρυμα</th>
              <th className="num">Πληρότητα</th><th className="num">Κενές</th>
              <th className="num">Δείκτης</th><th>Κατηγορία</th>
            </tr></thead>
            <tbody>
              {(showAllRisk ? risk.data.items : risk.data.items.slice(0, 25)).map((r, i) => (
                <tr key={r.dept_code}>
                  <td className="muted">{i + 1}</td>
                  <td><Link to={`/tmima/${r.dept_code}`}>{r.name}</Link></td>
                  <td className="small">{r.institution}</td>
                  <td className="num">{fmtPct(r.fill_rate)}</td>
                  <td className="num">{fmtInt(r.vacancies)}/{fmtInt(r.seats_offered)}</td>
                  <td className="num" style={{ fontWeight: 700 }}>{r.risk_score.toFixed(2)}</td>
                  <td><span className="badge" style={{ background: riskColor(r.risk_band) + "22", color: riskColor(r.risk_band) }}>{r.risk_band}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
