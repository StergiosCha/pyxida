import { useEffect, useState } from "react";
import { api, RegionsResp, AbandonResp } from "../lib/api";
import { ErrorBox, Loading } from "../lib/hooks";
import { fmtInt, fmtPct, fmtEuro } from "../lib/format";

function AbandonmentCost() {
  const [d, setD] = useState<AbandonResp | null>(null);
  useEffect(() => { api.abandonmentCost().then(setD).catch(() => {}); }, []);
  if (!d) return null;
  return (
    <div className="abandon-card">
      <h2>Το κόστος της εγκατάλειψης</h2>
      <div className="abandon-figures">
        <div className="abandon-fig">
          <span className="abandon-num">{fmtInt(d.empty_seats)}</span>
          <span className="abandon-lbl">κενές θέσεις ({d.year}, {d.category})</span>
        </div>
        <div className="abandon-x">×</div>
        <div className="abandon-fig">
          <span className="abandon-num">{fmtEuro(d.per_student_eur)}</span>
          <span className="abandon-lbl">δημόσια δαπάνη/φοιτητή/έτος ({d.per_student_year})</span>
        </div>
        <div className="abandon-eq">=</div>
        <div className="abandon-fig abandon-total">
          <span className="abandon-num">{fmtEuro(d.annual_cost_eur)}</span>
          <span className="abandon-lbl">/έτος · {fmtEuro(d.degree_cost_eur)} σε {d.degree_years_example} έτη</span>
        </div>
      </div>
      <p className="abandon-caveat">{d.caveat}</p>
      <div className="src">Πηγή δαπάνης: <a href={d.per_student_url} target="_blank" rel="noreferrer">{d.per_student_source}</a></div>
    </div>
  );
}

// «Χάρτης κινδύνου ανά περιφέρεια» — μέση πληρότητα/κενές ανά περιφερειακή
// ενότητα (NUTS-3). Χρωματική κλίμακα κενών θέσεων· διαχωρισμός μητρόπολης /
// περιφέρειας. ΔΕΝ εμφανίζεται δημογραφική επικάλυψη (cohort) γιατί δεν
// υπάρχει τεκμηριωμένη σειρά μεγέθους ηλικιακής κοόρτης ανά περιφέρεια — δεν
// κατασκευάζεται πλασματικά.
const CATS = ["ΓΕΛ90", "ΕΠΑΛ90", "ΓΕΛ10", "ΕΠΑΛ10"];

function heat(v: number): string {
  // 0 -> green, 0.5 -> amber, 1 -> deep red
  const t = Math.max(0, Math.min(1, v));
  if (t < 0.5) {
    const k = t / 0.5;
    return `rgb(${Math.round(46 + k * 178)},${Math.round(139 + k * 41)},${Math.round(87 - k * 40)})`;
  }
  const k = (t - 0.5) / 0.5;
  return `rgb(${Math.round(224 - k * 45)},${Math.round(180 - k * 142)},${Math.round(47 - k * 17)})`;
}

export default function RegionMap() {
  const [cat, setCat] = useState("ΓΕΛ90");
  const [data, setData] = useState<RegionsResp | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setData(null); setError(null);
    api.statsRegions(cat).then(setData).catch((e) => setError(String(e)));
  }, [cat]);

  const metro = data?.regions.filter((r) => r.is_metro) ?? [];
  const periphery = data?.regions.filter((r) => !r.is_metro) ?? [];
  const maxVac = Math.max(0.01, ...(data?.regions.map((r) => r.avg_vacancy) ?? [1]));

  return (
    <div className="page">
      <h1>Χάρτης κινδύνου ανά περιφέρεια</h1>
      <p className="lead">
        Μέση πληρότητα/κενές θέσεις ανά <b>περιφερειακή ενότητα (NUTS-3)</b>. Η κατανομή δείχνει
        καθαρά ότι οι κενές θέσεις συγκεντρώνονται στην <b>περιφέρεια</b>, όχι στα μητροπολιτικά
        κέντρα — το μοτίβο της περιφερειακής απαξίωσης.
      </p>

      <AbandonmentCost />

      <div className="controls">
        <label>Κατηγορία:&nbsp;
          <select value={cat} onChange={(e) => setCat(e.target.value)}>
            {CATS.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>
      </div>

      {error && <ErrorBox error={error} />}
      {!data && !error && <Loading />}

      {data && (
        <>
          <div className="legend-heat">
            <span>0% κενές</span>
            <div className="heat-gradient" />
            <span>{fmtPct(maxVac, 0)} κενές</span>
          </div>

          <div className="region-cols">
            <RegionCol title="Περιφέρεια (εκτός μητρόπολης)" rows={periphery} maxVac={maxVac} />
            <RegionCol title="Μητροπολιτικά κέντρα" rows={metro} maxVac={maxVac} />
          </div>

          <p className="source-note">{data.source_note}</p>
        </>
      )}
    </div>
  );
}

function RegionCol({ title, rows, maxVac }: { title: string; rows: RegionsResp["regions"]; maxVac: number }) {
  return (
    <div className="region-col">
      <h3>{title} <span className="muted">({rows.length})</span></h3>
      <div className="region-list">
        {rows.map((r) => (
          <div className="region-row" key={r.nuts3} title={`${r.n_dept} τμήματα · ${fmtInt(r.admitted)} εισαχθέντες`}>
            <span className="region-name">{r.region}</span>
            <div className="region-bar-wrap">
              <div className="region-bar" style={{
                width: `${(r.avg_vacancy / maxVac) * 100}%`,
                background: heat(r.avg_vacancy),
              }} />
            </div>
            <span className="region-val">{fmtPct(r.avg_vacancy, 0)}</span>
            <span className="region-n">{r.n_dept} τμ.</span>
          </div>
        ))}
      </div>
    </div>
  );
}
