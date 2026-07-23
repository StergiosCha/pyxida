"""
whatif.py — Προσομοιωτής σεναρίων («τι-θα-γινόταν-αν») για το 2026.

Every number is derived from DB rows — nothing invented:
  • baseline 2026 forecast band  ........ prediction table (carry-forward + PI)
  • 2026 ΕΒΕ coefficient  ............... dept_ebe_coef (ΥΑ Φ.253/160742/Α5,
                                          ΦΕΚ Β' 6782/16-12-2025)
  • field ΕΒΕ base (latest observed) .... field_ebe (2025)
The user supplies ASSUMPTIONS (sliders): a shift on the field ΕΒΕ base (proxy
for candidate performance / volume in the πεδίο) and a shift on demand (proxy
for candidate-volume pressure on this department). Outputs are always bands,
never single certainties, and the response labels every derived figure with its
assumption so the UI can render provenance honestly.

Scale note: ΕΒΕ bases/thresholds are on the /20 school-grade scale; βάσεις are
μόρια (/20400 for ΓΕΛ90 with weights). We expose the threshold both on /20 and
the ×1000 μόρια approximation the rest of the app uses for like-for-like lines.
"""
from __future__ import annotations
from typing import Optional
from . import db

LATEST_FIELD_EBE_YEAR = 2025   # last year with observed field bases
TARGET_YEAR = 2026


def dept_field(code: str) -> Optional[str]:
    r = db.q1("SELECT scientific_field FROM department WHERE dept_code=?", [code])
    return r["scientific_field"] if r else None


def defaults(code: str, category: str = "ΓΕΛ90") -> dict:
    """Baseline inputs the UI initialises its sliders from."""
    pred = db.q1("""SELECT point, lower_80, upper_80, lower_95, upper_95
                    FROM prediction WHERE dept_code=? AND category=? AND target_year=?""",
                 [code, category, TARGET_YEAR])
    coef = db.q1("""SELECT ebe_coefficient, ebe_special_coefficient, source_note
                    FROM dept_ebe_coef WHERE dept_code=? AND year=?""",
                 [code, TARGET_YEAR])
    fld = dept_field(code)
    base = db.q1("SELECT ebe_base, field_mean FROM field_ebe WHERE year=? AND field=?",
                 [LATEST_FIELD_EBE_YEAR, fld]) if fld else None
    hist = db.q("""SELECT year, base_last, ebe_threshold FROM admission
                   WHERE dept_code=? AND category=? ORDER BY year""", [code, category])
    return {
        "dept_code": code, "category": category, "target_year": TARGET_YEAR,
        "field": fld,
        "prediction": pred,                       # None => no forecast for this dept
        "coefficient_2026": (coef or {}).get("ebe_coefficient"),
        "coefficient_source": (coef or {}).get("source_note"),
        "field_ebe_base_latest": (base or {}).get("ebe_base"),
        "field_ebe_base_year": LATEST_FIELD_EBE_YEAR if base else None,
        "history": hist,
    }


def simulate(code: str, category: str = "ΓΕΛ90",
             demand_shift_pct: float = 0.0,
             ebe_base_shift_pct: float = 0.0,
             coefficient: Optional[float] = None) -> dict:
    """Apply the two assumption sliders (+ optional coefficient override) to the
    grounded baseline. demand_shift_pct / ebe_base_shift_pct are e.g. -5..+5."""
    d = defaults(code, category)
    out = {"inputs": {"demand_shift_pct": demand_shift_pct,
                      "ebe_base_shift_pct": ebe_base_shift_pct,
                      "coefficient": coefficient},
           "defaults": d}
    # clamp assumptions to a sane window so the UI cannot produce absurd bands
    ds = max(-15.0, min(15.0, float(demand_shift_pct))) / 100.0
    es = max(-15.0, min(15.0, float(ebe_base_shift_pct))) / 100.0
    coef = coefficient if coefficient is not None else d["coefficient_2026"]
    if coef is not None:
        coef = max(0.80, min(1.20, float(coef)))

    # 1. demand-adjusted forecast band (multiplicative shift on all quantiles)
    p = d["prediction"]
    if p and p.get("point") is not None:
        out["adjusted_prediction"] = {
            k: round(p[k] * (1 + ds)) for k in
            ("point", "lower_80", "upper_80", "lower_95", "upper_95")
            if p.get(k) is not None}
    else:
        out["adjusted_prediction"] = None

    # 2. ΕΒΕ floor estimate: threshold = field_base × coefficient
    fb = d["field_ebe_base_latest"]
    if fb is not None and coef is not None:
        thr20 = fb * (1 + es) * coef
        out["ebe_floor_est"] = {
            "threshold_20": round(thr20, 2),          # /20 school-grade scale
            "threshold_moria_approx": round(thr20 * 1000),  # ×1000 helper scale
            "coefficient_used": coef,
            "field_base_assumed": round(fb * (1 + es), 3),
            "note": (f"Βάση πεδίου {d['field']} {d['field_ebe_base_year']} "
                     f"({fb}) × συντ. {coef} — υπόθεση μεταβολής "
                     f"{ebe_base_shift_pct:+.0f}%"),
        }
        # 3. is the department ΕΒΕ-bound under these assumptions?
        ap = out["adjusted_prediction"]
        if ap:
            out["ebe_bound"] = bool(ap["lower_80"] < out["ebe_floor_est"]["threshold_moria_approx"])
    else:
        out["ebe_floor_est"] = None

    out["disclaimer"] = ("Σενάριο υποθέσεων — όχι πρόβλεψη. Τα διαστήματα "
                         "προέρχονται από το carry-forward μοντέλο και "
                         "μετατοπίζονται με την υπόθεση ζήτησης που ορίσατε.")
    return out
