import { useEffect, useState } from "react";
import { api, PrivPathResp } from "../lib/api";
import { ErrorBox, Loading } from "../lib/hooks";
import { fmtInt, fmtEuro } from "../lib/format";

// «Το ιδιωτικό μονοπάτι» — αν χάσεις τη δημόσια βάση, το κόστος του ΝΠΠΕ.
const PROGRAMS = ["Ιατρική", "Φαρμακευτική", "Νομική", "Ψυχολογία", "Διοίκηση Επιχειρήσεων"];

export default function PrivatePath() {
  const [program, setProgram] = useState("Ιατρική");
  const [moria, setMoria] = useState<string>("");
  const [d, setD] = useState<PrivPathResp | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setD(null); setError(null);
    const m = moria.trim() === "" ? undefined : Number(moria);
    api.privatePath(program, m).then(setD).catch((e) => setError(String(e)));
  }, [program, moria]);

  const missedAll = d && d.moria != null && d.reaches_any_public === false;

  return (
    <div className="page">
      <h1>Το ιδιωτικό μονοπάτι — η τιμή της αποτυχίας</h1>
      <p className="lead">
        Διάλεξε πρόγραμμα και (προαιρετικά) τα μόριά σου. Αν δεν φτάνεις καμία δημόσια βάση,
        δες τι κοστίζει η ιδιωτική εναλλακτική — το πλήρες πτυχίο.
      </p>

      <div className="controls">
        <label>Πρόγραμμα:&nbsp;
          <select value={program} onChange={(e) => setProgram(e.target.value)}>
            {PROGRAMS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <label>&nbsp;&nbsp;Μόρια (προαιρετικά):&nbsp;
          <input type="number" value={moria} min={0} max={20000} step={100}
            placeholder="π.χ. 17500" style={{ width: 110 }}
            onChange={(e) => setMoria(e.target.value)} />
        </label>
      </div>

      {error && <ErrorBox error={error} />}
      {!d && !error && <Loading />}

      {d && (
        <>
          {d.private_alternatives.map((p) => (
            <div className={"pp-price " + (missedAll ? "pp-price-alarm" : "")} key={p.institution}>
              <div>
                <div className="pp-inst">{p.institution} <span className="muted">({p.city})</span></div>
                <div className="pp-terms">{fmtEuro(p.tuition_eu)}/έτος × {p.degree_years} έτη</div>
              </div>
              <div className="pp-total">{fmtEuro(p.total_cost_eur)}</div>
            </div>
          ))}

          {missedAll && (
            <div className="pp-verdict">
              Με <b>{fmtInt(d.moria)}</b> μόρια δεν φτάνεις καμία δημόσια {d.program} —
              η μόνη διαδρομή είναι η ιδιωτική, με το παραπάνω κόστος.
            </div>
          )}

          <h3>Δημόσιες σχολές {d.program} (βάσεις {d.year})</h3>
          <div className="pp-pub-list">
            {d.public_departments.map((r) => (
              <div className={"pp-pub " + (r.reachable ? "reach" : d.moria != null ? "miss" : "")} key={r.name}>
                <span className="pp-pub-name">{r.name}</span>
                <span className="pp-pub-base">{fmtInt(r.base_last)}</span>
                {d.moria != null && (
                  <span className="pp-pub-gap">
                    {r.reachable ? "✓ φτάνεις" : `−${fmtInt(r.gap)} μόρια`}
                  </span>
                )}
              </div>
            ))}
          </div>
          <p className="source-note">{d.note}</p>
        </>
      )}
    </div>
  );
}
