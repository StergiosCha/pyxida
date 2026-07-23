import { useEffect, useRef, useState } from "react";
import { api, TrendResp } from "../lib/api";
import { ErrorBox, Loading } from "../lib/hooks";
import { fmtPct } from "../lib/format";

// «Πανεπιστημιακή έρημος» — μέση πληρότητα/κενές ανά περιφέρεια, animated στα
// διαθέσιμα έτη (2015–2019, 2024–2025). Το κενό 2020–2023 ΔΕΝ παρεμβάλλεται.
function heat(v: number): string {
  const t = Math.max(0, Math.min(1, v));
  if (t < 0.5) { const k = t / 0.5; return `rgb(${Math.round(46 + k * 178)},${Math.round(139 + k * 41)},${Math.round(87 - k * 40)})`; }
  const k = (t - 0.5) / 0.5; return `rgb(${Math.round(224 - k * 45)},${Math.round(180 - k * 142)},${Math.round(47 - k * 17)})`;
}

export default function Desert() {
  const [d, setD] = useState<TrendResp | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => { api.statsRegionsTrend().then(setD).catch((e) => setError(String(e))); }, []);

  useEffect(() => {
    if (!playing || !d) return;
    timer.current = window.setInterval(() => {
      setIdx((i) => (i + 1) % d.years.length);
    }, 1100);
    return () => { if (timer.current) window.clearInterval(timer.current); };
  }, [playing, d]);

  if (error) return <div className="page"><ErrorBox error={error} /></div>;
  if (!d) return <div className="page"><Loading /></div>;

  const year = d.years[idx];
  const maxVac = Math.max(0.01, ...d.rows.map((r) => r.avg_vacancy));
  const regs = d.rows.filter((r) => r.year === year).sort((a, b) => b.avg_vacancy - a.avg_vacancy);

  return (
    <div className="page">
      <h1>Πανεπιστημιακή έρημος — η υποχώρηση στον χρόνο</h1>
      <p className="lead">
        Μέση πληρότητα/κενές θέσεις ανά περιφερειακή ενότητα, ανά έτος. Πάτησε «Αναπαραγωγή» για να
        δεις πώς αδειάζει η περιφέρεια ενώ τα μητροπολιτικά κέντρα γεμίζουν.
      </p>

      <div className="desert-controls">
        <button className="play-btn" onClick={() => setPlaying((p) => !p)}>
          {playing ? "⏸ Παύση" : "▶ Αναπαραγωγή"}
        </button>
        <input type="range" min={0} max={d.years.length - 1} step={1} value={idx}
          onChange={(e) => { setPlaying(false); setIdx(Number(e.target.value)); }} />
        <span className="desert-year">{year}</span>
      </div>

      <div className="legend-heat">
        <span>0% κενές</span>
        <div className="heat-gradient" />
        <span>{fmtPct(maxVac, 0)} κενές</span>
      </div>

      <div className="desert-grid">
        {regs.map((r) => (
          <div className="desert-cell" key={r.nuts3}
            title={`${r.region} · ${r.n_dept} τμήματα · ${fmtPct(r.avg_vacancy)} κενές`}>
            <div className="desert-swatch" style={{ background: heat(r.avg_vacancy / maxVac) }}>
              {fmtPct(r.avg_vacancy, 0)}
            </div>
            <span className="desert-label">{r.region}{r.is_metro ? " ●" : ""}</span>
          </div>
        ))}
      </div>

      <p className="source-note">● = μητροπολιτικό κέντρο. {d.gap_note} {d.source_note}</p>
    </div>
  );
}
