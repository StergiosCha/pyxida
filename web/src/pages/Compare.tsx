import { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Legend,
} from "recharts";
import { api, CompareResp, FamilyItem, AdvisorResp } from "../lib/api";
import { useAsync, Loading, ErrorBox } from "../lib/hooks";
import { fmtMoria, fmtInt, fmtPct } from "../lib/format";
import Markdown from "../lib/Markdown";
import LlmKeyPanel from "../lib/LlmKeyPanel";
import { getLlmCreds } from "../lib/llmKey";

export default function Compare() {
  const fams = useAsync(() => api.compareFamilies(2), []);
  const [family, setFamily] = useState<string>("");
  const [data, setData] = useState<CompareResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [comment, setComment] = useState<AdvisorResp | null>(null);
  const [commenting, setCommenting] = useState(false);
  const [commentErr, setCommentErr] = useState<string | null>(null);

  async function load(f: string) {
    setFamily(f); setData(null); setComment(null); setCommentErr(null);
    if (!f) return;
    setLoading(true); setErr(null);
    try { setData(await api.compareFamily(f)); }
    catch (e: any) { setErr(e?.message ?? String(e)); }
    finally { setLoading(false); }
  }

  async function analyse() {
    if (!family) return;
    setCommenting(true); setCommentErr(null); setComment(null);
    try {
      setComment(await api.advisor({
        intent: "compare", family,
        question: `Σχολίασε τη σύγκριση των τμημάτων «${family}» ανά πόλη μετά την ΕΒΕ.`,
        ...getLlmCreds(),
      }));
    } catch (e: any) {
      setCommentErr(String(e?.message ?? e).includes("503")
        ? "Ο σχολιασμός με LLM είναι απενεργοποιημένος (PYXIDA_ENABLE_RAG=0)."
        : (e?.message ?? String(e)));
    } finally { setCommenting(false); }
  }

  const chartData = (data?.departments ?? []).map((d) => ({
    city: d.city, base_2019: d.base_2019, base_2025: d.base_2025,
    vac: d.vacancy_rate != null ? Math.round(d.vacancy_rate * 100) : 0,
  }));

  return (
    <>
      <div className="card">
        <h2>Σύγκριση ομοειδών τμημάτων</h2>
        <p className="muted">
          Επίλεξε ένα πρόγραμμα (π.χ. Φιλολογίας) και δες όλα τα ομώνυμα τμήματα σε
          διαφορετικές πόλεις: βάση πριν/μετά την ΕΒΕ, κενές θέσεις και πρόβλεψη 2026.
          Η σύγκριση είναι «όμοιο με όμοιο» — το ίδιο πτυχίο, διαφορετική πόλη.
        </p>
        {fams.loading && <Loading />}
        {fams.error && <ErrorBox error={fams.error} />}
        {fams.data && (
          <select value={family} onChange={(e) => load(e.target.value)}
                  style={{ minWidth: 320, padding: 6 }}>
            <option value="">— επίλεξε πρόγραμμα ({fams.data.n} διαθέσιμα) —</option>
            {fams.data.families.map((f: FamilyItem) => (
              <option key={f.family} value={f.family}>
                {f.family} ({f.n_departments})
              </option>
            ))}
          </select>
        )}
      </div>

      {loading && <Loading />}
      {err && <ErrorBox error={err} />}

      {data && (
        <>
          <div className="card">
            <h3>{data.summary.family}</h3>
            <div className="muted" style={{ marginBottom: 10 }}>
              {data.summary.n_departments} τμήματα · {fmtInt(data.summary.total_seats)} θέσεις ·{" "}
              {fmtInt(data.summary.total_vacancies)} κενές
              {data.summary.vacancy_rate != null && ` (${fmtPct(data.summary.vacancy_rate)})`} ·
              περισσότερες κενές: <b>{data.summary.worst}</b> · λιγότερες: <b>{data.summary.best}</b>
            </div>
            <div style={{ width: "100%", height: 300 }}>
              <ResponsiveContainer>
                <BarChart data={chartData} margin={{ top: 10, right: 20, bottom: 5, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="city" fontSize={11} />
                  <YAxis yAxisId="l" fontSize={11} />
                  <YAxis yAxisId="r" orientation="right" fontSize={11} />
                  <Tooltip />
                  <Legend />
                  <Bar yAxisId="l" dataKey="base_2019" name="Βάση 2019 (προ-ΕΒΕ)" fill="#7fa8d0" />
                  <Bar yAxisId="l" dataKey="base_2025" name="Βάση 2025" fill="#1f5fa8" />
                  <Bar yAxisId="r" dataKey="vac" name="% κενές 2025" fill="#c0392b" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="card">
            <table>
              <thead>
                <tr>
                  <th>Πόλη</th><th>Πεδίο</th><th>Βάση 2019</th><th>Βάση 2025</th>
                  <th>Εισ./Θέσεις</th><th>% κενές</th><th>Πρόβλεψη 2026 (80% ΔΕ)</th>
                </tr>
              </thead>
              <tbody>
                {data.departments.map((d) => (
                  <tr key={d.dept_code}>
                    <td>{d.city}</td>
                    <td>{d.field ?? "—"}</td>
                    <td>{d.base_2019 != null ? fmtMoria(d.base_2019) : "—"}</td>
                    <td>{d.base_2025 != null ? fmtMoria(d.base_2025) : "—"}</td>
                    <td>{fmtInt(d.admitted)}/{fmtInt(d.seats)}</td>
                    <td style={{ color: d.vacancy_rate && d.vacancy_rate > 0.25 ? "#c0392b" : undefined }}>
                      {d.vacancy_rate != null ? fmtPct(d.vacancy_rate) : "—"}
                    </td>
                    <td>{d.forecast_2026 != null
                      ? `${fmtMoria(d.forecast_2026)} [${fmtMoria(d.forecast_2026_lo80!)}–${fmtMoria(d.forecast_2026_hi80!)}]`
                      : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="card">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
              <h3 style={{ margin: 0 }}>Ανάλυση μοτίβου με LLM</h3>
              <button onClick={analyse} disabled={commenting}>
                {commenting ? "Ανάλυση…" : "Σχολίασε τη σύγκριση"}
              </button>
            </div>
            <p className="muted small">
              Ο σχολιασμός βασίζεται αποκλειστικά στα παραπάνω στοιχεία της βάσης· κάθε
              αριθμός επαληθεύεται πριν εμφανιστεί.
            </p>
            <LlmKeyPanel />
            {commentErr && <div className="disclaimer">{commentErr}</div>}
            {comment && (
              <div>
                <Markdown>{comment.answer}</Markdown>
                <div className="muted small" style={{ marginTop: 8 }}>
                  {comment.used_llm
                    ? `Παράχθηκε με LLM (επαληθευμένο: ${comment.llm_verified ? "ναι" : "όχι"}) · ${comment.n_facts} τεκμηριωμένα στοιχεία`
                    : `Ντετερμινιστικό πρότυπο (χωρίς LLM) · ${comment.n_facts} στοιχεία`}
                </div>
                <div className="disclaimer" style={{ marginTop: 8 }}>{comment.disclaimer}</div>
              </div>
            )}
          </div>
        </>
      )}
    </>
  );
}
