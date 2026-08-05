"""Watchdog API — serves sourced indicators, alerts, media ownership.
Read-only DuckDB. Every response carries provenance (source_url) per row.
Run: uvicorn api.main:app --port 8010
"""
import os, re, logging, duckdb
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

log = logging.getLogger("watchdog")
_LLM_LAST_ERROR = None

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "watchdog.duckdb")
app = FastAPI(title="Παρατηρητήριο — Watchdog API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def q(sql, params=None):
    con = duckdb.connect(DB, read_only=True)
    try:
        cur = con.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]
    finally:
        con.close()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/meta")
def meta():
    srcs = q("SELECT source_id, name, url, methodology, methodology_url, coverage FROM source ORDER BY source_id")
    inds = q("SELECT DISTINCT source_id, indicator, unit, direction FROM indicator ORDER BY indicator")
    yrs = q("SELECT MIN(year) mn, MAX(year) mx FROM indicator")[0]
    return {"sources": srcs, "indicators": inds, "year_range": yrs,
            "n_indicator_rows": q("SELECT COUNT(*) n FROM indicator")[0]["n"],
            "n_alerts": q("SELECT COUNT(*) n FROM alert")[0]["n"]}


@app.get("/indicators")
def indicators():
    """List distinct indicators with their source + latest value."""
    return q("""
        SELECT i.indicator, i.source_id, s.name AS source_name, i.unit, i.direction,
               MAX(i.year) AS latest_year,
               (SELECT value FROM indicator x WHERE x.indicator=i.indicator
                  AND x.source_id=i.source_id ORDER BY year DESC LIMIT 1) AS latest_value
        FROM indicator i JOIN source s ON i.source_id=s.source_id
        GROUP BY i.indicator, i.source_id, s.name, i.unit, i.direction
        ORDER BY i.indicator""")


@app.get("/indicators/{indicator}/series")
def series(indicator: str):
    rows = q("""SELECT year, value, lower_bound, upper_bound, rank, total_ranked,
                       unit, direction, source_url, note, is_verified
                FROM indicator WHERE indicator=? ORDER BY year""", [indicator])
    if not rows:
        raise HTTPException(404, f"Άγνωστος δείκτης: {indicator}")
    src = q("SELECT s.* FROM source s JOIN indicator i ON i.source_id=s.source_id WHERE i.indicator=? LIMIT 1", [indicator])
    return {"indicator": indicator, "source": src[0] if src else None, "series": rows}


@app.get("/alerts")
def alerts():
    return q("SELECT date, type, title_el, description, severity, source_url, is_verified FROM alert ORDER BY date DESC")


@app.get("/media")
def media():
    return q("SELECT outlet, outlet_type, owner, owner_interests, is_official, source_url, note FROM media_owner ORDER BY owner")


@app.get("/police")
def police():
    return q("""SELECT date, category, title_en, description, victim_or_scope,
                       body_or_court, outcome, source_url, methodology_url, note
                FROM police_violence ORDER BY date""")


# ── governance small-multiples (World Bank WGI, 0-100 percentile) ──────────
@app.get("/governance")
def governance():
    """The four World Bank Worldwide Governance Indicators as annual series,
    with 90% confidence bounds — Voice&Accountability, Rule of Law,
    Control of Corruption, Government Effectiveness."""
    rows = q("""SELECT indicator, year, value, lower_bound, upper_bound, source_url
                FROM indicator WHERE source_id='worldbank_wgi'
                ORDER BY indicator, year""")
    out = {}
    for r in rows:
        out.setdefault(r["indicator"], {"indicator": r["indicator"],
                                        "source_url": r["source_url"], "points": []})
        out[r["indicator"]]["points"].append(
            {"year": r["year"], "value": r["value"],
             "lo": r["lower_bound"], "hi": r["upper_bound"]})
    return {"unit": "0-100 percentile rank", "indicators": list(out.values())}


# ── Greece vs EU-27 comparison (computed from OWID, cached to JSON) ────────
@app.get("/eu-comparison")
def eu_comparison():
    """Greece's position among EU-27 peers on democracy / press / corruption
    indices. Ranks and medians were computed over the EU-27 set from the exact
    OWID series each row links to; higher = better for all rows here."""
    import json
    fp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "data", "raw", "owid", "eu_compare.json")
    if not os.path.exists(fp):
        return {"available": False, "rows": []}
    rows = json.load(open(fp, encoding="utf-8"))
    return {"available": True, "note": "Θέση Ελλάδας στους 27 της ΕΕ· υψηλότερο = καλύτερο.",
            "rows": rows}


# ── state-advertising flow (λίστα Πέτσα → owner → outlet) ─────────────────
@app.get("/state-ad-flow")
def state_ad_flow():
    """Sankey-ready flow: government COVID advertising ('λίστα Πέτσα', €19.8m,
    2020) → media-owner conglomerate → outlet. The per-owner split is NOT an
    official Πέτσα breakdown (that list was never published per-outlet); it is
    the media-ownership structure, shown to make capture visible. The single
    sourced total is the €19,832,132 figure; per-owner amounts are omitted as
    unknown rather than fabricated."""
    tot = q("SELECT amount_eur, source_url, detail FROM dossier "
            "WHERE title LIKE '%λίστα Πέτσα%' OR title LIKE '%Πέτσα%'")
    total = None
    src = tot[0]["source_url"] if tot else ""
    if tot and tot[0].get("amount_eur"):
        try:
            total = float(tot[0]["amount_eur"])
        except (TypeError, ValueError):
            total = None
    owners = q("SELECT outlet, owner, owner_interests, source_url FROM media_owner")
    nodes = [{"id": "govt", "label": "Κυβέρνηση (COVID-19 καμπάνια 2020)", "kind": "gov"}]
    links = []
    seen = set()
    for o in owners:
        oid = "own::" + (o["owner"] or "?")
        if oid not in seen:
            nodes.append({"id": oid, "label": o["owner"], "kind": "owner",
                          "interests": o.get("owner_interests"), "source_url": o.get("source_url")})
            links.append({"source": "govt", "target": oid})
            seen.add(oid)
        outid = "out::" + (o["outlet"] or "?")
        nodes.append({"id": outid, "label": o["outlet"], "kind": "outlet"})
        links.append({"source": oid, "target": outid})
    return {"total_eur": total, "total_label": "λίστα Πέτσα (κρατική διαφήμιση COVID-19, 2020)",
            "total_source": src,
            "note": "Το σύνολο €19,8εκ. είναι τεκμηριωμένο· η κατανομή ανά ιδιοκτήτη ΔΕΝ είναι "
                    "επίσημη ανάλυση της λίστας (δεν δημοσιεύτηκε ανά ΜΜΕ) — δείχνει τη δομή "
                    "ιδιοκτησίας, όχι ποσά ανά εταιρεία.",
            "nodes": nodes, "links": links}


# ── composite "State of Democracy" index (transparent, reweightable) ──────
_COMPOSITE = [
    ("Ελευθερία Έκφρασης (V-Dem)", "Freedom of Expression Index", "higher_better"),
    ("Φιλελεύθερη Δημοκρατία (V-Dem)", "Liberal Democracy Index", "higher_better"),
    ("Αντίληψη Διαφθοράς (TI)", "Corruption Perceptions Index", "higher_better"),
    ("Έλεγχος Διαφθοράς (WB)", "Control of Corruption", "higher_better"),
    ("Κράτος Δικαίου (WB)", "Rule of Law", "higher_better"),
    ("Φωνή & Λογοδοσία (WB)", "Voice and Accountability", "higher_better"),
]


@app.get("/composite-index")
def composite_index():
    """Per-component z-scored series + equal-weight composite. Fully transparent:
    every component and its raw value is returned so the client can reweight and
    the user can see the construction. Labelled explicitly as a derived index,
    NOT an official measure. Government-change reference line: 2019."""
    WINDOW_MIN = 2010  # modern window where all components overlap
    comps = []
    for label, ind, direction in _COMPOSITE:
        rows = q("SELECT year, value, source_url FROM indicator "
                 "WHERE indicator=? AND value IS NOT NULL AND year>=? ORDER BY year",
                 [ind, WINDOW_MIN])
        if len(rows) < 3:
            continue
        vals = [r["value"] for r in rows]
        mu = sum(vals) / len(vals)
        sd = (sum((v - mu) ** 2 for v in vals) / len(vals)) ** 0.5 or 1.0
        pts = [{"year": r["year"], "value": r["value"],
                "z": round((r["value"] - mu) / sd, 3)} for r in rows]
        comps.append({"label": label, "indicator": ind, "direction": direction,
                      "source_url": rows[0]["source_url"], "points": pts})
    years = sorted({p["year"] for c in comps for p in c["points"]})
    composite = []
    for y in years:
        zs = [p["z"] for c in comps for p in c["points"] if p["year"] == y]
        if zs:
            composite.append({"year": y, "z": round(sum(zs) / len(zs), 3), "n": len(zs)})
    return {"is_derived": True, "reference_year": 2019,
            "note": "Παράγωγος σύνθετος δείκτης (z-score ανά συνιστώσα, ίσα βάρη). "
                    "ΔΕΝ είναι επίσημη μέτρηση — εργαλείο σύνοψης· κάθε συνιστώσα φαίνεται ξεχωριστά.",
            "components": comps, "composite": composite}


# ── before/after 2019 (government-change split) ───────────────────────────
@app.get("/before-after")
def before_after(split_year: int = 2019):
    """Every indicator's value at the last pre-split year vs the latest year,
    with signed change. Just slices sourced series by date — the framing is
    pointed, the arithmetic is neutral."""
    inds = q("SELECT DISTINCT indicator, direction FROM indicator WHERE value IS NOT NULL")
    out = []
    for ind in inds:
        rows = q("SELECT year, value, source_url FROM indicator "
                 "WHERE indicator=? AND value IS NOT NULL ORDER BY year", [ind["indicator"]])
        pre = [r for r in rows if r["year"] <= split_year]
        post = [r for r in rows if r["year"] > split_year]
        if not pre or not post:
            continue
        a, b = pre[-1], post[-1]
        delta = b["value"] - a["value"]
        direction = ind["direction"] or "higher_better"
        better = (delta > 0) if "higher" in direction else (delta < 0)
        out.append({"indicator": ind["indicator"],
                    "before_year": a["year"], "before": round(a["value"], 3),
                    "after_year": b["year"], "after": round(b["value"], 3),
                    "delta": round(delta, 3), "direction": direction,
                    "improved": bool(better) if abs(delta) > 1e-9 else None,
                    "source_url": b["source_url"]})
    out.sort(key=lambda x: (x["improved"] is True, x["delta"]))
    return {"split_year": split_year, "n": len(out), "rows": out}


# ── impunity tracker (case → outcome + years elapsed) ─────────────────────
@app.get("/impunity")
def impunity():
    """Accountability outcome per case: convicted / acquitted / stalled /
    no-charges, plus years elapsed. Drawn from police_violence outcomes and
    dossier statuses — every row carries its source."""
    import datetime
    now = datetime.date.today().year

    def classify(text):
        t = _norm(text or "")
        if any(w in t for w in ["life", "convicted", "sentenced", "ισοβ", "καταδικ", "guilty",
                                "violation of article", "found a criminal", "criminal organ",
                                "disbarred", "banned", "blocked from"]):
            return "convicted"
        if any(w in t for w in ["acquit", "αθωώθηκ", "off the hook", "impunity", "ατιμωρησ",
                                "no evidence"]):
            return "acquitted"
        if any(w in t for w in ["charged", "pending", "ongoing", "trial", "investigation",
                                "εκκρεμ", "διερεύν", "probe", "requests lifting", "complaint"]):
            return "ongoing"
        if any(w in t for w in ["no charge", "no prosecution", "καμία δίωξη", "shelved",
                                "αρχειοθ", "forbids it to prosecute"]):
            return "no_charges"
        return "unclear"

    # systemic reports (not a discrete case) — excluded from the case tracker
    SKIP = ["report to the greek government", "national mechanism for the investigation"]

    cases = []
    for r in q("SELECT date, title_en, victim_or_scope, outcome, source_url FROM police_violence"):
        if any(s in _norm(r["title_en"]) for s in SKIP):
            continue
        yr = None
        for tok in (r["date"] or "").split("-"):
            if tok.isdigit() and len(tok) == 4:
                yr = int(tok); break
        cases.append({"case": r["title_en"], "year": yr, "date": r["date"],
                      "outcome_text": r["outcome"], "outcome": classify(r["outcome"]),
                      "years_elapsed": (now - yr) if yr else None,
                      "source_url": r["source_url"], "kind": "police"})
    # Only genuine accountability cases from the dossier: far-right prosecutions
    # and the surveillance/press cases — not the OPEKEPE subsidy rows (which are a
    # financial-fraud process, tracked separately). A row counts as a case if its
    # text names a court/charge/conviction/acquittal/prosecution outcome.
    CASE_HINT = ["convicted", "sentenced", "acquit", "trial", "prosecut", "charge",
                 "life", "guilty", "καταδικ", "αθωώθ", "δίκη", "δίωξη", "ισοβ",
                 "court", "banned", "dissolv", "criminal organ"]
    for r in q("SELECT date, title, detail, status, response, source_url, section FROM dossier "
               "WHERE status IN ('CONVICTED','ESTABLISHED','UNDER_INVESTIGATION','ALLEGED')"):
        blob = (r["title"] or "") + " " + (r["detail"] or "") + " " + (r["response"] or "")
        t = _norm(blob)
        if not any(h in t for h in CASE_HINT):
            continue  # not an accountability case with a judicial outcome
        oc = classify(t)
        if oc == "unclear":
            oc = {"CONVICTED": "convicted", "UNDER_INVESTIGATION": "ongoing"}.get(r["status"], "ongoing")
        yr = None
        for tok in (r["date"] or "").split("-"):
            if tok.isdigit() and len(tok) == 4:
                yr = int(tok); break
        cases.append({"case": r["title"], "year": yr, "date": r["date"],
                      "outcome_text": r["detail"], "outcome": oc,
                      "years_elapsed": (now - yr) if yr else None,
                      "source_url": r["source_url"], "kind": "dossier"})
    order = {"acquitted": 0, "no_charges": 1, "ongoing": 2, "unclear": 3, "convicted": 4}
    cases.sort(key=lambda c: (order.get(c["outcome"], 5), -(c["years_elapsed"] or 0)))
    counts = {}
    for c in cases:
        counts[c["outcome"]] = counts.get(c["outcome"], 0) + 1
    return {"n": len(cases), "counts": counts, "cases": cases}


# ── named entities (people / outlets) index + per-entity record ───────────
# Curated key figures — each maps to the substrings that identify them in the
# dossier (actor/detail/title). Substring match resolves compound rows
# ("Voridis; Avgenakis") to every person named in them.
_ENTITIES = [
    {"id": "mitsotakis", "name": "Κυριάκος Μητσοτάκης", "role": "Πρωθυπουργός (2019–)",
     "match": ["Mitsotakis", "Μητσοτάκη"]},
    {"id": "pierrakakis", "name": "Κυριάκος Πιερρακάκης", "role": "Υπ. Παιδείας / Οικονομικών",
     "match": ["Pierrakakis", "Πιερρακάκη"]},
    {"id": "georgiadis", "name": "Άδωνις Γεωργιάδης", "role": "Υπ. Υγείας / Αντιπρόεδρος ΝΔ",
     "match": ["Georgiadis", "Γεωργιάδη"]},
    {"id": "voridis", "name": "Μάκης Βορίδης", "role": "πρ. Υπ. Αγροτικής Ανάπτυξης / Μετανάστευσης",
     "match": ["Voridis", "Βορίδη"]},
    {"id": "avgenakis", "name": "Λευτέρης Αυγενάκης", "role": "πρ. Υπ. Αγροτικής Ανάπτυξης",
     "match": ["Avgenakis", "Αυγενάκη"]},
    {"id": "michaloliakos", "name": "Νίκος Μιχαλολιάκος", "role": "αρχηγός Χρυσής Αυγής",
     "match": ["Michaloliakos", "Μιχαλολιάκο"]},
    {"id": "kasidiaris", "name": "Ηλίας Κασιδιάρης", "role": "πρ. βουλευτής Χρυσής Αυγής",
     "match": ["Kasidiaris", "Κασιδιάρη"]},
    {"id": "marinakis", "name": "Ευάγγελος Μαρινάκης", "role": "ιδιοκτήτης ΜΜΕ / εφοπλιστής",
     "match": ["Marinakis", "Μαρινάκη", "Alter Ego"]},
    {"id": "koukakis", "name": "Θανάσης Κουκάκης", "role": "δημοσιογράφος (στόχος Predator)",
     "match": ["Koukakis", "Κουκάκη"]},
    {"id": "androulakis", "name": "Νίκος Ανδρουλάκης", "role": "πρόεδρος ΠΑΣΟΚ / ΜΕΠ (στόχος)",
     "match": ["Androulakis", "Ανδρουλάκη"]},
    {"id": "karamanlis", "name": "Κώστας Καραμανλής", "role": "πρ. Υπ. Μεταφορών / ΝΔ (Τέμπη)",
     "match": ["Karamanlis", "Καραμανλή"]},
    {"id": "triantopoulos", "name": "Χρήστος Τριαντόπουλος", "role": "πρ. Αναπλ. Υπ. / ΝΔ (Τέμπη)",
     "match": ["Triantopoulos", "Τριαντόπουλο"]},
]


def _norm(s):
    """accent-insensitive, case-insensitive Greek+Latin fold."""
    import unicodedata
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower()


@app.get("/entities")
def entities():
    """Key figures with a live count of dossier rows mentioning each."""
    rows = q("SELECT section, date, title, detail, actor, role, status, response, "
             "source_body, source_url FROM dossier")
    out = []
    for e in _ENTITIES:
        keys = [_norm(m) for m in e["match"]]
        hits = [r for r in rows if any(
            k in _norm(r.get("actor", "")) or k in _norm(r.get("detail", "")) or
            k in _norm(r.get("title", "")) for k in keys)]
        if hits:
            sc = {}
            for r in hits:
                sc[r["status"]] = sc.get(r["status"], 0) + 1
            out.append({**{k: e[k] for k in ("id", "name", "role")},
                        "n": len(hits), "status_counts": sc})
    return {"entities": out}


@app.get("/entities/{eid}")
def entity(eid: str):
    """Every dossier row that names this entity, newest first."""
    e = next((x for x in _ENTITIES if x["id"] == eid), None)
    if not e:
        raise HTTPException(404, f"Άγνωστο πρόσωπο: {eid}")
    rows = q("SELECT section, date, title, detail, actor, role, status, response, "
             "source_body, source_url FROM dossier")
    keys = [_norm(m) for m in e["match"]]
    hits = [r for r in rows if any(
        k in _norm(r.get("actor", "")) or k in _norm(r.get("detail", "")) or
        k in _norm(r.get("title", "")) for k in keys)]
    hits.sort(key=lambda r: (r.get("date") or ""), reverse=True)
    sc = {}
    for r in hits:
        sc[r["status"]] = sc.get(r["status"], 0) + 1
    return {"id": e["id"], "name": e["name"], "role": e["role"],
            "n": len(hits), "status_counts": sc, "rows": hits}


# ── accountability dossier (Fable sourced record) ─────────────────────────
@app.get("/network")
def network():
    """Force-graph of the accountability web: people ↔ cases ↔ sections.
    A person node links to each dossier row (case) that names them; each case
    links to its thematic section. Every case node carries its source_url so
    the graph stays navigable to primary sources."""
    rows = q("SELECT d_id, section, title, detail, actor, status, source_url FROM dossier")
    nodes = {}
    links = []

    def add(nid, label, kind, **extra):
        if nid not in nodes:
            nodes[nid] = {"id": nid, "label": label, "kind": kind, **extra}

    for e in _ENTITIES:
        keys = [_norm(m) for m in e["match"]]
        hits = [r for r in rows if any(
            k in _norm(r.get("actor", "")) or k in _norm(r.get("detail", "")) or
            k in _norm(r.get("title", "")) for k in keys)]
        if not hits:
            continue
        pid = "p::" + e["id"]
        add(pid, e["name"], "person", role=e["role"], n=len(hits))
        for r in hits:
            cid = "c::" + str(r["d_id"])
            add(cid, (r["title"] or r["detail"] or "")[:70], "case",
                status=r["status"], source_url=r["source_url"])
            links.append({"source": pid, "target": cid})
            sid = "s::" + (r["section"] or "?")
            add(sid, r["section"], "section")
            links.append({"source": cid, "target": sid})
    return {"n_nodes": len(nodes), "n_links": len(links),
            "note": "Κάθε ακμή = τεκμηριωμένη εγγραφή φακέλου· κάθε υπόθεση οδηγεί στην πηγή της.",
            "nodes": list(nodes.values()), "links": links}


@app.get("/dossier")
def dossier():
    """The sourced accountability record: OPEKEPE, surveillance, far-right,
    media capture, and named individuals. Grouped by section; every row carries
    a status label and a source_url."""
    rows = q("""SELECT section, date, title, detail, actor, role, status, response,
                       source_body, source_url, amount_eur
                FROM dossier ORDER BY section, date""")
    out = {}
    for r in rows:
        out.setdefault(r["section"], [])
        out[r["section"]].append(r)
    order = ["Τέμπη / Σιδηροδρομική τραγωδία", "OPEKEPE / Επιδοτήσεις ΕΕ",
             "Trust Your Stars / Έρευνα", "Πανεπιστημιακή αστυνομία (ΟΠΠΙ)",
             "Παρακολουθήσεις (υποκλοπές)", "Τύπος & αιχμαλωσία ΜΜΕ",
             "Ακροδεξιά / Χρυσή Αυγή", "Πρόσωπα — δημόσιο μητρώο"]
    # any section present in the data but not explicitly ordered still appears
    order = order + [s for s in out if s not in order]
    sections = [{"section": s, "rows": out[s]} for s in order if s in out]
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"n": len(rows), "status_counts": counts, "sections": sections}


# ── full flat export of every datapoint (CSV or JSON) ─────────────────────
@app.get("/export/{table}")
def export(table: str, format: str = "json"):
    from fastapi.responses import PlainTextResponse
    import csv, io
    allowed = {
        "indicators": """SELECT i.indicator, i.source_id, s.name AS source_name, i.year,
                            i.value, i.lower_bound, i.upper_bound, i.rank, i.total_ranked,
                            i.unit, i.direction, i.is_verified, i.source_url, i.note
                         FROM indicator i JOIN source s ON i.source_id=s.source_id
                         ORDER BY i.indicator, i.year""",
        "alerts": "SELECT date, type, title_el, description, severity, is_verified, source_url FROM alert ORDER BY date",
        "media": "SELECT outlet, outlet_type, owner, owner_interests, is_official, source_url, note FROM media_owner ORDER BY owner",
        "police": """SELECT date, category, title_en, description, victim_or_scope,
                        body_or_court, outcome, source_url, methodology_url, note
                     FROM police_violence ORDER BY date""",
        "sources": "SELECT source_id, name, url, methodology, methodology_url, coverage FROM source ORDER BY source_id",
        "dossier": """SELECT section, date, title, detail, actor, role, status, response,
                         source_body, source_url, amount_eur
                      FROM dossier ORDER BY section, date""",
    }
    if table not in allowed:
        raise HTTPException(404, f"Άγνωστος πίνακας: {table}. Διαθέσιμα: {list(allowed)}")
    rows = q(allowed[table])
    if format == "csv":
        if not rows:
            return PlainTextResponse("", media_type="text/csv")
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
        return PlainTextResponse(buf.getvalue(), media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=watchdog_{table}.csv"})
    return rows


# ══════════════════════════════════════════════════════════════════════════
#  «Ευρωπαίος αξιολογητής» — LLM comments on the sourced record, in the
#  persona of an objective EU institutional official. STRICTLY GROUNDED:
#  the model may only interpret rows retrieved from the DB; a grounding guard
#  rejects the answer if it introduces any 4-digit year not present in the
#  context (dates are the datum most likely to be hallucinated in this record).
#  No backend configured -> deterministic template (still fully grounded).
# ══════════════════════════════════════════════════════════════════════════

ASSESSOR_SYSTEM = (
    "You are an objective institutional official in the tradition of an EU "
    "rule-of-law rapporteur (European Commission Rule-of-Law report, Venice "
    "Commission, Council of Europe). You are neither Greek government nor "
    "opposition. You assess ONLY the sourced facts provided to you.\n\n"
    "RULES:\n"
    "1. Use ONLY the facts in the CONTEXT block. Never introduce a date, figure, "
    "name, or event that is not there. If you lack information, say so.\n"
    "2. Respect the status labels exactly: ESTABLISHED/CONVICTED = fact of record; "
    "ALLEGED/UNDER_INVESTIGATION = presumption of innocence applies, describe as "
    "allegation or ongoing proceeding, never as guilt.\n"
    "3. Attribute to institutions ('the EPPO found', 'the ECtHR ruled', 'RSF "
    "reports'), not to your own opinion. Report the record; do not deliver a verdict.\n"
    "4. Record the subject's response/denial where the context provides one.\n"
    "5. Sober, measured register. No rhetoric, no adjectives of outrage. Note "
    "systemic patterns where the record shows them (e.g. impunity, weak oversight) "
    "in the neutral language a rapporteur would use.\n"
    "6. Answer in Greek. End with one sentence on what an EU rule-of-law body would "
    "typically flag for follow-up, framed as procedure, not accusation."
)


def _assessor_llm():
    """Return generate_fn(system,user)->str, or None -> deterministic template.
    A missing SDK/key DEGRADES to template (never 500s); reason recorded in _LLM_LAST_ERROR."""
    global _LLM_LAST_ERROR
    backend = os.environ.get("WATCHDOG_LLM_BACKEND", "template").lower()
    if backend == "template":
        return None
    try:
        if backend == "openrouter":
            from openai import OpenAI
            key = os.environ["OPENROUTER_API_KEY"].strip().strip('"').strip("'")
            if not key:
                raise RuntimeError("OPENROUTER_API_KEY set but empty after strip")
            client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
            model = os.environ.get("WATCHDOG_LLM_MODEL", "anthropic/claude-sonnet-4.6")
            def generate_fn(system, user):
                r = client.chat.completions.create(model=model, max_tokens=1400,
                    temperature=0.2, messages=[{"role": "system", "content": system},
                                               {"role": "user", "content": user}])
                return r.choices[0].message.content
            return generate_fn
        if backend == "anthropic":
            import anthropic
            client = anthropic.Anthropic()
            model = os.environ.get("WATCHDOG_LLM_MODEL", "claude-3-5-haiku-latest")
            def generate_fn(system, user):
                r = client.messages.create(model=model, max_tokens=1400, temperature=0.2,
                    system=system, messages=[{"role": "user", "content": user}])
                return r.content[0].text
            return generate_fn
        if backend == "openai":
            from openai import OpenAI
            client = OpenAI()
            model = os.environ.get("WATCHDOG_LLM_MODEL", "gpt-4o-mini")
            def generate_fn(system, user):
                r = client.chat.completions.create(model=model, max_tokens=1400,
                    temperature=0.2, messages=[{"role": "system", "content": system},
                                               {"role": "user", "content": user}])
                return r.choices[0].message.content
            return generate_fn
    except Exception as e:
        _LLM_LAST_ERROR = f"{type(e).__name__}: {e}"
        log.warning("assessor backend '%s' setup failed (%s) — template fallback", backend, _LLM_LAST_ERROR)
        return None
    _LLM_LAST_ERROR = f"unknown backend '{backend}'"
    return None


def _dossier_rows(section=None):
    if section:
        return q("""SELECT section, date, title, detail, actor, role, status, response,
                           source_body, source_url FROM dossier WHERE section=? ORDER BY date""", [section])
    return q("""SELECT section, date, title, detail, actor, role, status, response,
                       source_body, source_url FROM dossier ORDER BY section, date""")


def _build_context(rows):
    """Compact, numbered CONTEXT block — the ONLY facts the model may use."""
    lines = []
    for i, r in enumerate(rows, 1):
        who = f" | {r['actor']}" if r.get("actor") else ""
        role = f" ({r['role']})" if r.get("role") else ""
        d = f"{r['date']} " if r.get("date") else ""
        resp = f" | ΑΠΑΝΤΗΣΗ: {r['response']}" if r.get("response") else ""
        lines.append(f"[{i}] {d}[{r['status']}]{who}{role} — {r['detail'] or r['title']} "
                     f"(πηγή: {r['source_body']}){resp}")
    return "\n".join(lines)


def _grounding_guard(answer, ctx):
    """Flag any 4-digit year in the answer that is NOT in the grounded context —
    the model must not invent dates. Returns list of ungrounded tokens."""
    ctx_years = set(re.findall(r'\b(?:19|20)\d{2}\b', ctx))
    ans_years = set(re.findall(r'\b(?:19|20)\d{2}\b', answer))
    return sorted(ans_years - ctx_years)


def _template_assessment(section, rows):
    """Deterministic grounded fallback — no LLM. Summarises the record faithfully."""
    from collections import Counter
    sc = Counter(r["status"] for r in rows)
    est = sc.get("ESTABLISHED", 0) + sc.get("CONVICTED", 0)
    alu = sc.get("ALLEGED", 0) + sc.get("UNDER_INVESTIGATION", 0)
    head = section or "όλες οι ενότητες"
    lines = [f"**Αξιολόγηση επί των τεκμηριωμένων στοιχείων — {head}**", "",
             f"Το μητρώο περιλαμβάνει {len(rows)} καταγραφές: {est} τεκμηριωμένες/τελεσίδικες "
             f"και {alu} υπό διερεύνηση ή καταγγελλόμενες (ισχύει το τεκμήριο αθωότητας).", ""]
    for r in rows[:12]:
        tag = {"ESTABLISHED": "τεκμηριωμένο", "CONVICTED": "καταδίκη",
               "ALLEGED": "καταγγελλόμενο", "UNDER_INVESTIGATION": "υπό διερεύνηση"}.get(r["status"], r["status"])
        who = f"{r['actor']}: " if r.get("actor") else ""
        lines.append(f"- [{tag}] {who}{r['detail'] or r['title']} — {r['source_body']}.")
        if r.get("response"):
            lines.append(f"  (Απάντηση ενδιαφερομένου: {r['response']})")
    lines += ["", "Σημείωση: αυτό είναι το ντετερμινιστικό, πλήρως τεκμηριωμένο πρότυπο "
              "(δεν χρησιμοποιείται LLM). Κάθε αριθμός προέρχεται από τις παραπάνω πηγές."]
    return "\n".join(lines)


class AssessReq(BaseModel):
    section: str | None = None
    entity: str | None = None


@app.post("/assessment")
def assessment(req: AssessReq):
    """LLM (or template) comments on the sourced record as an objective EU official.
    Strictly grounded; grounding guard rejects invented dates -> falls back to template."""
    scope_label = req.section or "όλες"
    if req.entity:
        e = next((x for x in _ENTITIES if x["id"] == req.entity), None)
        if not e:
            raise HTTPException(404, f"Άγνωστο πρόσωπο: {req.entity}")
        allr = _dossier_rows(None)
        keys = [_norm(m) for m in e["match"]]
        rows = [r for r in allr if any(
            k in _norm(r.get("actor", "")) or k in _norm(r.get("detail", "")) or
            k in _norm(r.get("title", "")) for k in keys)]
        scope_label = e["name"]
    else:
        rows = _dossier_rows(req.section)
    if not rows:
        raise HTTPException(404, f"Καμία εγγραφή: {scope_label}")
    ctx = _build_context(rows)
    gen = _assessor_llm()
    if gen is None:
        return {"used_llm": False, "grounded": True, "backend": "template",
                "section": req.section, "n_facts": len(rows),
                "assessment": _template_assessment(scope_label, rows),
                "note": _LLM_LAST_ERROR}
    user = (f"CONTEXT (οι μόνες πηγές που επιτρέπεται να χρησιμοποιήσεις):\n{ctx}\n\n"
            f"Σχολίασε το παραπάνω τεκμηριωμένο μητρώο ως αντικειμενικός Ευρωπαίος "
            f"αξιολογητής κράτους δικαίου. Αντικείμενο: {scope_label}.")
    try:
        answer = gen(ASSESSOR_SYSTEM, user)
    except Exception as e:
        log.warning("assessor call failed (%s) — template fallback", e)
        return {"used_llm": False, "grounded": True, "backend": "error-fallback",
                "section": req.section, "n_facts": len(rows),
                "assessment": _template_assessment(scope_label, rows), "note": str(e)}
    ungrounded = _grounding_guard(answer, ctx)
    if ungrounded:
        # model invented a date not in the record -> refuse it, serve the template
        return {"used_llm": False, "grounded": False, "backend": "guard-fallback",
                "section": req.section, "n_facts": len(rows),
                "assessment": _template_assessment(scope_label, rows),
                "note": f"Το μοντέλο εισήγαγε μη τεκμηριωμένα έτη {ungrounded}· "
                        f"απορρίφθηκε χάριν ακρίβειας."}
    return {"used_llm": True, "grounded": True, "backend": "llm",
            "section": req.section, "n_facts": len(rows), "assessment": answer}


@app.get("/assessment/meta")
def assessment_meta():
    backend = os.environ.get("WATCHDOG_LLM_BACKEND", "template").lower()
    key_env = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY",
               "openrouter": "OPENROUTER_API_KEY"}.get(backend)
    return {"backend": backend, "expected_key_env": key_env,
            "key_present": bool(key_env and os.environ.get(key_env)),
            "resolves": _assessor_llm() is not None, "setup_error": _LLM_LAST_ERROR}
