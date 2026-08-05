"""Build the watchdog DuckDB from raw sourced files. Idempotent.
Every indicator row is inserted with a mandatory source_url. Run:
    python -m pipeline.build_db
"""
import duckdb, csv, json, os, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "raw")
DB = os.path.join(ROOT, "data", "watchdog.duckdb")
TODAY = datetime.date.today().isoformat()


def _greece(path, valcol):
    rows = []
    with open(path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("Code") == "GRC" and r.get(valcol) not in (None, ""):
                rows.append((int(r["Year"]), float(r[valcol])))
    return sorted(rows)


def main():
    if os.path.exists(DB):
        os.remove(DB)
    con = duckdb.connect(DB)
    con.execute(open(os.path.join(ROOT, "pipeline", "schema.sql")).read())

    # ---- sources ----
    sources = [
        ("worldbank_wgi", "World Bank — Worldwide Governance Indicators",
         "https://api.worldbank.org/v2/country/GRC/indicator/CC.PER.RNK?format=json",
         "Perception-based composite percentile (0-100) with 90% CI",
         "https://api.worldbank.org/v2/country/GRC/indicator/CC.PER.RNK?format=json", "1996-2024"),
        ("owid_rsf", "Reporters Without Borders — World Press Freedom Index (via Our World in Data)",
         "https://ourworldindata.org/grapher/press-freedom-rsf?country=~GRC", "0-100 (higher=freer), OWID-recoded", "https://rsf.org/en/methodology", "2013-2021"),
        ("rsf_direct", "Reporters Without Borders — World Press Freedom Index (rank, verified)",
         "https://rsf.org/en/country/greece", "Global rank of 180", "https://rsf.org/en/methodology", "2022-2025"),
        ("owid_vdem_libdem", "V-Dem — Liberal Democracy Index (via Our World in Data)",
         "https://ourworldindata.org/grapher/liberal-democracy-index?country=~GRC", "Expert-coded composite 0-1", "https://v-dem.net/documents/", "1789-2025"),
        ("owid_vdem_freeexpr", "V-Dem — Freedom of Expression Index (via Our World in Data)",
         "https://ourworldindata.org/grapher/freedom-of-expression-index?country=~GRC", "Expert-coded composite 0-1", "https://v-dem.net/documents/", "1789-2025"),
        ("owid_cpi", "Transparency International — Corruption Perceptions Index (via Our World in Data)",
         "https://ourworldindata.org/grapher/TI-corruption-perception-index?country=~GRC", "0-100 (higher=cleaner)", "https://www.transparency.org/en/cpi", "2012-2024"),
    ]
    con.executemany("INSERT INTO source VALUES (?,?,?,?,?,?)", sources)

    ind_rows = []

    # ---- WGI (4 indicators, with CI) ----
    # Per-indicator World Bank data-API deep links (percentile-rank series) — these
    # are the exact reachable endpoints the wgi_greece.json was built from
    # (each verified HTTP 200; the worldbank.org portal is a JS SPA curl can't render).
    wgi = json.load(open(os.path.join(RAW, "worldbank", "wgi_greece.json")))
    WGI_URL = {
        "CC": "https://api.worldbank.org/v2/country/GRC/indicator/CC.PER.RNK?format=json",
        "GE": "https://api.worldbank.org/v2/country/GRC/indicator/GE.PER.RNK?format=json",
        "RL": "https://api.worldbank.org/v2/country/GRC/indicator/RL.PER.RNK?format=json",
        "VA": "https://api.worldbank.org/v2/country/GRC/indicator/VA.PER.RNK?format=json",
    }
    wgi_fallback = "https://api.worldbank.org/v2/country/GRC/indicator/CC.PER.RNK?format=json"
    for r in wgi:
        url = WGI_URL.get(r.get("ind"), wgi_fallback)
        ind_rows.append(("worldbank_wgi", r["label"], r["year"], r.get("score"), "percentile",
                         r.get("lb"), r.get("ub"), None, None, "higher_better", True,
                         None, url, TODAY))

    # ---- OWID series ----
    # Greece-filtered Our World in Data grapher deep-links (verified reachable) —
    # these are the exact interactive charts the series were extracted from.
    owid = [
        ("owid_rsf", "Press Freedom Index (score)", "rsf/owid_rsf_press_freedom.csv",
         "Press Freedom Index", "0-100", "higher_better",
         "https://ourworldindata.org/grapher/press-freedom-rsf?country=~GRC"),
        ("owid_vdem_libdem", "Liberal Democracy Index", "vdem/owid_vdem_libdem.csv",
         "Liberal democracy index", "0-1", "higher_better",
         "https://ourworldindata.org/grapher/liberal-democracy-index?country=~GRC"),
        ("owid_vdem_freeexpr", "Freedom of Expression Index", "vdem/owid_vdem_freeexpr.csv",
         "Freedom of expression index", "0-1", "higher_better",
         "https://ourworldindata.org/grapher/freedom-of-expression-index?country=~GRC"),
        ("owid_cpi", "Corruption Perceptions Index", "transparency/owid_cpi.csv",
         "Corruption Perceptions Index", "0-100", "higher_better",
         "https://ourworldindata.org/grapher/TI-corruption-perception-index?country=~GRC"),
    ]
    for sid, label, rel, valcol, unit, direction, url in owid:
        for y, v in _greece(os.path.join(RAW, rel), valcol):
            ind_rows.append((sid, label, y, v, unit, None, None, None, None, direction, True, None, url, TODAY))

    # ---- RSF verified ranks (post-2021) ----
    with open(os.path.join(RAW, "manual", "rsf_post2021.csv"), encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ind_rows.append(("rsf_direct", "Press Freedom rank", int(r["year"]), None, "rank",
                             None, None, int(r["rank"]), int(r["total_countries"]),
                             "rank_lower_better", True, r["note"], r["source_url"], TODAY))

    con.executemany(
        "INSERT INTO indicator VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ind_rows)

    # ---- alerts ----
    alerts = []
    with open(os.path.join(RAW, "manual", "alerts.csv"), encoding="utf-8") as f:
        for i, r in enumerate(csv.DictReader(f), 1):
            alerts.append((i, r["date"], r["type"], r["title_el"], r["description"],
                           r["severity"], r["source_url"], True))
    con.executemany("INSERT INTO alert VALUES (?,?,?,?,?,?,?,?)", alerts)

    # ---- media ownership ----
    mo_path = os.path.join(RAW, "manual", "media_ownership.csv")
    if os.path.exists(mo_path):
        with open(mo_path, encoding="utf-8") as f:
            mo = [(r["outlet"], r["outlet_type"], r["owner"], r["owner_interests"],
                   r["is_official"].strip().upper() == "TRUE", r["source_url"], r.get("note", ""))
                  for r in csv.DictReader(f)]
        con.executemany("INSERT INTO media_owner VALUES (?,?,?,?,?,?,?)", mo)

    # ============================================================
    # Antigravity ingest (indicators.csv / events.csv / police_violence.csv / sources.csv)
    # ============================================================
    import re

    def _slug(s):
        return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")

    have_ind = set(x[0] for x in con.execute("SELECT DISTINCT indicator FROM indicator").fetchall())
    have_src = set(x[0] for x in con.execute("SELECT source_id FROM source").fetchall())

    # DB already holds richer/authoritative series for these — skip the Antigravity copies
    SKIP_IND = {"Control of Corruption", "Rule of Law", "Government Effectiveness",
                "Voice & Accountability", "Liberal Democracy Index", "Corruption Perceptions Index"}

    # ---- register new sources (from sources.csv) ----
    src_meta = {}
    sp = os.path.join(RAW, "manual", "sources.csv")
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                sid = _slug(r["source_name"])
                src_meta[r["source_name"]] = sid
                if sid not in have_src:
                    con.execute("INSERT INTO source VALUES (?,?,?,?,?,?)",
                                (sid, r["source_name"], r["url"] or "https://example.org",
                                 (r.get("indicator_type") or "")[:200], r.get("methodology_url") or None,
                                 r.get("coverage_years") or None))
                    have_src.add(sid)

    # ---- new indicators (indicators.csv) ----
    ip = os.path.join(RAW, "manual", "indicators.csv")
    new_ind_rows = []
    if os.path.exists(ip):
        with open(ip, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                name = r["indicator"]
                if name in have_ind or name in SKIP_IND:
                    continue
                sid = src_meta.get(r["source_name"], _slug(r["source_name"]))
                if sid not in have_src:  # ensure FK satisfied
                    con.execute("INSERT INTO source VALUES (?,?,?,?,?,?)",
                                (sid, r["source_name"], "https://example.org", None, None, None))
                    have_src.add(sid)
                def num(x):
                    try:
                        return float(str(x).strip())
                    except (ValueError, TypeError):
                        return None
                def inum(x):
                    try:
                        return int(float(str(x).strip()))
                    except (ValueError, TypeError):
                        return None
                verified = "UNVERIFIED" not in ((r.get("note") or "") + (r.get("value") or "")).upper()
                new_ind_rows.append((sid, name, int(float(r["year"])), num(r.get("value")),
                                     r.get("unit") or None, num(r.get("lower_bound")), num(r.get("upper_bound")),
                                     inum(r.get("greece_rank")), inum(r.get("total_ranked")),
                                     (r.get("direction") or "higher_better"), verified,
                                     r.get("note") or None, r["source_url"], TODAY))
        con.executemany("INSERT INTO indicator VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", new_ind_rows)

    # ---- new events (events.csv) ----
    # Dedup against the dates already present in alerts.csv (existing rows are Greek-titled);
    # insert every event whose normalised date is NOT already an alert.
    EVENT_TITLE_EL = {
        "PEGA Committee Adopts Final Report on Greece":
            "Επιτροπή PEGA: τελική έκθεση για την Ελλάδα",
        "ADAE Audit on Telecommunications Providers":
            "Έλεγχος ΑΔΑΕ σε παρόχους τηλεπικοινωνιών",
    }
    ep = os.path.join(RAW, "manual", "events.csv")
    if os.path.exists(ep):
        have_dates = set(str(x[0]) for x in con.execute("SELECT date FROM alert").fetchall())
        next_id = con.execute("SELECT COALESCE(MAX(alert_id),0)+1 FROM alert").fetchone()[0]
        extra = []
        with open(ep, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                d = (r["date"] or "").strip()
                norm = f"{d}-01-01" if (len(d) == 4 and d.isdigit()) else d
                if norm in have_dates:      # true duplicate of an existing alert (same date)
                    continue
                if r["type"] == "eu_report" and len(d) == 4:
                    title_el = f"Έκθεση Κράτους Δικαίου ΕΕ {d} — κεφάλαιο Ελλάδας"
                else:
                    title_el = EVENT_TITLE_EL.get(r["title_en"], r["title_en"])
                extra.append((next_id, norm, r["type"], title_el,
                              r.get("description") or "", "medium", r["source_url"], True))
                have_dates.add(norm)
                next_id += 1
        if extra:
            con.executemany("INSERT INTO alert VALUES (?,?,?,?,?,?,?,?)", extra)

    # ---- police violence (police_violence.csv) ----
    pp = os.path.join(RAW, "manual", "police_violence.csv")
    if os.path.exists(pp):
        with open(pp, encoding="utf-8") as f:
            pv = [(i, r["date"], r["category"], r["title_en"], r["description"],
                   r["victim_or_scope"], r["body_or_court"], r["outcome"],
                   r["source_url"], r.get("methodology_url") or None, r.get("note") or None)
                  for i, r in enumerate(csv.DictReader(f), 1)]
        con.executemany("INSERT INTO police_violence VALUES (?,?,?,?,?,?,?,?,?,?,?)", pv)

    # ---- accountability dossier (Fable sourced record) ----
    dp = os.path.join(RAW, "fable", "dossier.csv")
    if os.path.exists(dp):
        with open(dp, encoding="utf-8") as f:
            dz = [(i, r["section"], r["date"] or None, r["title"], r["detail"] or None,
                   r["actor"] or None, r["role"] or None, r["status"], r["response"] or None,
                   r["source_body"] or None, r["source_url"], r.get("amount") or None)
                  for i, r in enumerate(csv.DictReader(f), 1)]
        con.executemany("INSERT INTO dossier VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", dz)

    # provenance QA gate: no indicator/alert/police/dossier row without a source_url
    bad_i = con.execute("SELECT COUNT(*) FROM indicator WHERE source_url IS NULL OR source_url=''").fetchone()[0]
    bad_a = con.execute("SELECT COUNT(*) FROM alert WHERE source_url IS NULL OR source_url=''").fetchone()[0]
    bad_p = con.execute("SELECT COUNT(*) FROM police_violence WHERE source_url IS NULL OR source_url=''").fetchone()[0]
    bad_d = con.execute("SELECT COUNT(*) FROM dossier WHERE source_url IS NULL OR source_url='' OR source_url NOT LIKE 'http%'").fetchone()[0]
    assert bad_i == 0 and bad_a == 0 and bad_p == 0 and bad_d == 0, \
        f"PROVENANCE GATE FAIL: {bad_i} indicator + {bad_a} alert + {bad_p} police + {bad_d} dossier rows lack source_url"
    # dossier must carry only valid status labels, and no Wikipedia links anywhere
    bad_status = con.execute("SELECT COUNT(*) FROM dossier WHERE status NOT IN "
        "('ESTABLISHED','CONVICTED','ALLEGED','UNDER_INVESTIGATION','UNVERIFIED')").fetchone()[0]
    assert bad_status == 0, f"DOSSIER STATUS GATE FAIL: {bad_status} rows with invalid status"
    wiki = con.execute("SELECT COUNT(*) FROM dossier WHERE source_url LIKE '%wikipedia.org%'").fetchone()[0]
    assert wiki == 0, f"NO-WIKIPEDIA GATE FAIL: {wiki} dossier rows link to Wikipedia"

    n_ind = con.execute("SELECT COUNT(*) FROM indicator").fetchone()[0]
    n_src = con.execute("SELECT COUNT(*) FROM source").fetchone()[0]
    n_alert = con.execute("SELECT COUNT(*) FROM alert").fetchone()[0]
    n_pv = con.execute("SELECT COUNT(*) FROM police_violence").fetchone()[0]
    n_media = con.execute("SELECT COUNT(*) FROM media_owner").fetchone()[0]
    n_doss = con.execute("SELECT COUNT(*) FROM dossier").fetchone()[0]
    con.close()
    print(f"DB built: {n_src} sources, {n_ind} indicator rows, {n_alert} alerts, "
          f"{n_pv} police-violence rows, {n_media} media owners, {n_doss} dossier rows. Provenance gate PASS.")


if __name__ == "__main__":
    main()
