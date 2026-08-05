import { useEffect, useState } from "react";
import { api, Alert, Media, SeriesResp, Indicator, Police, GovResp, DossierResp, AssessResp, EntitySummary, EntityDetail, EuResp, FlowResp, CompResp, BAResp, ImpResp, NetResp } from "./lib/api";
import Markdown from "./lib/Markdown";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, Area, ComposedChart, ReferenceLine, Legend,
} from "recharts";

function Src({ url, text }: { url: string; text: string }) {
  return <div className="src">Πηγή: <a href={url} target="_blank" rel="noreferrer">{text}</a></div>;
}

const TABS = [
  { id: "overview", label: "Επισκόπηση" },
  { id: "indicators", label: "Δείκτες" },
  { id: "governance", label: "Διακυβέρνηση" },
  { id: "dossier", label: "Φάκελος λογοδοσίας" },
  { id: "entities", label: "Πρόσωπα" },
  { id: "accountability", label: "Λογοδοσία & δίκτυο" },
  { id: "timeline", label: "Χρονολόγιο" },
  { id: "media", label: "ΜΜΕ & Αστυνομική βία" },
  { id: "data", label: "Δεδομένα & Εξαγωγή" },
] as const;
type TabId = typeof TABS[number]["id"];

// ---- Panel 1: press freedom (RSF rank) ----
function PressFreedom() {
  const [d, setD] = useState<SeriesResp | null>(null);
  useEffect(() => { api.series("Press Freedom rank").then(setD).catch(() => {}); }, []);
  if (!d) return null;
  const data = d.series.map(p => ({ year: p.year, rank: p.rank }));
  return (
    <div className="card">
      <h2>Ελευθερία Τύπου — κατάταξη RSF</h2>
      <p className="sub">Παγκόσμια κατάταξη (από 180). Χαμηλότερη θέση = χειρότερα. Η Ελλάδα ήταν <b>τελευταία στην ΕΕ</b> και τις 4 χρονιές.</p>
      <div className="kpi-row">
        {d.series.map(p => (
          <div className="kpi" key={p.year}>
            <div className="v">{p.rank}η</div>
            <div className="l">{p.year} · {p.note || ""}</div>
          </div>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 10, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="year" /><YAxis reversed domain={[80, 115]} />
          <Tooltip /><Line type="monotone" dataKey="rank" stroke="#c0392b" strokeWidth={2.5} dot={{ r: 5 }} />
        </LineChart>
      </ResponsiveContainer>
      <Src url={d.source.url} text={d.source.name} />
    </div>
  );
}

// ---- Panel 2: democracy vs corruption ----
function DemocracyContrast() {
  const [lib, setLib] = useState<SeriesResp | null>(null);
  const [cpi, setCpi] = useState<SeriesResp | null>(null);
  useEffect(() => {
    api.series("Liberal Democracy Index").then(setLib).catch(() => {});
    api.series("Corruption Perceptions Index").then(setCpi).catch(() => {});
  }, []);
  if (!lib || !cpi) return null;
  const byYear: Record<number, any> = {};
  lib.series.filter(p => p.year >= 2013).forEach(p => { byYear[p.year] = { year: p.year, lib: p.value ? p.value * 100 : null }; });
  cpi.series.filter(p => p.year >= 2013).forEach(p => { byYear[p.year] = { ...(byYear[p.year] || { year: p.year }), cpi: p.value }; });
  const data = Object.values(byYear).sort((a: any, b: any) => a.year - b.year);
  return (
    <div className="card">
      <h2>Η τίμια εικόνα: δημοκρατία vs διαφθορά</h2>
      <p className="sub">Ο δείκτης φιλελεύθερης δημοκρατίας (V-Dem) υποχωρεί απότομα· η αντίληψη διαφθοράς (CPI) μένει σταθερή. Σημείωση: οι δείκτες δεν συμφωνούν — RSF και V-Dem δείχνουν έντονη επιδείνωση, το Freedom House ήπια πτώση (88→85), ενώ ο δείκτης EIU βελτίωση (7,43→8,07). Δείχνουμε και τα δύο· αυτό κάνει την εικόνα αξιόπιστη.</p>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 10, right: 30, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="year" /><YAxis domain={[30, 100]} />
          <Tooltip /><ReferenceLine x={2019} stroke="#999" strokeDasharray="2 2" />
          <Line type="monotone" dataKey="lib" name="V-Dem Φιλελ. Δημοκρατία (×100)" stroke="#c0392b" strokeWidth={2.5} dot={false} />
          <Line type="monotone" dataKey="cpi" name="Διαφθορά CPI (ψηλότερα=καθαρότερα)" stroke="#2c7c4a" strokeWidth={2.5} strokeDasharray="6 4" dot={false} />
        </LineChart>
      </ResponsiveContainer>
      <Src url="https://v-dem.net" text="V-Dem Institute · Transparency International CPI" />
    </div>
  );
}

// ---- Panel 3: alerts timeline ----
function Alerts() {
  const [a, setA] = useState<Alert[]>([]);
  useEffect(() => { api.alerts().then(setA).catch(() => {}); }, []);
  return (
    <div className="card">
      <h2>Κράτος Δικαίου & Παρακολουθήσεις — χρονολόγιο</h2>
      <p className="sub">Τεκμηριωμένα περιστατικά, το καθένα με σύνδεσμο πηγής.</p>
      {a.map((x, i) => (
        <div className="alert" key={i}>
          <div className="d">{x.date} · {x.type}
            <span className={"tag " + (x.is_verified ? "verified" : "unofficial")}>{x.is_verified ? "επαληθευμένο" : "προς επαλήθευση"}</span>
          </div>
          <div className="t">{x.title_el}</div>
          <div className="desc">{x.description}</div>
          <div className="src"><a href={x.source_url} target="_blank" rel="noreferrer">πηγή →</a></div>
        </div>
      ))}
    </div>
  );
}

// ---- Panel 4: media ownership ----
function MediaOwnership() {
  const [m, setM] = useState<Media[]>([]);
  useEffect(() => { api.media().then(setM).catch(() => {}); }, []);
  return (
    <div className="card">
      <h2>Ιδιοκτησία ΜΜΕ — διασταυρούμενα συμφέροντα
        <span className="tag unofficial">μη επίσημα στοιχεία</span></h2>
      <p className="sub">Ποιος ελέγχει κάθε μέσο και ποια είναι τα κύρια επιχειρηματικά του συμφέροντα εκτός ΜΜΕ. Στοιχεία παρακολουθητών/τύπου — όχι επίσημο μητρώο.</p>
      <table>
        <thead><tr><th>Μέσο</th><th>Ιδιοκτήτης</th><th>Συμφέροντα εκτός ΜΜΕ</th><th>Πηγή</th></tr></thead>
        <tbody>
          {m.map((x, i) => (
            <tr key={i}>
              <td>{x.outlet}</td><td>{x.owner}</td><td>{x.owner_interests}</td>
              <td><a href={x.source_url} target="_blank" rel="noreferrer">→</a></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---- Panel 5: police violence & civil liberties ----
const PV_LABEL: Record<string, string> = {
  ecthr_judgment: "Απόφαση ΕΔΔΑ", ombudsman_report: "Έκθεση Συνηγόρου",
  ngo_report: "Έκθεση ΜΚΟ", individual_case: "Μεμονωμένη υπόθεση",
  protest_policing: "Αστυνόμευση διαδηλώσεων", cpt_report: "Έκθεση CPT",
};
function PoliceViolence() {
  const [p, setP] = useState<Police[]>([]);
  useEffect(() => { api.police().then(setP).catch(() => {}); }, []);
  if (!p.length) return null;
  return (
    <div className="card">
      <h2>Αστυνομική βία & ατομικές ελευθερίες</h2>
      <p className="sub">Αποφάσεις δικαστηρίων, εκθέσεις εποπτικών οργάνων και τεκμηριωμένες υποθέσεις. Μόνο γεγονότα και νομικές εκβάσεις — χωρίς χαρακτηρισμούς.</p>
      {p.map((x, i) => (
        <div className="alert" key={i}>
          <div className="d">{x.date} · {PV_LABEL[x.category] || x.category}
            {x.body_or_court ? " · " + x.body_or_court : ""}</div>
          <div className="t">{x.title_en}</div>
          <div className="desc">{x.description}</div>
          {x.outcome ? <div className="desc"><b>Έκβαση:</b> {x.outcome}</div> : null}
          <div className="src"><a href={x.source_url} target="_blank" rel="noreferrer">πηγή →</a></div>
        </div>
      ))}
    </div>
  );
}

// ---- Overview: headline KPIs ----
function EuComparison() {
  const [d, setD] = useState<EuResp | null>(null);
  useEffect(() => { api.euComparison().then(setD).catch(() => {}); }, []);
  if (!d || !d.available || !d.rows.length) return null;
  return (
    <div className="card">
      <h2>Ελλάδα vs Ευρωπαϊκή Ένωση (27)</h2>
      <p className="sub">Θέση της Ελλάδας ανάμεσα στα 27 κράτη-μέλη σε δείκτες δημοκρατίας, Τύπου και
        διαφθοράς. Υψηλότερο = καλύτερο· η κατάταξη υπολογίστηκε πάνω στο σύνολο ΕΕ-27 από τις ίδιες
        σειρές OWID που συνδέει κάθε γραμμή.</p>
      <div className="euc-list">
        {d.rows.map((r, i) => {
          const span = r.eu_best - r.eu_worst || 1;
          const pct = (v: number) => Math.max(0, Math.min(100, ((v - r.eu_worst) / span) * 100));
          const bottomThird = r.eu_rank > (2 * r.eu_total) / 3;
          return (
            <div className="euc-row" key={i}>
              <div className="euc-head">
                <b>{r.label}</b>
                <span className={"euc-rank " + (bottomThird ? "euc-bad" : "euc-mid")}>
                  {r.eu_rank}<span className="euc-of">/{r.eu_total} στην ΕΕ</span>
                </span>
              </div>
              <div className="euc-bar">
                <div className="euc-track" />
                <div className="euc-median" style={{ left: pct(r.eu_median) + "%" }} title={"Διάμεσος ΕΕ: " + r.eu_median} />
                <div className={"euc-gr " + (bottomThird ? "euc-gr-bad" : "")} style={{ left: pct(r.greece) + "%" }} title={"Ελλάδα: " + r.greece} />
              </div>
              <div className="euc-legend">
                <span>χειρότερη ΕΕ {r.eu_worst}</span>
                <span className="euc-gr-lab">▲ Ελλάδα {r.greece} ({r.year})</span>
                <span>καλύτερη ΕΕ {r.eu_best}</span>
              </div>
              <div className="src">Διάμεσος ΕΕ {r.eu_median} · <a href={r.source_url} target="_blank" rel="noreferrer">πηγή (OWID) →</a></div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Overview({ inds }: { inds: Indicator[] }) {
  const pick = (name: string) => inds.find(i => i.indicator === name);
  const cards = [
    { k: "Ελευθ. Τύπου — σκορ (RSF)", ind: pick("World Press Freedom Index - Overall"),
      fmt: (v: number) => v.toFixed(1), note: "τελευταία στην ΕΕ", bad: true },
    { k: "Φιλελεύθερη Δημοκρατία (V-Dem)", ind: pick("Liberal Democracy Index"),
      fmt: (v: number) => v.toFixed(3), note: "0,76 (2019) → πτώση", bad: true },
    { k: "Δείκτης Δημοκρατίας (EIU)", ind: pick("Democracy Index - Overall Score"),
      fmt: (v: number) => v.toFixed(2), note: "άνοδος 7,43→8,07", bad: false },
    { k: "Έλεγχος Διαφθοράς (WB)", ind: pick("Control of Corruption"),
      fmt: (v: number) => `${v.toFixed(0)}ο εκ.`, note: "σταθερός", bad: false },
    { k: "Freedom House (σύνολο)", ind: pick("Freedom in the World - Total Score"),
      fmt: (v: number) => `${v}/100`, note: "ήπια πτώση 88→85", bad: true },
    { k: "Ελευθερία Έκφρασης (V-Dem)", ind: pick("Freedom of Expression Index"),
      fmt: (v: number) => v.toFixed(3), note: "πτωτική", bad: true },
  ];
  return (
    <>
      <div className="card">
        <h2>Η εικόνα με μια ματιά</h2>
        <p className="sub">Τελευταία διαθέσιμη τιμή ανά δείκτη. Οι δείκτες <b>δεν συμφωνούν όλοι</b>:
          η ελευθερία Τύπου και η φιλελεύθερη δημοκρατία δείχνουν σαφή επιδείνωση, ο δείκτης EIU
          βελτίωση, η διαφθορά σταθερότητα. Αυτή η διαφωνία είναι μέρος της τίμιας εικόνας.</p>
        <div className="kpi-grid">
          {cards.map((c, i) => c.ind && (
            <div className={"kpi-card " + (c.bad ? "kpi-bad" : "kpi-neutral")} key={i}>
              <div className="kpi-k">{c.k}</div>
              <div className="kpi-v">{c.ind.latest_value != null ? c.fmt(c.ind.latest_value) : "—"}</div>
              <div className="kpi-note">{c.ind.latest_year} · {c.note}</div>
            </div>
          ))}
        </div>
      </div>
      <EuComparison />
      <CompositeIndex />
      <BeforeAfter />
      <PressFreedom />
      <DemocracyContrast />
    </>
  );
}

// ---- Indicators explorer: pick any of the 21 series ----
function IndicatorsExplorer({ inds }: { inds: Indicator[] }) {
  const [sel, setSel] = useState<string>("Liberal Democracy Index");
  const [d, setD] = useState<SeriesResp | null>(null);
  useEffect(() => { setD(null); api.series(sel).then(setD).catch(() => {}); }, [sel]);
  const data = (d?.series ?? []).filter(p => p.value != null || p.rank != null)
    .map(p => ({ year: p.year, value: p.value, rank: p.rank }));
  const isRank = data.length > 0 && data.every(p => p.value == null);
  return (
    <div className="card">
      <h2>Εξερεύνηση δεικτών</h2>
      <p className="sub">Και οι {inds.length} δείκτες από όλες τις πηγές. Επίλεξε για να δεις τη χρονοσειρά.</p>
      <select className="picker" value={sel} onChange={e => setSel(e.target.value)}>
        {inds.map(i => (
          <option key={i.indicator + i.source_id} value={i.indicator}>
            {i.indicator} — {i.source_name} ({i.latest_year})
          </option>
        ))}
      </select>
      {!d && <p className="muted">Φόρτωση…</p>}
      {d && (
        <>
          <ResponsiveContainer width="100%" height={280}>
            <LineChart data={data} margin={{ top: 10, right: 20, bottom: 5, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
              <XAxis dataKey="year" />
              <YAxis reversed={isRank} domain={["auto", "auto"]} />
              <Tooltip />
              <Line type="monotone" dataKey={isRank ? "rank" : "value"}
                name={isRank ? "κατάταξη" : d.indicator}
                stroke="#c0392b" strokeWidth={2.5} dot={{ r: 3 }} connectNulls />
            </LineChart>
          </ResponsiveContainer>
          <p className="sub" style={{ marginTop: 6 }}>
            {d.series[0]?.unit} · {d.series.length} σημεία · {d.series[0]?.year}–{d.series[d.series.length - 1]?.year}
          </p>
          {d.source && <Src url={d.source.url} text={d.source.name} />}
          {d.source?.methodology_url && (
            <div className="src">Μεθοδολογία: <a href={d.source.methodology_url} target="_blank" rel="noreferrer">→</a></div>
          )}
        </>
      )}
    </div>
  );
}

// ---- Governance small-multiples (World Bank WGI, 4 series with CI) ----
function Governance() {
  const [g, setG] = useState<GovResp | null>(null);
  useEffect(() => { api.governance().then(setG).catch(() => {}); }, []);
  if (!g) return null;
  const LABELS: Record<string, string> = {
    "Voice and Accountability": "Φωνή & Λογοδοσία",
    "Rule of Law": "Κράτος Δικαίου",
    "Control of Corruption": "Έλεγχος Διαφθοράς",
    "Government Effectiveness": "Αποτελεσματικότητα Κυβέρνησης",
  };
  return (
    <div className="card">
      <h2>Δείκτες Διακυβέρνησης — World Bank (WGI)</h2>
      <p className="sub">Εκατοστημόρια (0–100) με 90% διάστημα εμπιστοσύνης. Υψηλότερα = καλύτερα.
        Ο κάθετος δείκτης στο 2019 σημειώνει την αλλαγή κυβέρνησης.</p>
      <div className="sm-grid">
        {g.indicators.map((ind) => {
          const rows = ind.points.filter(p => p.value != null && p.year >= 2010);
          return (
            <div className="sm" key={ind.indicator}>
              <div className="sm-title">{LABELS[ind.indicator] || ind.indicator}</div>
              <ResponsiveContainer width="100%" height={160}>
                <ComposedChart data={rows} margin={{ top: 6, right: 8, bottom: 0, left: -18 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="year" tick={{ fontSize: 10 }} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <ReferenceLine x={2019} stroke="#c0392b" strokeDasharray="3 2" />
                  <Area dataKey="hi" stroke="none" fill="#c0392b" fillOpacity={0.08} />
                  <Area dataKey="lo" stroke="none" fill="#fff" fillOpacity={1} />
                  <Line type="monotone" dataKey="value" stroke="#2c3e50" strokeWidth={2} dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          );
        })}
      </div>
      <Src url={g.indicators[0]?.source_url || "https://info.worldbank.org/governance/wgi/"}
        text="World Bank — Worldwide Governance Indicators" />
    </div>
  );
}

// ---- Data & export ----
function DataExport({ meta }: { meta: any }) {
  const tables = [
    { t: "indicators", label: "Όλοι οι δείκτες (630 σημεία)" },
    { t: "dossier", label: "Φάκελος λογοδοσίας (64 γραμμές)" },
    { t: "alerts", label: "Χρονολόγιο περιστατικών (12)" },
    { t: "police", label: "Αστυνομική βία / υποθέσεις (9)" },
    { t: "media", label: "Ιδιοκτησία ΜΜΕ (9)" },
    { t: "sources", label: "Κατάλογος πηγών (20)" },
  ];
  return (
    <div className="card">
      <h2>Δεδομένα & Εξαγωγή</h2>
      <p className="sub">Κατέβασε κάθε πίνακα ως CSV ή JSON. Κάθε γραμμή φέρει τη δική της πηγή (source_url) —
        η βάση απορρίπτει οποιαδήποτε εγγραφή χωρίς πηγή.</p>
      <table>
        <thead><tr><th>Πίνακας</th><th>CSV</th><th>JSON</th></tr></thead>
        <tbody>
          {tables.map(({ t, label }) => (
            <tr key={t}>
              <td>{label}</td>
              <td><a href={api.exportUrl(t, "csv")} download>⬇ CSV</a></td>
              <td><a href={api.exportUrl(t, "json")} target="_blank" rel="noreferrer">JSON</a></td>
            </tr>
          ))}
        </tbody>
      </table>
      {meta && (
        <p className="sub" style={{ marginTop: 10 }}>
          Σύνολο: {meta.n_indicator_rows} σημεία δείκτη · {meta.sources?.length} πηγές ·
          έτη {meta.year_range?.mn}–{meta.year_range?.mx}. Όλες οι πηγές συνδέονται με βαθιά (deep) links
          στα δεδομένα της Ελλάδας, όχι σε γενικές σελίδες.
        </p>
      )}
    </div>
  );
}

// ---- Accountability dossier (Fable sourced record) ----
const STATUS_EL: Record<string, { el: string; cls: string }> = {
  ESTABLISHED: { el: "Τεκμηριωμένο", cls: "st-established" },
  CONVICTED: { el: "Καταδίκη", cls: "st-convicted" },
  ALLEGED: { el: "Καταγγελλόμενο", cls: "st-alleged" },
  UNDER_INVESTIGATION: { el: "Υπό διερεύνηση", cls: "st-inv" },
  UNVERIFIED: { el: "Ανεπιβεβαίωτο", cls: "st-unver" },
};
function Assessor({ section, entity }: { section?: string | null; entity?: string | null }) {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<AssessResp | null>(null);
  const [err, setErr] = useState<string | null>(null);
  function run() {
    setBusy(true); setErr(null);
    api.assessment({ section, entity }).then(setRes).catch(e => setErr(String(e))).finally(() => setBusy(false));
  }
  return (
    <div className="assessor">
      <button className="assess-btn" onClick={run} disabled={busy}>
        {busy ? "Αξιολόγηση…" : "🇪🇺 Σχολιασμός από Ευρωπαίο αξιολογητή κράτους δικαίου"}
      </button>
      {err && <div className="assess-err">Σφάλμα: {err}</div>}
      {res && (
        <div className="assess-out">
          <div className="assess-tags">
            <span className={"badge sm " + (res.grounded ? "st-established" : "st-alleged")}>
              {res.grounded ? "τεκμηριωμένο (grounded)" : "μη τεκμηριωμένο — απορρίφθηκε"}
            </span>
            <span className="badge sm st-unver">
              {res.used_llm ? "LLM: " + res.backend : "πρότυπο (χωρίς LLM)"}
            </span>
            <span className="assess-nfacts">{res.n_facts} τεκμηριωμένες πηγές</span>
          </div>
          <div className="assess-body"><Markdown>{res.assessment}</Markdown></div>
          {res.note && <div className="assess-note">{res.note}</div>}
          <div className="assess-disc">Ο σχολιασμός βασίζεται αποκλειστικά στις τεκμηριωμένες
            γραμμές της βάσης· ένας έλεγχος τεκμηρίωσης απορρίπτει κάθε ημερομηνία που δεν υπάρχει
            στις πηγές. Αναφέρει το μητρώο — δεν εκδίδει ετυμηγορία.</div>
        </div>
      )}
    </div>
  );
}

function CompositeIndex() {
  const [d, setD] = useState<CompResp | null>(null);
  useEffect(() => { api.compositeIndex().then(setD).catch(() => {}); }, []);
  if (!d) return null;
  return (
    <div className="card">
      <h2>Σύνθετος δείκτης «Κατάσταση Δημοκρατίας»</h2>
      <p className="sub">{d.note}</p>
      <div className="derived-flag">⚠ Παράγωγος δείκτης — όχι επίσημη μέτρηση. Κάθε συνιστώσα φαίνεται ξεχωριστά παρακάτω.</div>
      <ResponsiveContainer width="100%" height={280}>
        <ComposedChart data={d.composite} margin={{ top: 10, right: 20, bottom: 5, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="year" fontSize={12} />
          <YAxis fontSize={12} label={{ value: "z-score", angle: -90, position: "insideLeft", fontSize: 12 }} />
          <Tooltip formatter={(v: number) => v.toFixed(2)} />
          <ReferenceLine y={0} stroke="#999" />
          <ReferenceLine x={d.reference_year} stroke="#b3261e" strokeDasharray="4 2"
            label={{ value: "αλλαγή κυβέρνησης 2019", fontSize: 11, fill: "#b3261e", position: "top" }} />
          <Area type="monotone" dataKey="z" name="σύνθετος (ίσα βάρη)" stroke="#0d3b66" fill="#0d3b66" fillOpacity={0.12} strokeWidth={2.5} />
        </ComposedChart>
      </ResponsiveContainer>
      <div className="comp-legend">
        {d.components.map((c) => {
          const first = c.points[0], last = c.points[c.points.length - 1];
          const dz = last.z - first.z;
          return (
            <div className="comp-item" key={c.indicator}>
              <span className="comp-name">{c.label}</span>
              <span className={"comp-delta " + (dz < 0 ? "neg" : "pos")}>
                {dz >= 0 ? "▲" : "▼"} {dz.toFixed(2)}σ <span className="muted">({first.year}→{last.year})</span>
              </span>
              <a href={c.source_url} target="_blank" rel="noreferrer" className="comp-src">πηγή →</a>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function BeforeAfter() {
  const [d, setD] = useState<BAResp | null>(null);
  useEffect(() => { api.beforeAfter().then(setD).catch(() => {}); }, []);
  if (!d) return null;
  return (
    <div className="card">
      <h2>Πριν / Μετά το {d.split_year}</h2>
      <p className="sub">Κάθε δείκτης στην τελευταία τιμή πριν το {d.split_year} vs την πιο πρόσφατη.
        Απλή τομή τεκμηριωμένων σειρών κατά ημερομηνία· η αριθμητική είναι ουδέτερη.</p>
      <div className="ba-list">
        {d.rows.map((r) => (
          <div className="ba-row" key={r.indicator}>
            <span className="ba-name">{r.indicator}</span>
            <span className="ba-vals">{r.before} <span className="muted">({r.before_year})</span> →
              <b> {r.after}</b> <span className="muted">({r.after_year})</span></span>
            <span className={"ba-delta " + (r.improved === false ? "neg" : r.improved ? "pos" : "")}>
              {r.improved === false ? "▼ επιδείνωση" : r.improved ? "▲ βελτίωση" : "→"}
            </span>
            <a href={r.source_url} target="_blank" rel="noreferrer" className="comp-src">πηγή →</a>
          </div>
        ))}
      </div>
    </div>
  );
}

function StateAdFlow() {
  const [d, setD] = useState<FlowResp | null>(null);
  useEffect(() => { api.stateAdFlow().then(setD).catch(() => {}); }, []);
  if (!d) return null;
  const owners = d.nodes.filter((n) => n.kind === "owner");
  const outletsOf = (oid: string) => d.links.filter((l) => l.source === oid).map((l) => d.nodes.find((n) => n.id === l.target)?.label);
  return (
    <div className="card">
      <h2>Ο κρατικός διαφημιστικός σωλήνας</h2>
      <p className="sub">{d.note}</p>
      <div className="flow-total">
        Κρατική διαφήμιση COVID-19 («{d.total_label}»):
        <b> €{d.total_eur?.toLocaleString("el-GR")}</b>
        {d.total_source && <a href={d.total_source} target="_blank" rel="noreferrer" className="comp-src"> πηγή →</a>}
      </div>
      <div className="flow-diagram">
        <div className="flow-gov">Κυβέρνηση</div>
        <div className="flow-arrow">→</div>
        <div className="flow-owners">
          {owners.map((o) => (
            <div className="flow-owner" key={o.id}>
              <b>{o.label}</b>
              {o.interests && <div className="flow-interests">{o.interests}</div>}
              <div className="flow-outlets">{outletsOf(o.id).filter(Boolean).join(" · ")}</div>
              {o.source_url && <a href={o.source_url} target="_blank" rel="noreferrer" className="comp-src">πηγή →</a>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

const IMP_EL: Record<string, { el: string; cls: string }> = {
  convicted: { el: "Καταδίκη", cls: "imp-conv" },
  acquitted: { el: "Αθώωση", cls: "imp-acq" },
  ongoing: { el: "Εκκρεμεί", cls: "imp-ong" },
  no_charges: { el: "Καμία δίωξη", cls: "imp-none" },
  unclear: { el: "Ασαφές", cls: "imp-unc" },
};

function daysSince(iso: string | null): number | null {
  if (!iso) return null;
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return null;
  const d0 = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return Math.floor((Date.now() - d0.getTime()) / 86400000);
}

function Impunity() {
  const [d, setD] = useState<ImpResp | null>(null);
  useEffect(() => { api.impunity().then(setD).catch(() => {}); }, []);
  if (!d) return null;
  const unresolved = d.cases
    .filter((c) => (c.outcome === "ongoing" || c.outcome === "no_charges") && c.date)
    .map((c) => ({ ...c, days: daysSince(c.date) }))
    .filter((c) => c.days != null)
    .sort((a, b) => (b.days || 0) - (a.days || 0));
  return (
    <div className="card">
      <h2>Δείκτης ατιμωρησίας</h2>
      <p className="sub">Έκβαση ανά υπόθεση: καταδίκη / αθώωση / εκκρεμότητα / καμία δίωξη, με τα
        έτη που πέρασαν. Από τις καταγραφές αστυνομικής βίας και τον φάκελο λογοδοσίας.</p>

      {unresolved.length > 0 && (
        <div className="imp-clock-wrap">
          <h3 className="imp-clock-title">Ρολόι ατιμωρησίας — υποθέσεις χωρίς οριστική έκβαση</h3>
          <div className="imp-clocks">
            {unresolved.map((c, i) => (
              <div className="imp-clock" key={i}>
                <div className="imp-clock-days">{c.days?.toLocaleString("el-GR")}</div>
                <div className="imp-clock-lbl">ημέρες</div>
                <div className="imp-clock-case">{c.case}</div>
                <a href={c.source_url} target="_blank" rel="noreferrer" className="comp-src">πηγή →</a>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="imp-counts">
        {Object.entries(d.counts).map(([k, v]) => (
          <span key={k} className={"imp-chip " + (IMP_EL[k]?.cls || "")}>{IMP_EL[k]?.el || k}: {v}</span>
        ))}
      </div>
      <div className="imp-list">
        {d.cases.map((c, i) => (
          <div className="imp-row" key={i}>
            <span className={"imp-badge " + (IMP_EL[c.outcome]?.cls || "")}>{IMP_EL[c.outcome]?.el || c.outcome}</span>
            <span className="imp-case">{c.case}</span>
            {c.years_elapsed != null && <span className="imp-years">{c.years_elapsed} έτη</span>}
            <a href={c.source_url} target="_blank" rel="noreferrer" className="comp-src">πηγή →</a>
          </div>
        ))}
      </div>
    </div>
  );
}

function NetworkGraph() {
  const [d, setD] = useState<NetResp | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  useEffect(() => { api.network().then(setD).catch(() => {}); }, []);
  if (!d) return null;
  const persons = d.nodes.filter((n) => n.kind === "person");
  const casesOf = (pid: string) => d.links.filter((l) => l.source === pid)
    .map((l) => d.nodes.find((n) => n.id === l.target)).filter(Boolean);
  return (
    <div className="card">
      <h2>Δίκτυο λογοδοσίας</h2>
      <p className="sub">{d.note} · {persons.length} πρόσωπα, {d.n_nodes} κόμβοι.
        Επίλεξε πρόσωπο για να δεις τις συνδεδεμένες υποθέσεις.</p>
      <div className="net-people">
        {persons.map((p) => (
          <button key={p.id} className={"net-person " + (sel === p.id ? "active" : "")}
            onClick={() => setSel(sel === p.id ? null : p.id)}>
            {p.label} <span className="net-n">{p.n}</span>
          </button>
        ))}
      </div>
      {sel && (
        <div className="net-cases">
          <h4>{persons.find((p) => p.id === sel)?.label} — συνδεδεμένες υποθέσεις</h4>
          {casesOf(sel).map((c, i) => c && (
            <div className="net-case" key={i}>
              <span className="net-dot" />
              <span>{c.label}</span>
              {c.source_url && <a href={c.source_url} target="_blank" rel="noreferrer" className="comp-src">πηγή →</a>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Accountability() {
  return (<><Impunity /><NetworkGraph /></>);
}

function StatusBadges({ counts }: { counts: Record<string, number> }) {
  return (
    <div className="badge-row">
      {Object.entries(counts).map(([k, v]) => (
        <span key={k} className={"badge sm " + (STATUS_EL[k]?.cls || "")}>{STATUS_EL[k]?.el || k}: {v}</span>
      ))}
    </div>
  );
}

function Entities() {
  const [list, setList] = useState<EntitySummary[] | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [detail, setDetail] = useState<EntityDetail | null>(null);
  useEffect(() => { api.entities().then(r => setList(r.entities)).catch(() => {}); }, []);
  useEffect(() => { if (sel) { setDetail(null); api.entity(sel).then(setDetail).catch(() => {}); } }, [sel]);
  if (!list) return <div className="card"><p className="muted">Φόρτωση…</p></div>;

  if (sel && detail) {
    return (
      <div className="card">
        <button className="back-btn" onClick={() => { setSel(null); setDetail(null); }}>← Όλα τα πρόσωπα</button>
        <h2>{detail.name}</h2>
        <p className="sub">{detail.role} · {detail.n} τεκμηριωμένες καταγραφές</p>
        <StatusBadges counts={detail.status_counts} />
        <Assessor entity={detail.id} />
        <div className="doss-body">
          {detail.rows.map((r, i) => (
            <div className="doss-row" key={i}>
              <div className="doss-row-top">
                <span className={"badge sm " + (STATUS_EL[r.status]?.cls || "")}>{STATUS_EL[r.status]?.el || r.status}</span>
                {r.date && <span className="doss-date">{r.date}</span>}
                <span className="doss-role">{r.section}</span>
              </div>
              <div className="doss-detail">{r.detail || r.title}</div>
              {r.response && <div className="doss-resp">Απάντηση: «{r.response}»</div>}
              <div className="src">{r.source_body && <span>{r.source_body} · </span>}
                <a href={r.source_url} target="_blank" rel="noreferrer">πηγή →</a></div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <h2>Πρόσωπα — δημόσιο μητρώο</h2>
      <p className="sub">Επίλεξε πρόσωπο για να δεις κάθε τεκμηριωμένη καταγραφή που το αφορά, με σχολιασμό
        από Ευρωπαίο αξιολογητή. Ισχύει το τεκμήριο αθωότητας για ό,τι δεν είναι τελεσίδικο.</p>
      <div className="entity-grid">
        {list.map(e => (
          <button className="entity-card" key={e.id} onClick={() => setSel(e.id)}>
            <b>{e.name}</b>
            <span className="entity-role">{e.role}</span>
            <StatusBadges counts={e.status_counts} />
            <span className="entity-n">{e.n} καταγραφές →</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function Dossier() {
  const [d, setD] = useState<DossierResp | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => { api.dossier().then(setD).catch(() => {}); }, []);
  if (!d) return <div className="card"><p className="muted">Φόρτωση…</p></div>;
  return (
    <div className="card">
      <h2>Φάκελος δημοκρατικής λογοδοσίας</h2>
      <p className="sub">Τεκμηριωμένο μητρώο — <b>όχι ετυμηγορία</b>. Κάθε γραμμή φέρει πηγή και ετικέτα
        κατάστασης· ισχύει το τεκμήριο αθωότητας για ό,τι δεν έχει τελεσίδικη καταδίκη.
        Πηγές: EPPO, ΣτΕ/ECtHR, Επιτροπή ΕΕ, DPA/ΑΔΑΕ, Ευρωκοινοβούλιο, δικαστήρια.</p>
      <div className="badge-row">
        {Object.entries(d.status_counts).map(([k, v]) => (
          <span key={k} className={"badge " + (STATUS_EL[k]?.cls || "")}>
            {STATUS_EL[k]?.el || k}: {v}
          </span>
        ))}
      </div>
      <Assessor section={null} />
      {d.sections.map(sec => (
        <div className="doss-sec" key={sec.section}>
          <button className="doss-head" onClick={() => setOpen(open === sec.section ? null : sec.section)}>
            <span>{open === sec.section ? "▾" : "▸"} {sec.section}</span>
            <span className="doss-count">{sec.rows.length}</span>
          </button>
          {open === sec.section && (
            <div className="doss-body">
              <Assessor section={sec.section} />
              {sec.rows.map((r, i) => (
                <div className="doss-row" key={i}>
                  <div className="doss-row-top">
                    <span className={"badge sm " + (STATUS_EL[r.status]?.cls || "")}>{STATUS_EL[r.status]?.el || r.status}</span>
                    {r.date && <span className="doss-date">{r.date}</span>}
                    {r.actor && <b className="doss-actor">{r.actor}</b>}
                    {r.role && <span className="doss-role">{r.role}</span>}
                  </div>
                  <div className="doss-detail">{r.detail || r.title}</div>
                  {r.response && <div className="doss-resp">Απάντηση: «{r.response}»</div>}
                  <div className="src">
                    {r.source_body && <span>{r.source_body} · </span>}
                    <a href={r.source_url} target="_blank" rel="noreferrer">πηγή →</a>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
      <p className="sub" style={{ marginTop: 12 }}>
        Πηγή δεδομένων: έρευνα Fable (επαληθευμένο μητρώο). Οι Wikipedia/δευτερογενείς σύνδεσμοι
        αντικαταστάθηκαν με πρωτογενείς πηγές (EPPO, EPRS, δικαστήρια). Εξαγωγή στην καρτέλα «Δεδομένα».
      </p>
    </div>
  );
}

export default function App() {
  const [meta, setMeta] = useState<any>(null);
  const [inds, setInds] = useState<Indicator[]>([]);
  const [tab, setTab] = useState<TabId>("overview");
  useEffect(() => {
    api.meta().then(setMeta).catch(() => {});
    api.indicators().then(setInds).catch(() => {});
  }, []);
  return (
    <div className="wrap">
      <header>
        <h1>Παρατηρητήριο Δημοκρατίας — Ελλάδα</h1>
        <p>Δείκτες δημοκρατίας, ελευθερίας Τύπου και κράτους δικαίου από ανεξάρτητους διεθνείς φορείς.
          Κάθε αριθμός με πηγή, ημερομηνία και μεθοδολογία.</p>
      </header>
      <nav className="tabs">
        {TABS.map(t => (
          <button key={t.id} className={"tab " + (tab === t.id ? "active" : "")}
            onClick={() => setTab(t.id)}>{t.label}</button>
        ))}
      </nav>
      <div className="disclaimer">
        <b>Μεθοδολογική σημείωση.</b> Το παρατηρητήριο παρουσιάζει δείκτες όπως τους μετρούν εξωτερικοί
        φορείς (RSF, V-Dem, World Bank, Transparency International, CMPF, EIU, Freedom House). Δεν αποδίδει
        χαρακτηρισμούς με δική του φωνή — τα τεκμηριωμένα στοιχεία μιλούν από μόνα τους. Οι δείκτες
        αντίληψης έχουν ευρέα διαστήματα εμπιστοσύνης και διαβάζονται ως τάσεις.
      </div>

      {tab === "overview" && <Overview inds={inds} />}
      {tab === "indicators" && <IndicatorsExplorer inds={inds} />}
      {tab === "governance" && <Governance />}
      {tab === "dossier" && <Dossier />}
      {tab === "entities" && <Entities />}
      {tab === "accountability" && <Accountability />}
      {tab === "timeline" && <Alerts />}
      {tab === "media" && <><StateAdFlow /><PoliceViolence /><MediaOwnership /></>}
      {tab === "data" && <DataExport meta={meta} />}
    </div>
  );
}
