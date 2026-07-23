import { useState } from "react";
import { getLlmCreds, setLlmCreds, clearLlmKey, hasLlmKey } from "./llmKey";

// Small collapsible panel that lets the user paste their own LLM API key.
// Stored only in this browser (localStorage). Powers the σύμβουλος + LLM
// commentary when the server has no key of its own.
export default function LlmKeyPanel({ onChange }: { onChange?: () => void }) {
  const cur = getLlmCreds();
  const [open, setOpen] = useState(!hasLlmKey());
  const [key, setKey] = useState(cur.llm_key || "");
  const [backend, setBackend] = useState(cur.llm_backend || "openrouter");
  const [model, setModel] = useState(cur.llm_model || "");
  const [saved, setSaved] = useState(false);

  const save = () => {
    setLlmCreds({ llm_key: key, llm_backend: backend, llm_model: model || undefined });
    setSaved(true);
    setTimeout(() => setSaved(false), 1800);
    if (onChange) onChange();
  };
  const clear = () => {
    clearLlmKey();
    setKey(""); setModel("");
    if (onChange) onChange();
  };

  const placeholder =
    backend === "openrouter" ? "sk-or-v1-..."
    : backend === "anthropic" ? "sk-ant-..."
    : "sk-...";

  return (
    <div className="llm-key-panel">
      <button className="llm-key-toggle" onClick={() => setOpen(!open)}>
        <span className={hasLlmKey() ? "dot on" : "dot off"} />
        {hasLlmKey() ? "Κλειδί API: ενεργό" : "Προσθήκη κλειδιού API (για τον σύμβουλο)"}
        <span className="chev">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="llm-key-body">
          <p className="llm-key-note">
            Ο σύμβουλος και τα σχόλια LLM χρειάζονται ένα κλειδί API. Δώστε το δικό
            σας — αποθηκεύεται <b>μόνο σε αυτόν τον browser</b> (localStorage), δεν
            αποστέλλεται πουθενά εκτός από την υπηρεσία που επιλέγετε, και δεν
            καταγράφεται στον server.
          </p>
          <div className="llm-key-row">
            <label>Πάροχος</label>
            <select value={backend} onChange={(e) => setBackend(e.target.value)}>
              <option value="openrouter">OpenRouter (Claude Sonnet 4.6)</option>
              <option value="anthropic">Anthropic (απευθείας)</option>
              <option value="openai">OpenAI</option>
            </select>
          </div>
          <div className="llm-key-row">
            <label>Κλειδί</label>
            <input type="password" value={key} placeholder={placeholder}
                   onChange={(e) => setKey(e.target.value)} autoComplete="off" />
          </div>
          <div className="llm-key-row">
            <label>Μοντέλο <span className="opt">(προαιρετικό)</span></label>
            <input type="text" value={model}
                   placeholder={backend === "openrouter" ? "anthropic/claude-sonnet-4.6" : "προεπιλογή"}
                   onChange={(e) => setModel(e.target.value)} autoComplete="off" />
          </div>
          <div className="llm-key-actions">
            <button className="btn-primary" onClick={save} disabled={!key.trim()}>
              {saved ? "Αποθηκεύτηκε ✓" : "Αποθήκευση"}
            </button>
            {hasLlmKey() && (
              <button className="btn-ghost" onClick={clear}>Διαγραφή κλειδιού</button>
            )}
            <a className="llm-key-link" href="https://openrouter.ai/keys"
               target="_blank" rel="noreferrer">Πάρτε κλειδί OpenRouter →</a>
          </div>
        </div>
      )}
    </div>
  );
}
