import { useEffect, useState } from "react";
import { api, IntentResp } from "../lib/api";
import { ErrorBox, Loading } from "../lib/hooks";
import { fmtPct, fmtEuro } from "../lib/format";

// «Η απόδειξη της πρόθεσης» — για κάθε πρόγραμμα ΝΠΠΕ, οι κενές θέσεις του
// αντίστοιχου δημόσιου πεδίου vs ο εθνικός μέσος όρος. Η ανάγνωση περί πρόθεσης
// είναι ΕΡΜΗΝΕΙΑ (επισημαίνεται)· η αριθμητική κενών είναι ουδέτερη/τεκμηριωμένη.
export default function Intent() {
  const [d, setD] = useState<IntentResp | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { api.nppeIntent().then(setD).catch((e) => setError(String(e))); }, []);

  if (error) return <div className="page"><ErrorBox error={error} /></div>;
  if (!d) return <div className="page"><Loading /></div>;

  const nat = d.national_mean_vacancy;
  const maxV = Math.max(nat, ...d.programs.map((p) => p.public_mean_vacancy), 0.2);

  return (
    <div className="page">
      <h1>Η «πρόθεση»: πού μπήκαν τα μη κρατικά</h1>
      <p className="lead">
        Για κάθε αδειοδοτημένο πρόγραμμα ΝΠΠΕ, οι κενές θέσεις του αντίστοιχου <b>δημόσιου</b>
        πεδίου το 2025, σε σύγκριση με τον εθνικό μέσο όρο κενών ({fmtPct(nat)}). Όσο χαμηλότερες
        οι κενές, τόσο ισχυρότερη η δημόσια ζήτηση στο πεδίο.
      </p>

      <div className="intent-finding">
        <b>Το μοτίβο:</b> και τα πέντε πεδία που επέλεξαν τα ΝΠΠΕ έχουν κενές θέσεις <b>κάτω</b> από
        τον εθνικό μέσο όρο — Ιατρική, Φαρμακευτική, Ψυχολογία στο 0%. Τα ιδιωτικά μπήκαν εκεί που
        το δημόσιο είναι <b>ισχυρότερο</b>, όχι στην περιφέρεια που αδειάζει.
      </div>

      <div className="intent-legend-note">
        <span className="intent-natkey" /> κόκκινη γραμμή = εθνικός μέσος όρος κενών ({fmtPct(nat, 0)})
      </div>
      <div className="intent-chart">
        {d.programs.map((p) => (
          <div className="intent-row" key={p.program}>
            <span className="intent-name">{p.program}
              {p.tuition_eu && <span className="intent-tui"> · δίδακτρα {fmtEuro(p.tuition_eu)}/έτος</span>}
            </span>
            <div className="intent-bar-wrap">
              <div className="intent-bar" style={{ width: `${(p.public_mean_vacancy / maxV) * 100}%` }} />
              <div className="intent-natline" style={{ left: `${(nat / maxV) * 100}%` }} />
            </div>
            <span className="intent-val">{fmtPct(p.public_mean_vacancy, 0)}
              <span className="intent-n"> · {p.n_public_depts} δημ. τμ.</span></span>
          </div>
        ))}
      </div>

      <p className="disclaimer">
        <b>Επιφύλαξη:</b> η σύνδεση κενών→πρόθεσης είναι <i>ερμηνεία</i>, όχι στατιστικό συμπέρασμα.
        Τα δεδομένα δείχνουν ότι τα ΝΠΠΕ στοχεύουν πεδία υψηλής δημόσιας ζήτησης· το «γιατί» παραμένει
        εκτός εμβέλειας των αριθμών.
      </p>
      <p className="source-note">{d.note}</p>
    </div>
  );
}
