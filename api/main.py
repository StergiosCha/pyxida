"""
«Πυξίδα ΑΕΙ» — FastAPI backend.

REST endpoints (all read-only over the DuckDB spine):
  GET  /health
  GET  /meta                          -> years, categories, fields, counts
  GET  /departments                   -> search/filter (q, field, city, inst, μόρια range)
  GET  /departments/{code}            -> profile + 10y history + ΕΒΕ
  GET  /departments/{code}/history    -> raw yearly series
  GET  /stats/fields                  -> βάση trends per πεδίο/έτος
  GET  /stats/vacancies               -> κενές θέσεις matrix (heatmap source)
  GET  /stats/risk                    -> «τμήματα σε κίνδυνο» ranked index
  GET  /nppe                          -> non-state universities (ΝΠΠΕ)
  POST /calc/eligibility              -> μόρια + ΕΒΕ eligible set (ranked)
  GET  /predictions/{code}            -> forecast (Phase 3; feature-flagged)

Provenance: every admission row carries source_id + provenance_note; endpoints
surface these so the UI can trace each number to a file + year.
"""
from __future__ import annotations
import os, logging
from fastapi import FastAPI, HTTPException, Query

log = logging.getLogger("pyxida.advisor")
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from api.db import q, q1
from api.eligibility import (Grades, eligible_departments, compute_moria,
                             FIELD_WEIGHTS, FIELD_LABELS_EL, SUBJECT_LABELS_EL)
from api.risk import risk_table

FEATURE_PREDICTIONS = os.environ.get("PYXIDA_ENABLE_PREDICTIONS", "0") == "1"
FEATURE_RAG = os.environ.get("PYXIDA_ENABLE_RAG", "0") == "1"

app = FastAPI(title="Πυξίδα ΑΕΙ API", version="0.1.0",
              description="Ελληνικές πανελλαδικές βάσεις — δεδομένα, στατιστικά, προβλέψεις.")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])


# ── meta ────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/meta")
def meta():
    years = [r["year"] for r in q("SELECT DISTINCT year FROM admission ORDER BY year")]
    cats = [r["category"] for r in q("SELECT DISTINCT category FROM admission ORDER BY category")]
    counts = q1("""SELECT
        (SELECT COUNT(*) FROM department) AS departments,
        (SELECT COUNT(*) FROM institution) AS institutions,
        (SELECT COUNT(*) FROM admission) AS admission_rows,
        (SELECT COUNT(*) FROM dept_alias) AS aliases,
        (SELECT COUNT(*) FROM unmatched_dept) AS unmatched""")
    return {
        "years": years, "categories": cats,
        "fields": [{"id": k, "label": v} for k, v in FIELD_LABELS_EL.items()],
        "subjects": [{"id": k, "label": v} for k, v in SUBJECT_LABELS_EL.items()],
        "counts": counts,
        "gap_years": [2020, 2021, 2022, 2023],
        "features": {"predictions": FEATURE_PREDICTIONS, "rag": FEATURE_RAG},
        "llm": _llm_status(),
    }


def _mask(v):
    """Masked key preview for /meta: length + first4/last4, never the full value.
    Reveals a placeholder ('sk-or-...') or a whitespace-only value without leaking
    the secret."""
    if v is None:
        return None
    raw = v
    s = v.strip().strip('"').strip("'")
    return {"len_raw": len(raw), "len_stripped": len(s),
            "preview": (s[:4] + "…" + s[-4:]) if len(s) >= 10 else s,
            "had_whitespace": raw != s}


def _llm_status():
    """Diagnostic: what LLM backend the server sees and whether it resolves to a
    working generate_fn. Lets you confirm from one URL why the advisor did or did
    not use an LLM. Never leaks key values — only presence booleans."""
    backend = os.environ.get("PYXIDA_LLM_BACKEND", "template").lower()
    key_env = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY",
               "openrouter": "OPENROUTER_API_KEY"}.get(backend)
    fn = _advisor_llm() if FEATURE_RAG else None
    # live probe: actually call the model once (tiny) so /meta reports whether
    # the API call itself works — the client can build fine yet the call 401/404.
    probe = None
    if fn is not None:
        try:
            out = fn("Απάντησε με μία λέξη.", "Πες 'εντάξει'.")
            probe = {"ok": True, "sample": (out or "")[:60]}
        except Exception as e:
            probe = {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}
    return {
        "backend": backend,
        "rag_enabled": FEATURE_RAG,
        "expected_key_env": key_env,
        "key_present": bool(os.environ.get(key_env)) if key_env else None,
        "key_preview": _mask(os.environ.get(key_env)) if key_env else None,
        "model": os.environ.get("PYXIDA_LLM_MODEL"),
        "generate_fn_resolved": fn is not None,   # True => client built OK
        "setup_error": _LLM_LAST_ERROR,           # why it fell back, if it did
        "live_call": probe,                       # actual API round-trip result
    }


# ── departments ───────────────────────────────────────────────────────────
@app.get("/departments")
def list_departments(
    q_text: Optional[str] = Query(None, alias="q"),
    field: Optional[str] = None, city: Optional[str] = None,
    institution: Optional[str] = None,
    moria_min: Optional[float] = None, moria_max: Optional[float] = None,
    year: int = 2025, category: str = "ΓΕΛ90",
    limit: int = 100, offset: int = 0,
):
    where = ["a.year = ?", "a.category = ?", "a.base_last IS NOT NULL"]
    params: list = [year, category]
    # Greek accent-insensitive matching: fold both column and term through
    # strip_accents(upper(...)) so "Πληροφορικής" matches "ΠΛΗΡΟΦΟΡΙΚΗΣ" and
    # "Αθήνα" matches the accent-stripped city key. (DuckDB has strip_accents.)
    if q_text:
        where.append("(strip_accents(upper(d.name)) LIKE strip_accents(upper(?)) "
                     "OR strip_accents(upper(i.name)) LIKE strip_accents(upper(?)))")
        params += [f"%{q_text}%", f"%{q_text}%"]
    if field:
        where.append("d.scientific_field = ?"); params.append(field)
    if city:
        where.append("(strip_accents(upper(d.city)) LIKE strip_accents(upper(?)) "
                     "OR strip_accents(upper(d.city_display)) LIKE strip_accents(upper(?)))")
        params.append(f"%{city}%"); params.append(f"%{city}%")
    if institution:
        where.append("strip_accents(upper(i.name)) LIKE strip_accents(upper(?))")
        params.append(f"%{institution}%")
    if moria_min is not None:
        where.append("a.base_last >= ?"); params.append(moria_min)
    if moria_max is not None:
        where.append("a.base_last <= ?"); params.append(moria_max)
    total = q1(f"""SELECT COUNT(*) n FROM admission a
        JOIN department d ON d.dept_code=a.dept_code
        LEFT JOIN institution i ON i.institution_id=d.institution_id
        WHERE {' AND '.join(where)}""", params)["n"]
    rows = q(f"""SELECT a.dept_code, d.name, i.name AS institution,
        COALESCE(d.city_display, d.city) AS city,
        d.scientific_field, a.base_last, a.seats_offered, a.admitted,
        a.vacancies, a.fill_rate, a.ebe_coefficient, a.ebe_threshold
        FROM admission a
        JOIN department d ON d.dept_code=a.dept_code
        LEFT JOIN institution i ON i.institution_id=d.institution_id
        WHERE {' AND '.join(where)}
        ORDER BY a.base_last DESC LIMIT ? OFFSET ?""", params + [limit, offset])
    return {"total": total, "limit": limit, "offset": offset, "items": rows}


@app.get("/departments/{code}")
def department_profile(code: str, category: str = "ΓΕΛ90"):
    dept = q1("""SELECT d.*, i.name AS institution, i.inst_type, i.is_state
        FROM department d LEFT JOIN institution i ON i.institution_id=d.institution_id
        WHERE d.dept_code = ?""", [code])
    if not dept:
        raise HTTPException(404, f"Άγνωστος κωδικός τμήματος: {code}")
    history = q("""SELECT year, category, base_last, grade_first, seats_offered,
        admitted, vacancies, fill_rate, ebe_coefficient, ebe_threshold,
        provenance_note FROM admission
        WHERE dept_code = ? AND category = ? ORDER BY year""", [code, category])
    aliases = q("""SELECT alias_code, alias_name, relation, confidence, year_from, year_to
        FROM dept_alias WHERE canonical_code = ?""", [code])
    demand = _demand_for(code)
    return {"department": dept, "category": category,
            "history": history, "aliases": aliases, "demand": demand}


def _has_preference():
    try:
        return bool(q1("SELECT 1 FROM information_schema.tables WHERE table_name='preference'"))
    except Exception:
        return False


def _demand_for(code: str):
    """First-preference demand per year (independent of who was admitted)."""
    if not _has_preference():
        return None
    return q("""SELECT year, pref1, pref2, pref3, pref_other, pref_total
        FROM preference WHERE dept_code = ? ORDER BY year""", [code])


@app.get("/departments/{code}/history")
def department_history(code: str, category: Optional[str] = None):
    if category:
        return q("""SELECT * FROM admission WHERE dept_code=? AND category=?
                    ORDER BY year""", [code, category])
    return q("SELECT * FROM admission WHERE dept_code=? ORDER BY year, category", [code])


# ── stats ─────────────────────────────────────────────────────────────────
@app.get("/stats/fields")
def stats_fields(category: str = "ΓΕΛ90"):
    """Median/mean βάση per scientific_field per year."""
    return q("""SELECT a.year, d.scientific_field AS field,
        COUNT(*) n, ROUND(MEDIAN(a.base_last),0) median_base,
        ROUND(AVG(a.base_last),0) mean_base,
        SUM(a.vacancies) vacancies
        FROM admission a JOIN department d ON d.dept_code=a.dept_code
        WHERE a.category=? AND d.scientific_field IS NOT NULL AND a.base_last IS NOT NULL
        GROUP BY a.year, d.scientific_field ORDER BY a.year, field""", [category])


@app.get("/stats/cities")
def stats_cities(category: str = "ΓΕΛ90", year: int = 2025):
    """City directory for the search filter: each city (display-cased) with its
    department count and the institutions present, latest year. One institution
    can span several cities (e.g. Παν. Κρήτης → Ηράκλειο + Ρέθυμνο), so this is
    keyed by city, not institution."""
    return q("""SELECT COALESCE(d.city_display, d.city) AS city,
        COUNT(DISTINCT a.dept_code) n_depts,
        COUNT(DISTINCT d.institution_id) n_institutions,
        STRING_AGG(DISTINCT i.name, ' · ') institutions
        FROM admission a JOIN department d ON d.dept_code=a.dept_code
        LEFT JOIN institution i ON i.institution_id=d.institution_id
        WHERE a.category=? AND a.year=? AND d.city IS NOT NULL
        GROUP BY 1 ORDER BY n_depts DESC, city""", [category, year])


@app.get("/stats/vacancies")
def stats_vacancies(category: str = "ΓΕΛ90", top: int = 40):
    """Vacancy heatmap source: per-year totals + worst departments."""
    by_year = q("""SELECT year, SUM(vacancies) vacancies, SUM(seats_offered) seats,
        ROUND(SUM(vacancies)*1.0/NULLIF(SUM(seats_offered),0),4) vacancy_rate
        FROM admission WHERE category=? GROUP BY year ORDER BY year""", [category])
    worst = q("""SELECT a.dept_code, d.name, i.name institution, a.year,
        a.vacancies, a.seats_offered, a.fill_rate
        FROM admission a JOIN department d ON d.dept_code=a.dept_code
        LEFT JOIN institution i ON i.institution_id=d.institution_id
        WHERE a.category=? AND a.year=(SELECT MAX(year) FROM admission WHERE category=?)
        ORDER BY a.vacancies DESC NULLS LAST LIMIT ?""", [category, category, top])
    return {"by_year": by_year, "worst_latest": worst}


@app.get("/stats/risk")
def stats_risk(year: int = 2025, category: str = "ΓΕΛ90",
               top: int = 50, all: bool = False, band: Optional[str] = None):
    """At-risk index for every department, ranked. By default returns the top
    `top`; pass all=true for the FULL list (all departments, at-risk and not),
    or band=υψηλός|μέτριος|χαμηλός to filter to one risk tier. `n` is the full
    count; `n_by_band` breaks it down so nothing is hidden."""
    tbl = risk_table(q, year, category)
    n_by_band = {}
    for r in tbl:
        n_by_band[r["risk_band"]] = n_by_band.get(r["risk_band"], 0) + 1
    items = tbl if (all or band) else tbl[:top]
    if band:
        items = [r for r in items if r["risk_band"] == band]
    return {"year": year, "category": category, "n": len(tbl),
            "n_returned": len(items), "n_by_band": n_by_band, "items": items}


# ── ΝΠΠΕ ────────────────────────────────────────────────────────────────
@app.get("/stats/demand")
def stats_demand(year: int = 2025, category: str = "ΓΕΛ90"):
    """Demand (first preferences) vs vacancy per department — the core signal:
    departments students don't want are the ones that empty out."""
    if not _has_preference():
        return {"available": False, "rows": [],
                "note": "Το πίνακας preference δεν έχει φορτωθεί· τρέξε pipeline.load_preferences."}
    rows = q("""SELECT a.dept_code, d.name, COALESCE(d.city_display,d.city) AS city,
                   d.scientific_field AS field,
                   a.seats_offered AS seats, a.vacancies AS vac, a.base_last AS base,
                   p.pref1, p.pref_total
            FROM admission a
            JOIN department d ON d.dept_code=a.dept_code
            JOIN preference p ON p.dept_code=a.dept_code AND p.year=a.year
            WHERE a.year=? AND a.category=? AND a.seats_offered>0""", [year, category])
    for r in rows:
        r["vacancy_rate"] = round(r["vac"]/r["seats"], 4) if r["seats"] else None
        r["demand_per_seat"] = round(r["pref1"]/r["seats"], 3) if r["seats"] else None
    return {"available": True, "year": year, "category": category,
            "n": len(rows), "rows": rows,
            "note": "pref1 = πρώτες προτιμήσεις (ζήτηση ανεξάρτητη από εισαγωγή). "
                    "Πηγή: data.gov.gr, Στατιστικά Μηχανογραφικών."}


@app.get("/nppe")
def nppe():
    rows = q("SELECT * FROM nppe_program ORDER BY institution, program")
    return {"n": len(rows), "items": rows,
            "note": "Στοιχεία εγγραφών ενδέχεται να προέρχονται από δημοσιεύματα· "
                    "επισημαίνονται ως μη επίσημα (enrollment_is_official=false)."}


# ── program-family comparison ─────────────────────────────────────────────
@app.get("/compare/families")
def compare_families(min_n: int = 2, category: str = "ΓΕΛ90"):
    from . import compare
    fams = compare.list_families(min_n=min_n, category=category)
    return {"n": len(fams), "families": fams}


@app.get("/compare/{family}")
def compare_family_ep(family: str, category: str = "ΓΕΛ90"):
    from . import compare
    res = compare.compare_family(family, category=category)
    if not res["departments"]:
        raise HTTPException(404, f"Δεν βρέθηκαν τμήματα για «{family}».")
    return res


# ── eligibility calculator ────────────────────────────────────────────────
class EligibilityRequest(BaseModel):
    grades: dict[str, float] = Field(..., description="Subject grades on /20 scale")
    field_id: str = Field(..., description="One of 1ο/2ο/3ο/4ο")
    year: int = 2025
    category: str = "ΓΕΛ90"
    include_ineligible: bool = False
    field_weights: Optional[dict] = None


@app.post("/calc/eligibility")
def calc_eligibility(req: EligibilityRequest):
    if req.field_id not in FIELD_WEIGHTS and not req.field_weights:
        raise HTTPException(400, f"Άγνωστο πεδίο: {req.field_id}")
    g = Grades(values=req.grades)
    try:
        return eligible_departments(
            q, g, req.field_id, year=req.year, category=req.category,
            field_weights=req.field_weights,
            include_ineligible=req.include_ineligible)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/calc/moria")
def calc_moria(req: EligibilityRequest):
    g = Grades(values=req.grades)
    return compute_moria(g, req.field_id, req.field_weights)


# ── predictions (Phase 3, feature-flagged) ────────────────────────────────
@app.get("/predictions/{code}")
def predictions(code: str, category: str = "ΓΕΛ90"):
    if not FEATURE_PREDICTIONS:
        raise HTTPException(503, "Οι προβλέψεις είναι απενεργοποιημένες "
                                 "(feature flag PYXIDA_ENABLE_PREDICTIONS).")
    rows = q("""SELECT * FROM prediction WHERE dept_code=? AND category=?
                ORDER BY target_year""", [code, category])
    return {"dept_code": code, "category": category, "predictions": rows}


# ── city / institution comparison (within-family, matched) ───────────────
@app.get("/places/options")
def places_options():
    from . import places
    return places.list_options()


@app.get("/places/compare")
def places_compare(kind: str, a: str, b: str):
    if kind not in ("city", "institution"):
        raise HTTPException(400, "kind must be 'city' or 'institution'")
    from . import places
    return places.compare_places(kind, a, b)


# ── private-path cost: miss the public βάση → the ΝΠΠΕ price tag ───────────
@app.get("/nppe/private-path")
def private_path(program: str, moria: float | None = None,
                 year: int = 2025, category: str = "ΓΕΛ90"):
    """For a ΝΠΠΕ program family, list the public departments (with 2025 βάσεις)
    and the private alternative's full degree cost. If the student passes their
    μόρια, flags which public seats they'd reach vs miss — making the private
    price tag the concrete cost of a near-miss. All figures sourced: βάσεις from
    data.gov.gr, tuition from the research report (ΝΠΠΕ §4)."""
    kw = _NPPE_FAMILY.get(program)
    if not kw:
        raise HTTPException(404, f"Άγνωστο πρόγραμμα ΝΠΠΕ: {program}. "
                                 f"Διαθέσιμα: {', '.join(_NPPE_FAMILY)}")
    npp = q("""SELECT institution, city, tuition_eu, degree_years, note, enrollment_is_official
               FROM nppe_program WHERE program=? AND tuition_eu IS NOT NULL""", [program])
    pub = q("""
        SELECT d.name, d.city_display, a.base_last, a.ebe_threshold, a.vacancies
        FROM admission a JOIN department d ON a.dept_code = d.dept_code
        WHERE a.year=? AND a.category=?
              AND (UPPER(d.name) LIKE ? OR UPPER(d.name) LIKE ?)
              AND a.base_last IS NOT NULL
        ORDER BY a.base_last DESC
    """, [year, category, f"{kw}%", f"% {kw}%"])
    for r in pub:
        r["reachable"] = (moria is not None and moria >= (r["base_last"] or 0))
        r["gap"] = round((r["base_last"] or 0) - moria, 1) if moria is not None else None
    privates = []
    for n in npp:
        yrs = n["degree_years"] or 4
        privates.append({"institution": n["institution"], "city": n["city"],
                         "tuition_eu": n["tuition_eu"], "degree_years": yrs,
                         "total_cost_eur": int((n["tuition_eu"] or 0) * yrs),
                         "note": n["note"]})
    any_reach = any(r["reachable"] for r in pub) if moria is not None else None
    return {"program": program, "public_family": kw, "moria": moria,
            "year": year, "category": category,
            "reaches_any_public": any_reach,
            "public_departments": pub, "private_alternatives": privates,
            "note": "Βάσεις: data.gov.gr (Υπ. Παιδείας). Δίδακτρα ΝΠΠΕ: ερευνητική έκθεση §4. "
                    "Το ιδιωτικό κόστος = δίδακτρα × έτη σπουδών· δεν περιλαμβάνει διαβίωση."}


# ── cost of abandonment (empty seats × sourced per-student public spend) ──
# Eurostat UOE educ_uoe_fini04: Greece public annual expenditure per FTE
# tertiary student. Latest available = 2023. This is the ONLY figure used;
# it is a real sourced number, not an estimate.
_PER_STUDENT_EUR = 2984          # Greece 2023, public institutions, EUR/FTE/yr
_PER_STUDENT_YEAR = 2023
_PER_STUDENT_SRC = ("Eurostat (UOE) educ_uoe_fini04 — δημόσια ετήσια δαπάνη ανά "
                    "φοιτητή τριτοβάθμιας (FTE), Ελλάδα 2023")
_PER_STUDENT_URL = "https://ec.europa.eu/eurostat/databrowser/view/educ_uoe_fini04/default/table?lang=en"


@app.get("/stats/abandonment-cost")
def abandonment_cost(year: int = 2025, category: str = "ΓΕΛ90"):
    """Public money allocated to seats that went unfilled: empty seats ×
    Eurostat per-student public spend (€/student/year). The per-student figure
    is a real sourced number (Eurostat 2023); the annual cost is one cohort-year.
    A 4-year degree multiplier is returned SEPARATELY (not baked in) so the user
    sees the arithmetic. This estimates *allocated* funding proportional to
    enrolment, not marginal savings — labelled as such in the UI."""
    tot = q("""SELECT SUM(seats_offered) AS seats, SUM(admitted) AS adm,
                      SUM(vacancies) AS empty
               FROM admission WHERE year=? AND category=?""", [year, category])
    empty = int(tot[0]["empty"] or 0)
    seats = int(tot[0]["seats"] or 0)
    annual = empty * _PER_STUDENT_EUR
    # top departments by absolute empty-seat cost
    depts = q("""
        SELECT d.name, d.city_display, a.vacancies, a.seats_offered
        FROM admission a JOIN department d ON a.dept_code = d.dept_code
        WHERE a.year=? AND a.category=? AND a.vacancies > 0
        ORDER BY a.vacancies DESC LIMIT 20
    """, [year, category])
    for r in depts:
        r["annual_cost_eur"] = int((r["vacancies"] or 0) * _PER_STUDENT_EUR)
    return {"year": year, "category": category,
            "empty_seats": empty, "total_seats": seats,
            "per_student_eur": _PER_STUDENT_EUR, "per_student_year": _PER_STUDENT_YEAR,
            "annual_cost_eur": annual,
            "degree_years_example": 4,
            "degree_cost_eur": annual * 4,
            "per_student_source": _PER_STUDENT_SRC, "per_student_url": _PER_STUDENT_URL,
            "caveat": "Εκτιμά τη δημόσια χρηματοδότηση που αντιστοιχεί (κατ' αναλογία εγγραφών) "
                      "στις κενές θέσεις — όχι το οριακό κόστος/εξοικονόμηση. Η δαπάνη ανά φοιτητή "
                      "είναι πραγματικό στοιχείο Eurostat (2023), όχι εκτίμηση.",
            "top_departments": depts}


# ── regional wealth vs seat-fill ("class map" — correlation, honestly) ────
@app.get("/stats/wealth-fill")
def stats_wealth_fill(year: int = 2025, category: str = "ΓΕΛ90"):
    """Regional GDP/capita (Eurostat) vs seat fill-rate (data.gov.gr) per NUTS-3
    region. Reports the ACTUAL Pearson correlation with n and an approximate
    significance — never a forced narrative. This is an ECOLOGICAL (regional)
    relationship; it does NOT measure individual family income and cannot show
    that poorer students are excluded. The UI states this limit explicitly and
    reports the finding as-is, weak or strong."""
    import numpy as np, math
    rows = q("""
        SELECT cc.region, d.nuts3, cc.gdp_per_capita, cc.is_metro,
               AVG(ri.fill_rate) AS fill, AVG(ri.vacancy_rate) AS vac, COUNT(*) AS n
        FROM v_risk_inputs ri
        JOIN department d    ON ri.dept_code = d.dept_code
        JOIN city_context cc ON d.nuts3      = cc.nuts3
        WHERE ri.year=? AND ri.category=? AND cc.gdp_per_capita IS NOT NULL
        GROUP BY 1,2,3,4 ORDER BY cc.gdp_per_capita
    """, [year, category])
    g = np.array([r["gdp_per_capita"] for r in rows], float)
    f = np.array([r["fill"] for r in rows], float)
    n = len(rows)

    def pearson(a, b):
        a = a - a.mean(); b = b - b.mean()
        d = math.sqrt(float((a @ a) * (b @ b)))
        return float(a @ b) / d if d else 0.0
    r = pearson(g, f)
    t = r * math.sqrt((n - 2) / (1 - r ** 2)) if abs(r) < 1 and n > 2 else 0.0
    # crude two-sided p from t via survival of normal approx (n large-ish)
    p = math.erfc(abs(t) / math.sqrt(2))
    strength = ("καμία ουσιαστική" if abs(r) < 0.2 else
                "ασθενής" if abs(r) < 0.4 else
                "μέτρια" if abs(r) < 0.6 else "ισχυρή")
    for rr in rows:
        rr["fill"] = round(rr["fill"], 4); rr["vac"] = round(rr["vac"], 4)
    return {"year": year, "category": category, "n_regions": n,
            "corr_gdp_fill": round(r, 3), "t_stat": round(t, 2),
            "p_approx": round(p, 3), "significant_05": bool(p < 0.05),
            "strength_el": strength,
            "finding": (f"Συσχέτιση GDP/κατοίκου–πληρότητας: r={r:+.2f} ({strength}), "
                        f"n={n}, p≈{p:.2f}. "
                        + ("ΔΕΝ είναι στατιστικά σημαντική — ο περιφερειακός πλούτος δεν "
                           "προβλέπει την πληρότητα." if p >= 0.05 else
                           "Στατιστικά σημαντική στο 5%.")),
            "caveat": "ΟΙΚΟΛΟΓΙΚΗ συσχέτιση σε επίπεδο περιφέρειας — ΔΕΝ μετρά ατομικό "
                      "οικογενειακό εισόδημα και ΔΕΝ τεκμηριώνει ότι φτωχοί φοιτητές "
                      "αποκλείονται. GDP/κατοίκου: Eurostat NUTS-3· πληρότητα: data.gov.gr.",
            "regions": rows}


# ── 2030 trend scenario (NOT a forecast — conditional extrapolation) ──────
@app.get("/stats/projection")
def stats_projection(target_year: int = 2030, category: str = "ΓΕΛ90",
                     model: str = "linear"):
    """Conditional trend extrapolation of regional vacancy — explicitly a
    SCENARIO ('if the 2015–2025 trend continues'), never a forecast. Fitted on
    observed years only (2015–2019, 2024–2025); the 2020–2023 gap is absent, not
    interpolated. Each region gets a linear fit with a prediction interval; both
    the point and the band are CLIPPED to [0,1] because a vacancy rate is bounded
    — near the ceiling the number reads as 'trending to saturation', not a literal
    value. Regions with <4 observed points are suppressed (no honest line through
    noise). model='linear' (all years) or 'recent' (last 3 observed years)."""
    import numpy as np
    rows = q("""
        SELECT ri.year, cc.region, d.nuts3, cc.is_metro,
               AVG(ri.vacancy_rate) AS v, COUNT(*) AS n
        FROM v_risk_inputs ri
        JOIN department d    ON ri.dept_code = d.dept_code
        JOIN city_context cc ON d.nuts3      = cc.nuts3
        WHERE ri.category = ? AND d.nuts3 IS NOT NULL
        GROUP BY 1,2,3,4 ORDER BY 2,1
    """, [category])
    from collections import defaultdict
    ser = defaultdict(list); meta = {}
    for r in rows:
        ser[r["region"]].append((r["year"], r["v"]))
        meta[r["region"]] = (r["nuts3"], r["is_metro"])
    out, suppressed = [], 0
    for reg, pts in ser.items():
        pts = sorted(pts)
        if model == "recent":
            pts = pts[-3:]
        if len(pts) < 4 and model != "recent":
            suppressed += 1; continue
        if len(pts) < 3:
            suppressed += 1; continue
        xs = np.array([p[0] for p in pts], float)
        ys = np.array([p[1] for p in pts], float)
        A = np.vstack([xs, np.ones_like(xs)]).T
        coef, *_ = np.linalg.lstsq(A, ys, rcond=None)
        slope, intc = coef
        resid = ys - A @ coef
        dof = len(xs) - 2
        s = float(np.sqrt((resid @ resid) / dof)) if dof > 0 else 0.0
        xm = xs.mean(); ssx = ((xs - xm) ** 2).sum() or 1.0
        se = s * np.sqrt(1 + 1 / len(xs) + (target_year - xm) ** 2 / ssx)
        pt = slope * target_year + intc
        clip = lambda z: max(0.0, min(1.0, z))
        p_c, lo_c, hi_c = clip(pt), clip(pt - 1.96 * se), clip(pt + 1.96 * se)
        latest = pts[-1]
        out.append({"region": reg, "nuts3": meta[reg][0], "is_metro": bool(meta[reg][1]),
                    "n_points": len(xs),
                    "latest_year": latest[0], "latest_vacancy": round(latest[1], 4),
                    "proj_vacancy": round(p_c, 4),
                    "proj_lo": round(lo_c, 4), "proj_hi": round(hi_c, 4),
                    "slope_per_year": round(float(slope), 5),
                    "at_ceiling": bool(p_c >= 0.999)})
    out.sort(key=lambda x: -x["proj_vacancy"])
    return {"target_year": target_year, "category": category, "model": model,
            "n_regions": len(out), "n_suppressed": suppressed,
            "is_scenario": True,
            "observed_years": sorted({r["year"] for r in rows}),
            "caveat": "ΣΕΝΑΡΙΟ, όχι πρόβλεψη: «αν συνεχιστεί η τάση 2015–2025». Γραμμική "
                      "προβολή σε φραγμένο μέγεθος (0–100%) — κοντά στο ταβάνι σημαίνει «τείνει "
                      "προς πλήρη ερήμωση», όχι κυριολεκτική τιμή. Το κενό 2020–2023 δεν "
                      "παρεμβάλλεται. Καμία υπόθεση δημογραφικής/πολιτικής μεταβολής.",
            "regions": out}


# ── ΝΠΠΕ "intent" dashboard: private programs vs public-analog demand ─────
_NPPE_FAMILY = {
    "Ιατρική": "ΙΑΤΡΙΚΗΣ",
    "Φαρμακευτική": "ΦΑΡΜΑΚΕΥΤΙΚΗΣ",
    "Διοίκηση Επιχειρήσεων": "ΔΙΟΙΚΗΣΗΣ ΕΠΙΧΕΙΡΗΣΕΩΝ",
    "Ψυχολογία": "ΨΥΧΟΛΟΓΙΑΣ",
    "Νομική": "ΝΟΜΙΚΗΣ",
}


@app.get("/nppe/intent")
def nppe_intent(year: int = 2025, category: str = "ΓΕΛ90"):
    """For each licensed ΝΠΠΕ program, the vacancy of its public-analog field vs
    the national mean. Shows whether private universities entered high-demand
    (low-vacancy) public markets or the eroding periphery. Descriptive: the
    'intent' reading is interpretation, labelled as such in the UI; the vacancy
    arithmetic is neutral and sourced to data.gov.gr βάσεις."""
    nat = q("""SELECT AVG(vacancy_rate) AS v FROM v_risk_inputs
               WHERE year=? AND category=?""", [year, category])
    national = nat[0]["v"] if nat else None
    out = []
    for prog, kw in _NPPE_FAMILY.items():
        rows = q("""
            SELECT d.name, d.city_display, ri.vacancy_rate, ri.admitted
            FROM v_risk_inputs ri JOIN department d ON ri.dept_code = d.dept_code
            WHERE ri.year=? AND ri.category=?
                  AND (UPPER(d.name) LIKE ? OR UPPER(d.name) LIKE ?)
        """, [year, category, f"{kw}%", f"% {kw}%"])
        if not rows:
            continue
        mvac = sum(r["vacancy_rate"] for r in rows) / len(rows)
        tui = q("SELECT tuition_eu FROM nppe_program WHERE program=? LIMIT 1", [prog])
        out.append({"program": prog, "public_family": kw, "n_public_depts": len(rows),
                    "public_mean_vacancy": round(mvac, 4),
                    "vs_national": round(mvac - (national or 0), 4),
                    "tuition_eu": tui[0]["tuition_eu"] if tui else None})
    out.sort(key=lambda x: x["public_mean_vacancy"])
    return {"year": year, "category": category,
            "national_mean_vacancy": round(national, 4) if national is not None else None,
            "note": "Πηγή κενών: data.gov.gr βάσεις (Υπ. Παιδείας). Η ανάγνωση περί «πρόθεσης» "
                    "είναι ερμηνεία — τα ΝΠΠΕ μπήκαν σε πεδία με ζήτηση κάτω από τον εθνικό μέσο "
                    "όρο κενών, δηλ. εκεί που το δημόσιο είναι ισχυρότερο.",
            "programs": out}


# ── regional risk map (NUTS-3 aggregation, Eurostat-sourced context) ──────
@app.get("/stats/regions")
def stats_regions(year: int = 2025, category: str = "ΓΕΛ90"):
    """Per-NUTS-3-region aggregate: mean vacancy, department count, admitted,
    plus Eurostat context (metro flag, population, GDP/capita). Powers the
    regional risk map. Demographic-cohort overlay is intentionally omitted —
    no sourced per-region cohort series exists in the DB (candidate_volume is
    empty), so it is not shown rather than fabricated."""
    rows = q("""
        SELECT d.nuts3, cc.region,
               COUNT(*)                    AS n_dept,
               AVG(ri.vacancy_rate)        AS avg_vacancy,
               SUM(ri.admitted)            AS admitted,
               AVG(ri.margin_over_ebe)     AS avg_margin_ebe,
               cc.is_metro, cc.population, cc.gdp_per_capita
        FROM v_risk_inputs ri
        JOIN department d   ON ri.dept_code = d.dept_code
        JOIN city_context cc ON d.nuts3     = cc.nuts3
        WHERE ri.year = ? AND ri.category = ? AND d.nuts3 IS NOT NULL
        GROUP BY 1,2,7,8,9
        ORDER BY avg_vacancy DESC
    """, [year, category])
    return {"year": year, "category": category, "n_regions": len(rows),
            "source_note": "Eurostat NUTS-3 (tourism/GDP/population) + data.gov.gr βάσεις· "
                           "κενές = μέση πληρότητα ανά περιφερειακή ενότητα.",
            "regions": rows}


@app.get("/stats/regions/trend")
def stats_regions_trend(category: str = "ΓΕΛ90"):
    """Per-region mean vacancy across every available year — powers the animated
    «πανεπιστημιακή έρημος» map showing where public higher-ed empties over time.
    Only years present in the βάσεις series (2015–2019, 2024–2025) are returned;
    the 2020–2023 gap is a data-availability gap (no official open data), not an
    interpolation — it is left absent rather than filled."""
    rows = q("""
        SELECT ri.year, d.nuts3, cc.region, cc.is_metro,
               AVG(ri.vacancy_rate) AS avg_vacancy, COUNT(*) AS n_dept
        FROM v_risk_inputs ri
        JOIN department d    ON ri.dept_code = d.dept_code
        JOIN city_context cc ON d.nuts3      = cc.nuts3
        WHERE ri.category = ? AND d.nuts3 IS NOT NULL
        GROUP BY 1,2,3,4
        ORDER BY ri.year, avg_vacancy DESC
    """, [category])
    years = sorted({r["year"] for r in rows})
    return {"category": category, "years": years,
            "gap_note": "Κενό 2020–2023: δεν υπάρχουν επίσημα ανοικτά δεδομένα· "
                        "τα έτη λείπουν, δεν παρεμβάλλονται.",
            "source_note": "Eurostat NUTS-3 + data.gov.gr βάσεις.",
            "rows": rows}


# ── what-if simulator (Phase 3) ───────────────────────────────────────────
class WhatIfRequest(BaseModel):
    dept_code: str
    category: str = "ΓΕΛ90"
    demand_shift_pct: float = 0.0       # -15..+15 (%)
    ebe_base_shift_pct: float = 0.0     # -15..+15 (%)
    coefficient: Optional[float] = None # default: 2026 ΦΕΚ coefficient


@app.get("/whatif/{code}")
def whatif_defaults(code: str, category: str = "ΓΕΛ90"):
    if not FEATURE_PREDICTIONS:
        raise HTTPException(503, "Οι προβλέψεις είναι απενεργοποιημένες "
                                 "(feature flag PYXIDA_ENABLE_PREDICTIONS).")
    from . import whatif
    return whatif.defaults(code, category)


@app.post("/whatif")
def whatif_simulate(req: WhatIfRequest):
    if not FEATURE_PREDICTIONS:
        raise HTTPException(503, "Οι προβλέψεις είναι απενεργοποιημένες "
                                 "(feature flag PYXIDA_ENABLE_PREDICTIONS).")
    from . import whatif
    return whatif.simulate(req.dept_code, req.category,
                           req.demand_shift_pct, req.ebe_base_shift_pct,
                           req.coefficient)


# ── LLM advisor (RAG, Phase 3, feature-flagged) ───────────────────────────
class AdvisorRequest(BaseModel):
    question: str
    intent: Optional[str] = None          # "department"|"vacancies"|"nppe"|"eligibility"|"compare"
    dept: Optional[str] = None            # dept name or code (intent=department)
    family: Optional[str] = None          # program family (intent=compare)
    grades: Optional[dict] = None         # {subject: grade} (intent=eligibility)
    field_id: Optional[str] = None        # πεδίο (intent=eligibility)
    year: int = 2025
    # optional per-request LLM credentials (user brings their own key via the UI).
    # Used only to build the client for this call; never logged or persisted.
    llm_key: Optional[str] = None
    llm_backend: Optional[str] = None     # "openrouter"|"anthropic"|"openai"
    llm_model: Optional[str] = None


@app.post("/advisor")
def advisor(req: AdvisorRequest):
    # RAG retrieval itself is always available; the LLM rephrasing is optional.
    # A user who supplies their own key may use the advisor even if the server
    # did not enable the RAG feature flag (the flag gates the SERVER's own key).
    if not FEATURE_RAG and not req.llm_key:
        raise HTTPException(503, "Ο σύμβουλος (RAG) είναι απενεργοποιημένος "
                                 "(feature flag PYXIDA_ENABLE_RAG). Προσθέστε το "
                                 "δικό σας κλειδί API για να τον ενεργοποιήσετε.")
    from . import rag
    _llm = lambda: _advisor_llm(req.llm_key, req.llm_backend, req.llm_model)
    # route to the right deterministic retriever(s), then ground the answer
    intent = (req.intent or "").lower()
    ctx = rag.GroundedContext()
    if intent == "department" and req.dept:
        ctx = rag.retrieve_department(req.dept)
    elif intent == "vacancies":
        ctx = rag.retrieve_vacancy_context()
    elif intent == "nppe":
        ctx = rag.retrieve_nppe()
    elif intent == "eligibility" and req.grades and req.field_id:
        ctx = rag.retrieve_eligibility(req.grades, req.field_id, year=req.year)
    elif intent == "compare" and req.family:
        # analytical commentary on a program-family comparison uses its own
        # system prompt (analyst, not student advisor)
        ctx = rag.retrieve_comparison(req.family)
        return rag.answer(req.question or f"Σχολίασε τη σύγκριση για «{req.family}».",
                          ctx, generate_fn=_llm(),
                          system=rag.COMPARE_SYSTEM_PROMPT)
    else:
        # no structured intent: try a department name match from the free text
        ctx = rag.retrieve_department(req.question)
        if not ctx.facts:
            # tokenized fallback — extract dept/institution terms from the question
            ctx = rag.retrieve_freetext(req.question)
    return rag.answer(req.question, ctx, generate_fn=_llm())


_LLM_LAST_ERROR: Optional[str] = None   # last construction/call error, for /meta


def _advisor_llm(user_key: Optional[str] = None,
                 user_backend: Optional[str] = None,
                 user_model: Optional[str] = None):
    """Return an LLM generate_fn if a backend is configured, else None (which
    yields the deterministic grounded template — still fully grounded).

    A per-request key/backend/model (supplied by the user through the frontend)
    takes precedence over the server environment. This lets a hosted deployment
    run with NO server-side key: each visitor brings their own. The key is used
    only to construct the client for this call; it is never logged or persisted
    server-side."""
    global _LLM_LAST_ERROR
    backend = (user_backend or os.environ.get("PYXIDA_LLM_BACKEND", "template")).lower()
    # a user-supplied key with no explicit backend implies openrouter (the app default)
    if user_key and not user_backend:
        backend = "openrouter"
    if backend == "template":
        return None

    # A missing SDK or unset key must DEGRADE to the template, never 500 the
    # endpoint — return None on any setup failure, but RECORD why (so a silent
    # fallback to template is diagnosable via /meta instead of mysterious).
    try:
        if backend == "anthropic":
            import anthropic
            _k = (user_key or os.environ.get("ANTHROPIC_API_KEY","")).strip().strip('"').strip("'")
            client = anthropic.Anthropic(api_key=_k) if _k else anthropic.Anthropic()
            model = user_model or os.environ.get("PYXIDA_LLM_MODEL", "claude-3-5-haiku-latest")

            def generate_fn(system: str, user: str) -> str:
                resp = client.messages.create(
                    model=model, max_tokens=1500, temperature=0.3,
                    system=system,
                    messages=[{"role": "user", "content": user}])
                return resp.content[0].text
            return generate_fn

        if backend == "openai":
            from openai import OpenAI
            _k = (user_key or os.environ.get("OPENAI_API_KEY","")).strip().strip('"').strip("'")
            client = OpenAI(api_key=_k) if _k else OpenAI()
            model = user_model or os.environ.get("PYXIDA_LLM_MODEL", "gpt-4o-mini")

            def generate_fn(system: str, user: str) -> str:
                resp = client.chat.completions.create(
                    model=model, max_tokens=1500, temperature=0.3,
                    messages=[{"role": "system", "content": system},
                              {"role": "user", "content": user}])
                return resp.choices[0].message.content
            return generate_fn

        if backend == "openrouter":
            # OpenRouter is OpenAI-API-compatible: same SDK, custom base_url.
            # Reads OPENROUTER_API_KEY; model slug via PYXIDA_LLM_MODEL. Default is
            # Claude Sonnet 4.6 (anthropic/claude-sonnet-4.6). Slugs change over
            # time — see openrouter.ai/models for the current id.
            from openai import OpenAI
            # .strip() kills the classic trailing-newline/quote from `export KEY=...`
            # per-request key (from the frontend) wins over the server env var.
            key = (user_key or os.environ.get("OPENROUTER_API_KEY","")).strip().strip('"').strip("'")
            if not key:
                raise RuntimeError("No OpenRouter key: set OPENROUTER_API_KEY or supply one in the app")
            client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
            model = user_model or os.environ.get("PYXIDA_LLM_MODEL", "anthropic/claude-sonnet-4.6")

            def generate_fn(system: str, user: str) -> str:
                resp = client.chat.completions.create(
                    model=model, max_tokens=1500, temperature=0.3,
                    messages=[{"role": "system", "content": system},
                              {"role": "user", "content": user}])
                return resp.choices[0].message.content
            return generate_fn
    except Exception as e:
        _LLM_LAST_ERROR = f"{type(e).__name__}: {e}"
        log.warning("LLM backend '%s' setup failed (%s) — falling back to "
                    "deterministic template", backend, _LLM_LAST_ERROR)
        return None   # SDK missing or client init failed -> template fallback

    _LLM_LAST_ERROR = f"unknown backend '{backend}'"
    # unknown backend name -> safe default (deterministic template)
    return None
