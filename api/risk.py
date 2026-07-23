"""
«Τμήματα σε κίνδυνο» index.

Composite of three normalised signals (0..1, higher = more at-risk):
  - vacancy_rate  : κενές θέσεις / θέσεις (latest year)
  - low_demand    : 1 - fill_rate, and low βάση percentile within its field
  - merger_signal : boolean flag from the report / crosswalk (former ΤΕΙ, etc.)

Score = 0.45*vacancy + 0.35*low_fill + 0.20*merger. Transparent and tunable;
returned alongside its components so the UI can explain WHY a department scores.
"""
from __future__ import annotations

W_VAC, W_FILL, W_MERGER = 0.45, 0.35, 0.20


def risk_table(con_q, year: int = 2025, category: str = "ΓΕΛ90") -> list[dict]:
    rows = con_q("""
        SELECT a.dept_code, d.name, i.name AS institution, d.city,
               d.scientific_field, d.merger_signal,
               a.base_last, a.seats_offered, a.admitted, a.vacancies,
               a.fill_rate, a.ebe_coefficient, a.ebe_threshold
        FROM admission a
        JOIN department d ON d.dept_code = a.dept_code
        LEFT JOIN institution i ON i.institution_id = d.institution_id
        WHERE a.year = ? AND a.category = ? AND a.seats_offered > 0""",
        [year, category])
    out = []
    for r in rows:
        vac_rate = (r["vacancies"] / r["seats_offered"]) if r["seats_offered"] else 0.0
        vac_rate = max(0.0, min(1.0, vac_rate))
        fill = r["fill_rate"] if r["fill_rate"] is not None else 1.0
        low_fill = max(0.0, min(1.0, 1.0 - fill))
        merger = 1.0 if r["merger_signal"] else 0.0
        score = W_VAC * vac_rate + W_FILL * low_fill + W_MERGER * merger
        out.append({
            "dept_code": r["dept_code"], "name": r["name"],
            "institution": r["institution"], "city": r["city"],
            "scientific_field": r["scientific_field"],
            "base_last": r["base_last"], "seats_offered": r["seats_offered"],
            "vacancies": r["vacancies"], "fill_rate": round(fill, 4),
            "vacancy_rate": round(vac_rate, 4),
            "risk_score": round(score, 4),
            "components": {"vacancy": round(W_VAC * vac_rate, 4),
                           "low_fill": round(W_FILL * low_fill, 4),
                           "merger": round(W_MERGER * merger, 4)},
            "risk_band": ("υψηλός" if score >= 0.5 else
                          "μέτριος" if score >= 0.25 else "χαμηλός"),
        })
    out.sort(key=lambda x: -x["risk_score"])
    return out
