import { useEffect, useState } from "react";
import { api, ProjResp } from "../lib/api";
import { ErrorBox, Loading } from "../lib/hooks";
import { fmtPct } from "../lib/format";

// «Αν συνεχιστεί η τάση» — ΣΕΝΑΡΙΟ, όχι πρόβλεψη. Παρατηρούμενο (συμπαγές) vs
// προβολή (διακεκομμένο/γκρι). Δύο μοντέλα· η απόκλισή τους δείχνει την αβεβαιότητα.
export default function Projection() {
  const [model, setModel] = useState("linear");
  const [d, setD] = useState<ProjResp | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setD(null); setError(null);
    api.statsProjection(model).then(setD).catch((e) => setError(String(e)));
  }, [model]);

  return (
    <div className="page">
      <h1>Το 2030, αν δεν αλλάξει τίποτα</h1>
      <div className="scenario-banner">
        ⚠ ΣΕΝΑΡΙΟ, όχι πρόβλεψη. Γραμμική προβολή της τάσης 2015–2025 στις κενές θέσεις ανά
        περιφέρεια. Δείχνει την <b>τροχιά</b> αν δεν αλλάξει τίποτα — όχι τι θα συμβεί.
      </div>

      <div className="controls">
        <label>Μοντέλο:&nbsp;
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            <option value="linear">Γραμμικό (όλα τα έτη)</option>
            <option value="recent">Πρόσφατη τάση (3 τελευταία έτη)</option>
          </select>
        </label>
      </div>

      {error && <ErrorBox error={error} />}
      {!d && !error && <Loading />}

      {d && (
        <>
          <p className="sub">{d.n_regions} περιφέρειες · παρατηρούμενα έτη: {d.observed_years.join(", ")}
            {d.n_suppressed > 0 && ` · ${d.n_suppressed} αποκρύφθηκαν (πολύ λίγα σημεία)`}</p>
          <div className="proj-list">
            {d.regions.map((r) => (
              <div className="proj-row" key={r.nuts3}>
                <span className="proj-name">{r.region}{r.is_metro ? " ●" : ""}</span>
                <span className="proj-now">τώρα {fmtPct(r.latest_vacancy, 0)}</span>
                <div className="proj-track">
                  <div className="proj-observed" style={{ width: `${r.latest_vacancy * 100}%` }} />
                  <div className="proj-band" style={{
                    left: `${r.proj_lo * 100}%`, width: `${Math.max(1, (r.proj_hi - r.proj_lo) * 100)}%` }} />
                  <div className="proj-point" style={{ left: `${r.proj_vacancy * 100}%` }} />
                </div>
                <span className="proj-target">
                  {r.at_ceiling ? "→ πλήρης ερήμωση" : `${d.target_year}: ${fmtPct(r.proj_vacancy, 0)}`}
                  <span className="proj-ci"> [{fmtPct(r.proj_lo, 0)}–{fmtPct(r.proj_hi, 0)}]</span>
                </span>
              </div>
            ))}
          </div>
          <div className="proj-legend">
            <span><i className="lg-obs" /> παρατηρούμενο (2025)</span>
            <span><i className="lg-band" /> διάστημα πρόβλεψης 95%</span>
            <span><i className="lg-pt" /> προβολή {d.target_year}</span>
            <span>● = μητρόπολη</span>
          </div>
          <p className="disclaimer">{d.caveat}</p>
        </>
      )}
    </div>
  );
}
