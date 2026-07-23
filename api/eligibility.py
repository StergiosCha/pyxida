"""
μόρια + ΕΒΕ eligibility engine.

Greek Panhellenic scoring (post-ν.4777/2021):
  - Each επιστημονικό πεδίο weights 4 core subjects by συντελεστές βαρύτητας
    that sum to 1.00 (on the /20 grade scale). μόρια = Σ(grade × weight) × 1000
    -> a /20000 scale, matching the βάσεις stored in `admission`.
  - ΕΒΕ (Ελάχιστη Βάση Εισαγωγής) is a HARD floor: a candidate's field-average
    (grade mean, /20) must clear each department's ΕΒΕ threshold (also /20)
    BEFORE μόρια are even compared. This engine applies ΕΒΕ as a gate, then
    ranks the passing set by μόρια vs the department's latest βάση.

The subject-weight table below is the standard 4-field scheme; it is a MODEL
INPUT, editable per Ministry Υ.Α. without touching code. Callers can override
via `field_weights=`.
"""
from __future__ import annotations
from dataclasses import dataclass, field as dc_field

# ── canonical subject keys ──────────────────────────────────────────────
# NG=Νεοελ. Γλώσσα/Λογοτεχνία, MATH=Μαθηματικά, PHYS=Φυσική, CHEM=Χημεία,
# BIO=Βιολογία, ANC=Αρχαία Ελληνικά, HIST=Ιστορία, LAT=Λατινικά,
# AOTH=Ανάπτυξη Εφαρμογών/ΑΕΠΠ, ECON=ΑΟΘ/Οικονομία
SUBJECTS = ["NG", "MATH", "PHYS", "CHEM", "BIO", "ANC", "HIST", "LAT", "AOTH", "ECON"]

SUBJECT_LABELS_EL = {
    "NG": "Νεοελληνική Γλώσσα & Λογοτεχνία", "MATH": "Μαθηματικά",
    "PHYS": "Φυσική", "CHEM": "Χημεία", "BIO": "Βιολογία",
    "ANC": "Αρχαία Ελληνικά", "HIST": "Ιστορία", "LAT": "Λατινικά",
    "AOTH": "Πληροφορική (ΑΕΠΠ)", "ECON": "Οικονομία (ΑΟΘ)",
}

# Standard weights per επιστημονικό πεδίο (weights sum to 1.00).
# Fields: 1ο Ανθρωπιστικές, 2ο Θετικές/Τεχνολογικές, 3ο Υγείας, 4ο Οικ./Πληροφ.
FIELD_WEIGHTS = {
    "1ο": {"NG": 0.30, "ANC": 0.30, "HIST": 0.25, "LAT": 0.15},
    "2ο": {"NG": 0.20, "MATH": 0.35, "PHYS": 0.30, "CHEM": 0.15},
    "3ο": {"NG": 0.20, "PHYS": 0.25, "CHEM": 0.25, "BIO": 0.30},
    "4ο": {"NG": 0.25, "MATH": 0.30, "ECON": 0.25, "AOTH": 0.20},
}

FIELD_LABELS_EL = {
    "1ο": "1ο πεδίο — Ανθρωπιστικές, Νομικές & Κοινωνικές",
    "2ο": "2ο πεδίο — Θετικές & Τεχνολογικές",
    "3ο": "3ο πεδίο — Επιστήμες Υγείας & Ζωής",
    "4ο": "4ο πεδίο — Οικονομίας & Πληροφορικής",
}


@dataclass
class Grades:
    """Subject grades on the /20 scale (missing = not sat)."""
    values: dict[str, float] = dc_field(default_factory=dict)

    def get(self, k: str) -> float | None:
        v = self.values.get(k)
        return float(v) if v is not None else None


def compute_moria(grades: Grades, field_id: str,
                  field_weights: dict | None = None) -> dict:
    """Return {moria, field_average, missing, complete} for one πεδίο.

    field_average is the plain mean of the field's weighted subjects (/20),
    used for the ΕΒΕ gate. moria is Σ(grade×weight)×1000 on the /20000 scale.
    """
    weights = (field_weights or FIELD_WEIGHTS).get(field_id)
    if weights is None:
        raise ValueError(f"unknown field_id {field_id!r}")
    tot_w, acc, present, missing = 0.0, 0.0, [], []
    for subj, w in weights.items():
        g = grades.get(subj)
        if g is None:
            missing.append(subj)
            continue
        acc += g * w
        tot_w += w
        present.append(subj)
    complete = not missing
    # μόρια on /20000 scale; if some subjects missing, scale by present weight
    moria = round(acc * 1000, 1) if complete else round((acc / tot_w) * 1000, 1) if tot_w else 0.0
    field_avg = round(sum(grades.get(s) for s in present) / len(present), 3) if present else 0.0
    return {"moria": moria, "field_average": field_avg,
            "complete": complete, "missing": missing}


def eligible_departments(con_q, grades: Grades, field_id: str,
                         year: int = 2025, category: str = "ΓΕΛ90",
                         field_weights: dict | None = None,
                         include_ineligible: bool = False) -> dict:
    """Rank departments for a candidate.

    ΕΒΕ gate: candidate field_average (/20) >= dept ΕΒΕ threshold (/20).
    Then compare μόρια to the department's βάση for `year`.
    Returns {profile, eligible:[...], blocked_by_ebe:[...]}.
    """
    m = compute_moria(grades, field_id, field_weights)
    moria = m["moria"]
    fa = m["field_average"]

    rows = con_q("""
        SELECT a.dept_code, d.name, i.name AS institution, d.city,
               a.base_last, a.seats_offered, a.vacancies, a.fill_rate,
               a.ebe_coefficient, a.ebe_threshold
        FROM admission a
        JOIN department d ON d.dept_code = a.dept_code
        LEFT JOIN institution i ON i.institution_id = d.institution_id
        WHERE a.year = ? AND a.category = ? AND a.base_last IS NOT NULL
        ORDER BY a.base_last DESC""", [year, category])

    eligible, blocked = [], []
    for r in rows:
        ebe_thr20 = (r["ebe_threshold"] / 1000.0) if r["ebe_threshold"] else None
        passes_ebe = (ebe_thr20 is None) or (fa >= ebe_thr20)
        margin = round(moria - r["base_last"], 1) if r["base_last"] is not None else None
        item = {
            "dept_code": r["dept_code"], "name": r["name"],
            "institution": r["institution"], "city": r["city"],
            "base_last": r["base_last"], "your_moria": moria,
            "margin": margin,                       # + => above last year's βάση
            "ebe_threshold": ebe_thr20, "your_field_avg": fa,
            "ebe_coefficient": r["ebe_coefficient"],
            "vacancies": r["vacancies"], "fill_rate": r["fill_rate"],
            "passes_ebe": passes_ebe,
            "likely_admit": bool(passes_ebe and margin is not None and margin >= 0),
        }
        if passes_ebe:
            eligible.append(item)
        elif include_ineligible:
            blocked.append(item)
    # rank eligible by margin desc (safest first)
    eligible.sort(key=lambda x: (x["margin"] is None, -(x["margin"] or -1e9)))
    return {
        "profile": {"field_id": field_id, "field_label": FIELD_LABELS_EL.get(field_id),
                    "moria": moria, "field_average": fa,
                    "complete": m["complete"], "missing": m["missing"],
                    "year_compared": year, "category": category},
        "eligible": eligible,
        "blocked_by_ebe": blocked,
        "n_eligible": len(eligible),
        "n_likely": sum(1 for e in eligible if e["likely_admit"]),
    }
