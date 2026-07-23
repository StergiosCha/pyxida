import { api } from "../lib/api";
import { useAsync, Loading, ErrorBox } from "../lib/hooks";
import { fmtEuro, fmtInt } from "../lib/format";

export default function Nppe() {
  const { data, error, loading } = useAsync(() => api.nppe(), []);
  if (loading) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;

  // group by institution
  const byInst = new Map<string, typeof data.items>();
  for (const it of data.items) {
    if (!byInst.has(it.institution)) byInst.set(it.institution, []);
    byInst.get(it.institution)!.push(it);
  }

  return (
    <>
      <div className="card">
        <h2>Μη κρατικά πανεπιστήμια (ΝΠΠΕ)</h2>
        <p className="muted small">
          Νομικά Πρόσωπα Πανεπιστημιακής Εκπαίδευσης (ν.5094/2024) — τα αδειοδοτημένα ιδρύματα, τα προγράμματα
          και τα δίδακτρα, δίπλα στις δημόσιες εναλλακτικές.
        </p>
        <div className="disclaimer">{data.note}</div>
      </div>

      {[...byInst.entries()].map(([inst, progs]) => (
        <div className="card" key={inst}>
          <h3>{inst} <span className="muted small">· μητρικό: {progs[0].parent_uni} · {progs[0].city}</span></h3>
          <table>
            <thead><tr>
              <th>Πρόγραμμα</th><th className="num">Έτη</th>
              <th className="num">Δίδακτρα (ΕΕ)</th><th className="num">Δίδακτρα (εκτός ΕΕ)</th>
              <th className="num">Εγγραφές</th><th>Δημόσια αντιστοιχία</th>
            </tr></thead>
            <tbody>
              {progs.map((p) => (
                <tr key={p.nppe_id}>
                  <td>{p.program}
                    {p.note ? <div className="provenance">{p.note}</div> : null}</td>
                  <td className="num">{p.degree_years}</td>
                  <td className="num">{fmtEuro(p.tuition_eu)}</td>
                  <td className="num">{fmtEuro(p.tuition_intl)}</td>
                  <td className="num">
                    {p.enrollment != null ? fmtInt(p.enrollment) : "—"}{" "}
                    {p.enrollment != null && !p.enrollment_is_official &&
                      <span className="badge unofficial" title="Στοιχείο από δημοσιεύματα, όχι επίσημο">μη επίσημο</span>}
                  </td>
                  <td className="small muted">{p.public_analog_dept ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </>
  );
}
