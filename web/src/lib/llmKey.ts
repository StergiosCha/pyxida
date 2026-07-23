// Per-user LLM credentials, held only in the browser (localStorage).
// The key is sent in the POST body of /advisor requests so a hosted deployment
// can run with NO server-side key — each visitor brings their own. It is never
// stored server-side and never logged. Clearing it here removes it from the
// browser entirely.

const KKEY = "pyxida_llm_key";
const KBACKEND = "pyxida_llm_backend";
const KMODEL = "pyxida_llm_model";

export interface LlmCreds {
  llm_key?: string;
  llm_backend?: string;
  llm_model?: string;
}

export function getLlmCreds(): LlmCreds {
  const key = localStorage.getItem(KKEY) || "";
  if (!key) return {};
  return {
    llm_key: key,
    llm_backend: localStorage.getItem(KBACKEND) || "openrouter",
    llm_model: localStorage.getItem(KMODEL) || undefined,
  };
}

export function setLlmCreds(c: LlmCreds) {
  if (c.llm_key) localStorage.setItem(KKEY, c.llm_key.trim());
  else localStorage.removeItem(KKEY);
  if (c.llm_backend) localStorage.setItem(KBACKEND, c.llm_backend);
  if (c.llm_model) localStorage.setItem(KMODEL, c.llm_model);
  else localStorage.removeItem(KMODEL);
}

export function hasLlmKey(): boolean {
  return !!localStorage.getItem(KKEY);
}

export function clearLlmKey() {
  localStorage.removeItem(KKEY);
  localStorage.removeItem(KBACKEND);
  localStorage.removeItem(KMODEL);
}
