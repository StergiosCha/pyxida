import { useState } from "react";
import { api, AdvisorResp, Meta } from "../lib/api";
import { useAsync, ErrorBox } from "../lib/hooks";
import Markdown from "../lib/Markdown";
import LlmKeyPanel from "../lib/LlmKeyPanel";
import { getLlmCreds } from "../lib/llmKey";

// The advisor is feature-flagged server-side (PYXIDA_ENABLE_RAG). When the flag
// is off the endpoint returns 503; we surface that as an informational notice
// rather than an error, since it's an intended state for the MVP.
export default function Advisor() {
  const { data: meta } = useAsync<Meta>(() => api.meta(), []);
  const [intent, setIntent] = useState("department");
  const [dept, setDept] = useState("");
  const [question, setQuestion] = useState("");
  const [field, setField] = useState("3ο");
  const [grades, setGrades] = useState<Record<string, string>>({});
  const [resp, setResp] = useState<AdvisorResp | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [disabled, setDisabled] = useState(false);
  const [busy, setBusy] = useState(false);

  const ragOn = meta?.features?.rag ?? false;

  async function ask() {
    setBusy(true); setErr(null); setResp(null); setDisabled(false);
    try {
      const body: Record<string, unknown> = { intent, question };
      if (intent === "department") body.dept = dept;
      if (intent === "eligibility") {
        body.field_id = field;
        body.grades = Object.fromEntries(
          Object.entries(grades).filter(([, v]) => v !== "").map(([k, v]) => [k, Number(v)]));
      }
      setResp(await api.advisor({ ...body, ...getLlmCreds() }));
    } catch (e) {
      const msg = String(e);
      if (msg.includes("503")) setDisabled(true);
      else setErr(msg);
    } finally { setBusy(false); }
  }

  return (
    <>
      <div className="card">
        <h2>Σύμβουλος (RAG) <span className="badge ebe">πειραματικό</span></h2>
        <p className="muted small">
          Ο σύμβουλος απαντά <strong>μόνο</strong> από τα επίσημα δεδομένα της εφαρμογής και την
          έκθεση — ποτέ δεν εφευρίσκει βάσεις ή ΕΒΕ. Κάθε αριθμός συνοδεύεται από πηγή και έτος.
          {!ragOn && <> Η λειτουργία είναι <strong>ανενεργή</strong> σε αυτή την εγκατάσταση
            (feature flag <code>PYXIDA_ENABLE_RAG</code>).</>}
        </p>
        <LlmKeyPanel />
        <div className="grid" style={{ gridTemplateColumns: "1fr 2fr", alignItems: "end" }}>
          <div className="field"><label>Τύπος ερώτησης</label>
            <select value={intent} onChange={(e) => setIntent(e.target.value)}>
              <option value="department">Τμήμα (βάσεις/ΕΒΕ/πρόβλεψη)</option>
              <option value="eligibility">Επιλεξιμότητα με βαθμούς</option>
              <option value="vacancies">Κενές θέσεις</option>
              <option value="nppe">Μη κρατικά (ΝΠΠΕ)</option>
            </select></div>
          {intent === "department" && (
            <div className="field"><label>Τμήμα (όνομα ή κωδικός)</label>
              <input type="text" value={dept} placeholder="π.χ. 295 ή Ιατρικής" onChange={(e) => setDept(e.target.value)} /></div>
          )}
          {intent === "eligibility" && (
            <div className="field"><label>Πεδίο</label>
              <select value={field} onChange={(e) => setField(e.target.value)}>
                {(meta?.fields ?? []).map((f) => <option key={f.id} value={f.id}>{f.id}</option>)}
              </select></div>
          )}
        </div>
        {intent === "eligibility" && (
          <div className="grid cols-4">
            {["NG", "MATH", "PHYS", "CHEM", "BIO", "ANC", "HIST", "LAT", "ECON", "AOTH"].map((s) => (
              <div className="field" key={s}><label>{s}</label>
                <input type="number" min={0} max={20} step={0.1} value={grades[s] ?? ""}
                  onChange={(e) => setGrades((g) => ({ ...g, [s]: e.target.value }))} /></div>
            ))}
          </div>
        )}
        <div className="field"><label>Η ερώτησή σας</label>
          <input type="text" value={question} placeholder="Γράψτε την ερώτηση…"
            onChange={(e) => setQuestion(e.target.value)} onKeyDown={(e) => e.key === "Enter" && ask()} /></div>
        <button className="btn" disabled={busy} onClick={ask}>{busy ? "Αναζήτηση…" : "Ρώτησε τον σύμβουλο"}</button>
      </div>

      {disabled && (
        <div className="disclaimer">
          Ο σύμβουλος είναι απενεργοποιημένος σε αυτή την εγκατάσταση. Ενεργοποιήστε τον θέτοντας
          <code> PYXIDA_ENABLE_RAG=1</code> στο backend. Οι υπόλοιπες λειτουργίες (αναζήτηση,
          στατιστικά, υπολογιστής) δουλεύουν κανονικά.
        </div>
      )}
      {err && <ErrorBox error={err} />}
      {resp && (
        <>
          <div className="card">
            <Markdown>{resp.answer}</Markdown>
          </div>
          <div className="card">
            <h3>Πηγές ({resp.n_facts}) {resp.used_llm ? "" : <span className="muted small">· ντετερμινιστική σύνθεση</span>}</h3>
            <ul className="small">
              {resp.citations.map((c, i) => (
                <li key={i}>{c.text} <span className="provenance">[{c.source}{c.year ? `, ${c.year}` : ""}]</span></li>
              ))}
            </ul>
          </div>
          <div className="disclaimer">{resp.disclaimer}</div>
        </>
      )}
    </>
  );
}
