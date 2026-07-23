import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  ComposedChart, Line, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ReferenceLine, Legend,
} from "recharts";
import { api, WhatIfDefaults, WhatIfResp, DeptRow } from "../lib/api";
import { ErrorBox } from "../lib/hooks";
import { fmtMoria, fmtInt } from "../lib/format";

// Προσομοιωτής 2026: sliders για υποθέσεις ζήτησης / ΕΒΕ → ζώνες πρόβλεψης live.
// Κάθε αριθμός βάσης προέρχεται από το DB (carry-forward + ΦΕΚ συντελεστές)·
// τα sliders ορίζουν ρητά επισημασμένες ΥΠΟΘΕΣΕΙΣ, όχι νέες «προβλέψεις».
export default function Simulator() {
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<DeptRow[]>([]);
  const [code, setCode] = useState<string | null>(params.get("code"));
  const [defs, setDefs] = useState<WhatIfDefaults | null>(null);
  const [sim, setSim] = useState<WhatIfResp | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [demand, setDemand] = useState(0);   // -15..+15 %
  const [ebeShift, setEbeShift] = useState(0); // -15..+15 %
  const [coef, setCoef] = useState<number | null>(null);

  // department search
  useEffect(() => {
    if (q.trim().length < 2) { setHits([]); return; }
    const t = setTimeout(async () => {
      try {
        const r = await api.departments({ q, limit: 8 });
        setHits(r.items);
      } catch (e) { setError(String(e)); }
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  // load defaults when a department is picked
  useEffect(() => {
    if (!code) return;
    setError(null); setSim(null);
    api.whatifDefaults(code)
      .then((d) => { setDefs(d); setCoef(d.coefficient_2026 ?? null);
                     setDemand(0); setEbeShift(0);
                     setParams({ code }, { replace: true }); })
      .catch((e) => setError(String(e)));
  }, [code]);

  // re-simulate on any slider change (debounced)
  useEffect(() => {
    if (!code || !defs) return;
    const t = setTimeout(async () => {
      try {
        const r = await api.whatifSimulate({
          dept_code: code, demand_shift_pct: demand,
          ebe_base_shift_pct: ebeShift, coefficient: coef ?? undefined,
        });
        setSim(r); setError(null);
      } catch (e) { setError(String(e)); }
    }, 150);
    return () => clearTimeout(t);
  }, [code, defs, demand, ebeShift, coef]);

  const years = [2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026];
  const byYear = new Map((defs?.history ?? []).map((h) => [h.year, h]));
  const base = defs?.prediction ?? null;
  const adj = sim?.adjusted_prediction ?? null;
  const floor = sim?.ebe_floor_est?.threshold_moria_approx ?? null;
  const series = years.map((y) => ({
    year: y,
    base: byYear.get(y)?.base_last ?? null,
    // baseline band, drawn only at 2026 (anchored on 2025 for a joined ribbon)
    b_lo: y === 2026 ? base?.lower_80 ?? null : y === 2025 ? byYear.get(2025)?.base_last ?? null : null,
    b_hi: y === 2026 ? base?.upper_80 ?? null : y === 2025 ? byYear.get(2025)?.base_last ?? null : null,
    b_pt: y === 2026 ? base?.point ?? null : y === 2025 ? byYear.get(2025)?.base_last ?? null : null,
    a_lo: y === 2026 ? adj?.lower_80 ?? null : y === 2025 ? byYear.get(2025)?.base_last ?? null : null,
    a_hi: y === 2026 ? adj?.upper_80 ?? null : y === 2025 ? byYear.get(2025)?.base_last ?? null : null,
    a_pt: y === 2026 ? adj?.point ?? null : y === 2025 ? byYear.get(2025)?.base_last ?? null : null,
  }));
  const changed = demand !== 0 || ebeShift !== 0 ||
    (coef !== null && defs?.coefficient_2026 !== null && coef !== defs?.coefficient_2026);

  return (
    <>
      <div className="card">
        <h2>Προσομοιωτής σεναρίων 2026</h2>
        <p className="muted small">
          Επιλέξτε τμήμα και ορίστε <strong>υποθέσεις</strong> για τη ζήτηση και την ΕΒΕ του 2026.
          Οι ζώνες ενημερώνονται ζωντανά. Βάση εκκίνησης: πρόβλεψη carry-forward με διαστήματα
          εμπιστοσύνης και ο <strong>συντελεστής ΕΒΕ 2026 του ΦΕΚ</strong> (ΥΑ Φ.253/160742/Α5,
          ΦΕΚ Β΄ 6782/16-12-2025). Ένα σενάριο δεν είναι πρόβλεψη.
        </p>
        <div className="field" style={{ maxWidth: 460 }}>
          <label>Αναζήτηση τμήματος</label>
          <input type="text" value={q} placeholder="π.χ. Ιατρικής ή 127"
            onChange={(e) => setQ(e.target.value)} />
          {hits.length > 0 && (
            <div className="card" style={{ marginTop: 6, padding: 8 }}>
              {hits.map((h) => (
                <div key={h.dept_code} style={{ padding: "4px 6px", cursor: "pointer" }}
                  onClick={() => { setCode(h.dept_code); setQ(""); setHits([]); }}>
                  <strong>{h.dept_code}</strong> — {h.name} <span className="muted small">{h.institution}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {error && <ErrorBox error={error} />}

      {defs && (
        <>
          <div className="grid cols-3">
            <div className="card">
              <label>Υπόθεση ζήτησης τμήματος: <strong>{demand > 0 ? "+" : ""}{demand}%</strong></label>
              <input type="range" min={-15} max={15} step={1} value={demand}
                onChange={(e) => setDemand(Number(e.target.value))} style={{ width: "100%" }} />
              <p className="small muted">Μετατοπίζει όλη τη ζώνη πρόβλεψης (π.χ. αλλαγή προτιμήσεων, εισακτέων).</p>
            </div>
            <div className="card">
              <label>Υπόθεση βάσης πεδίου (ΕΒΕ): <strong>{ebeShift > 0 ? "+" : ""}{ebeShift}%</strong></label>
              <input type="range" min={-15} max={15} step={1} value={ebeShift}
                onChange={(e) => setEbeShift(Number(e.target.value))} style={{ width: "100%" }} />
              <p className="small muted">
                Μεταβάλλει τον μέσο όρο επιδόσεων του πεδίου {defs.field ?? "—"} (βάση {defs.field_ebe_base_year ?? "—"}:
                {" "}{defs.field_ebe_base_latest ?? "—"}/20).
              </p>
            </div>
            <div className="card">
              <label>Συντελεστής ΕΒΕ 2026: <strong>{coef?.toFixed(2) ?? "—"}</strong>
                {defs.coefficient_2026 != null && coef !== defs.coefficient_2026 &&
                  <span className="chip" style={{ marginLeft: 6 }}>ΦΕΚ: {defs.coefficient_2026.toFixed(2)}</span>}
              </label>
              <input type="range" min={0.8} max={1.2} step={0.01}
                value={coef ?? 1} disabled={coef === null}
                onChange={(e) => setCoef(Number(e.target.value))} style={{ width: "100%" }} />
              <p className="small muted">
                {defs.coefficient_2026 != null
                  ? <>Προεπιλογή: ο δημοσιευμένος συντελεστής του ΦΕΚ ({defs.coefficient_2026.toFixed(2)}).</>
                  : <>Δεν υπάρχει δημοσιευμένος συντελεστής 2026 για αυτό το τμήμα.</>}
              </p>
            </div>
          </div>

          <div className="card">
            <h3>Βάση 2015–2025 και ζώνη 2026 υπό τις υποθέσεις σας</h3>
            <ResponsiveContainer width="100%" height={320}>
              <ComposedChart data={series} margin={{ top: 10, right: 20, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eef2f6" />
                <XAxis dataKey="year" />
                <YAxis domain={["auto", "auto"]} tickFormatter={(v) => fmtInt(v)} width={64} />
                <Tooltip formatter={(v: any) => fmtMoria(v)} labelFormatter={(l) => `Έτος ${l}`} />
                <Legend />
                <ReferenceLine x={2021} stroke="#c0392b" strokeDasharray="4 3"
                  label={{ value: "ΕΒΕ 2021", position: "top", fill: "#c0392b", fontSize: 11 }} />
                {floor !== null && (
                  <ReferenceLine y={floor} stroke="#e08214" strokeDasharray="5 3"
                    label={{ value: `κατώφλι ΕΒΕ ~${fmtInt(floor)}`, position: "insideBottomRight",
                             fill: "#e08214", fontSize: 11 }} />
                )}
                <Line type="monotone" dataKey="base" name="Βάση (ιστορικό)" stroke="#1f5fa8"
                  strokeWidth={2.5} connectNulls={false} dot={{ r: 3 }} />
                <Area type="monotone" dataKey="b_hi" name="ζώνη 80% (baseline)" stroke="none"
                  fill="#8fb3d9" fillOpacity={0.25} connectNulls={false} legendType="none" />
                <Area type="monotone" dataKey="b_lo" stroke="none" fill="#ffffff"
                  fillOpacity={1} connectNulls={false} legendType="none" />
                <Line type="monotone" dataKey="b_pt" name="Πρόβλεψη 2026 (baseline)"
                  stroke="#8fb3d9" strokeWidth={1.5} strokeDasharray="4 3" connectNulls dot={{ r: 3 }} />
                {changed && <Line type="monotone" dataKey="a_pt" name="Σενάριό σας"
                  stroke="#e08214" strokeWidth={2} strokeDasharray="6 3" connectNulls dot={{ r: 4 }} />}
              </ComposedChart>
            </ResponsiveContainer>
            <p className="small muted">
              Το κενό 2020–2023 αντιστοιχεί σε έτη που απουσιάζουν από τα επίσημα ανοικτά δεδομένα.
            </p>
          </div>

          <div className="grid cols-3">
            <div className="card stat">
              <div className="num">{adj ? fmtMoria(adj.point) : base ? fmtMoria(base.point) : "—"}</div>
              <div className="lbl">σημείο 2026 {changed ? "(σενάριο)" : "(baseline)"}</div>
            </div>
            <div className="card stat">
              <div className="num">
                {adj ? `${fmtInt(adj.lower_80)}–${fmtInt(adj.upper_80)}`
                     : base ? `${fmtInt(base.lower_80)}–${fmtInt(base.upper_80)}` : "—"}
              </div>
              <div className="lbl">80% διάστημα</div>
            </div>
            <div className="card stat">
              <div className="num">{sim?.ebe_bound === true ? "ΝΑΙ" : sim?.ebe_bound === false ? "ΟΧΙ" : "—"}</div>
              <div className="lbl">πιθανός περιορισμός από ΕΒΕ;</div>
            </div>
          </div>

          {sim?.ebe_floor_est && (
            <div className="card">
              <h3>Εκτίμηση κατωφλιού ΕΒΕ 2026</h3>
              <p className="small">
                {sim.ebe_floor_est.note} → <strong>{sim.ebe_floor_est.threshold_20}/20</strong>{" "}
                (≈ {fmtInt(sim.ebe_floor_est.threshold_moria_approx)} στην κλίμακα μορίων ×1000).
              </p>
              <p className="small muted">{sim.disclaimer}</p>
            </div>
          )}

          <p className="small">
            <Link to={`/tmima/${code}`}>→ πλήρες προφίλ τμήματος</Link>
          </p>
        </>
      )}
    </>
  );
}
