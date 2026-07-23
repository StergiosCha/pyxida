import { useEffect, useState } from "react";

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    fn()
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(String(e)))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error, loading };
}

export function Loading({ label = "Φόρτωση…" }: { label?: string }) {
  return <div className="loading">{label}</div>;
}

export function ErrorBox({ error }: { error: string }) {
  return (
    <div className="card" style={{ borderColor: "#f0c0c0", background: "#fdf2f2" }}>
      <strong>Σφάλμα:</strong> <span className="small">{error}</span>
    </div>
  );
}
