"""
compare.py — program-family comparison ("Σύγκριση προγραμμάτων").

A *program family* is a department name with its city parenthetical and any
duplicate-name tail removed:  "ΦΙΛΟΛΟΓΙΑΣ (ΡΕΘΥΜΝΟ)" and "ΦΙΛΟΛΟΓΙΑΣ (ΑΘΗΝΑ)"
share the family "ΦΙΛΟΛΟΓΙΑΣ", while "ΙΤΑΛΙΚΗΣ ΓΛΩΣΣΑΣ ΚΑΙ ΦΙΛΟΛΟΓΙΑΣ" is its own
family. This groups like-for-like degrees across cities so the same program can
be compared head-to-head (the ΕΒΕ effect is only interpretable within a family).

All numbers come from the DB; nothing is invented. Used by /compare endpoints
and by the RAG advisor (intent=compare) for a grounded LLM commentary.
"""
from __future__ import annotations
import re
from . import db

PRE_YEAR = 2019   # last pre-ΕΒΕ year with data
POST_YEAR = 2025  # latest year


# Latin capitals that appear as homoglyphs inside Greek department names in the
# raw files (e.g. "\u039c\u0391\u0398\u0397\u039c\u0391\u03a4\u0399\u039a\u03a9\u039d KAI \u0395\u03a6\u0391\u03a1\u039c\u039f\u03a3\u039c\u0395\u039d\u03a9\u039d..." with a Latin K/A/I) \u2014 they
# silently split families, so normalise them to their Greek lookalikes.
_HOMOGLYPHS = str.maketrans("ABEZHIKMNOPTYX", "\u0391\u0392\u0395\u0396\u0397\u0399\u039a\u039c\u039d\u039f\u03a1\u03a4\u03a5\u03a7")

# Curated merges (audited 2026-07 against the crosswalk alias table): official
# renames / name variants of the SAME degree that the purely name-based key
# would otherwise split. Keys and values are post-normalisation family keys.
_PRESCHOOL = "\u03a0\u0391\u0399\u0394\u0391\u0393\u03a9\u0393\u0399\u039a\u03a9\u039d \u03a0\u03a1\u039f\u03a3\u03a7\u039f\u039b\u0399\u039a\u0397\u03a3 \u0395\u039a\u03a0\u0391\u0399\u0394\u0395\u03a5\u03a3\u0397\u03a3"
_FAMILY_MERGES = {
    # Political science: same discipline (all πεδίο 1ο), split only by official-title
    # variants (singular/plural, and "και Δημόσιας Διοίκησης / και Ιστορίας /
    # και Διεθνών Σχέσεων" tails). Canonicalise to ΠΟΛΙΤΙΚΗΣ ΕΠΙΣΤΗΜΗΣ so Athens
    # (ΕΚΠΑ + Παντείου), Θεσσαλονίκη, Κομοτηνή, Ρέθυμνο, Κόρινθος compare head-to-head.
    "ΠΟΛΙΤΙΚΩΝ ΕΠΙΣΤΗΜΩΝ": "ΠΟΛΙΤΙΚΗΣ ΕΠΙΣΤΗΜΗΣ",
    "ΠΟΛΙΤΙΚΗΣ ΕΠΙΣΤΗΜΗΣ ΚΑΙ ΔΗΜΟΣΙΑΣ ΔΙΟΙΚΗΣΗΣ": "ΠΟΛΙΤΙΚΗΣ ΕΠΙΣΤΗΜΗΣ",
    "ΠΟΛΙΤΙΚΗΣ ΕΠΙΣΤΗΜΗΣ ΚΑΙ ΙΣΤΟΡΙΑΣ": "ΠΟΛΙΤΙΚΗΣ ΕΠΙΣΤΗΜΗΣ",
    "ΠΟΛΙΤΙΚΗΣ ΕΠΙΣΤΗΜΗΣ ΚΑΙ ΔΙΕΘΝΩΝ ΣΧΕΣΕΩΝ": "ΠΟΛΙΤΙΚΗΣ ΕΠΙΣΤΗΜΗΣ",
    # singular/plural variant of the same program (\u039a\u03b1\u03bb\u03b1\u03bc\u03ac\u03c4\u03b1 vs \u0398\u03b5\u03c3/\u03bd\u03af\u03ba\u03b7-\u03a3\u03b7\u03c4\u03b5\u03af\u03b1)
    "\u0395\u03a0\u0399\u03a3\u03a4\u0397\u039c\u0397\u03a3 \u0394\u0399\u0391\u03a4\u03a1\u039f\u03a6\u0397\u03a3 \u039a\u0391\u0399 \u0394\u0399\u0391\u0399\u03a4\u039f\u039b\u039f\u0393\u0399\u0391\u03a3": "\u0395\u03a0\u0399\u03a3\u03a4\u0397\u039c\u03a9\u039d \u0394\u0399\u0391\u03a4\u03a1\u039f\u03a6\u0397\u03a3 \u039a\u0391\u0399 \u0394\u0399\u0391\u0399\u03a4\u039f\u039b\u039f\u0393\u0399\u0391\u03a3",
    # \u039f\u0394\u0395 (\u039f\u03a0\u0391/\u03a0\u0391\u039c\u0391\u039a naming) vs \u0394\u0395 \u2014 like-for-like business degree
    "\u039f\u03a1\u0393\u0391\u039d\u03a9\u03a3\u0397\u03a3 \u039a\u0391\u0399 \u0394\u0399\u039f\u0399\u039a\u0397\u03a3\u0397\u03a3 \u0395\u03a0\u0399\u03a7\u0395\u0399\u03a1\u0397\u03a3\u0395\u03a9\u039d": "\u0394\u0399\u039f\u0399\u039a\u0397\u03a3\u0397\u03a3 \u0395\u03a0\u0399\u03a7\u0395\u0399\u03a1\u0397\u03a3\u0395\u03a9\u039d",
    # \u03bd\u03b7\u03c0\u03b9\u03b1\u03b3\u03c9\u03b3\u03bf\u03af: every university uses a different official title
    "\u0395\u03a0\u0399\u03a3\u03a4\u0397\u039c\u03a9\u039d \u03a4\u0397\u03a3 \u0395\u039a\u03a0\u0391\u0399\u0394\u0395\u03a5\u03a3\u0397\u03a3 \u039a\u0391\u0399 \u03a4\u0397\u03a3 \u0391\u0393\u03a9\u0393\u0397\u03a3 \u03a3\u03a4\u0397\u039d \u03a0\u03a1\u039f\u03a3\u03a7\u039f\u039b\u0399\u039a\u0397 \u0397\u039b\u0399\u039a\u0399\u0391": _PRESCHOOL,
    "\u0395\u039a\u03a0\u0391\u0399\u0394\u0395\u03a5\u03a3\u0397\u03a3 \u039a\u0391\u0399 \u0391\u0393\u03a9\u0393\u0397\u03a3 \u03a3\u03a4\u0397\u039d \u03a0\u03a1\u039f\u03a3\u03a7\u039f\u039b\u0399\u039a\u0397 \u0397\u039b\u0399\u039a\u0399\u0391": _PRESCHOOL,
    "\u0395\u03a0\u0399\u03a3\u03a4\u0397\u039c\u03a9\u039d \u03a4\u0397\u03a3 \u0395\u039a\u03a0\u0391\u0399\u0394\u0395\u03a5\u03a3\u0397\u03a3 \u03a3\u03a4\u0397\u039d \u03a0\u03a1\u039f\u03a3\u03a7\u039f\u039b\u0399\u039a\u0397 \u0397\u039b\u0399\u039a\u0399\u0391": _PRESCHOOL,
    "\u0395\u03a0\u0399\u03a3\u03a4\u0397\u039c\u03a9\u039d \u03a0\u03a1\u039f\u03a3\u03a7\u039f\u039b\u0399\u039a\u0397\u03a3 \u0391\u0393\u03a9\u0393\u0397\u03a3 \u039a\u0391\u0399 \u0395\u039a\u03a0\u0391\u0399\u0394\u0395\u03a5\u03a3\u0397\u03a3": _PRESCHOOL,
    "\u0395\u03a0\u0399\u03a3\u03a4\u0397\u039c\u03a9\u039d \u03a4\u0397\u03a3 \u03a0\u03a1\u039f\u03a3\u03a7\u039f\u039b\u0399\u039a\u0397\u03a3 \u0391\u0393\u03a9\u0393\u0397\u03a3 \u039a\u0391\u0399 \u0395\u039a\u03a0\u0391\u0399\u0394\u0395\u03a5\u03a4\u0399\u039a\u039f\u03a5 \u03a3\u03a7\u0395\u0394\u0399\u0391\u03a3\u039c\u039f\u03a5": _PRESCHOOL,
    "\u03a0\u0391\u0399\u0394\u0391\u0393\u03a9\u0393\u0399\u039a\u039f \u03a0\u03a1\u039f\u03a3\u03a7\u039f\u039b\u0399\u039a\u0397\u03a3 \u0395\u039a\u03a0\u0391\u0399\u0394\u0395\u03a5\u03a3\u0397\u03a3": _PRESCHOOL,
}


def family_key(name: str) -> str:
    """Program family = name minus (CITY) and any ' - duplicate' tail, upper-cased.
    Military-school parentheticals (\u03a3\u03a3\u0391\u03a3 etc.) are kept so e.g. the \u03a3\u03a3\u0391\u03a3
    \u03a0\u03bb\u03b7\u03c1\u03bf\u03c6\u03bf\u03c1\u03b9\u03ba\u03ae\u03c2 stays distinct from the civilian \u03a0\u03bb\u03b7\u03c1\u03bf\u03c6\u03bf\u03c1\u03b9\u03ba\u03ae\u03c2 family."""
    n = name.replace("(\u03a3\u03a3\u0391\u03a3)", "\u03a3\u03a3\u0391\u03a3")            # keep the military marker
    n = re.sub(r"\s*\([^)]*\)\s*", " ", n)         # drop city parenthetical
    n = re.split(r"\s+[-\u2013]\s+", n)[0]         # drop ' - dup name' tail
    n = re.sub(r"\s+", " ", n).strip().upper().translate(_HOMOGLYPHS)
    return _FAMILY_MERGES.get(n, n)


def list_families(min_n: int = 2, category: str = "ΓΕΛ90", year: int = POST_YEAR):
    """Families present in `year` with >= min_n departments, for the dropdown."""
    rows = db.q("""SELECT d.name FROM admission a JOIN department d ON d.dept_code=a.dept_code
                   WHERE a.category=? AND a.year=?""", [category, year])
    counts: dict[str, int] = {}
    for r in rows:
        counts[family_key(r["name"])] = counts.get(family_key(r["name"]), 0) + 1
    out = [{"family": k, "n_departments": c} for k, c in counts.items() if c >= min_n]
    return sorted(out, key=lambda x: (-x["n_departments"], x["family"]))


def compare_family(family: str, category: str = "ΓΕΛ90"):
    """All departments in a family, with pre/post-ΕΒΕ trajectory + vacancy."""
    fam = family.strip().upper()
    rows = db.q("""
        SELECT a.dept_code, d.name, COALESCE(d.city_display, d.city) AS city,
               d.scientific_field AS field,
               a.base_last AS base_post, a.seats_offered, a.admitted, a.vacancies,
               a.fill_rate, a.ebe_coefficient, a.ebe_threshold
        FROM admission a JOIN department d ON d.dept_code=a.dept_code
        WHERE a.category=? AND a.year=?""", [category, POST_YEAR])
    pre = {r["dept_code"]: r["base_last"] for r in db.q(
        "SELECT dept_code, base_last FROM admission WHERE category=? AND year=?",
        [category, PRE_YEAR])}
    fc = {r["dept_code"]: r for r in db.q(
        "SELECT dept_code, point, lower_80, upper_80 FROM prediction")}
    depts = []
    for r in rows:
        if family_key(r["name"]) != fam:
            continue
        code = r["dept_code"]
        vr = (r["vacancies"] / r["seats_offered"]) if r["seats_offered"] else None
        f = fc.get(code)
        depts.append({
            "dept_code": code, "name": r["name"], "city": r["city"],
            "field": r["field"],
            "base_2019": pre.get(code), "base_2025": r["base_post"],
            "seats": r["seats_offered"], "admitted": r["admitted"],
            "vacancies": r["vacancies"],
            "vacancy_rate": round(vr, 3) if vr is not None else None,
            "ebe_coefficient": r["ebe_coefficient"],
            "forecast_2026": (round(f["point"]) if f else None),
            "forecast_2026_lo80": (round(f["lower_80"]) if f else None),
            "forecast_2026_hi80": (round(f["upper_80"]) if f else None),
        })
    depts.sort(key=lambda d: (d["vacancy_rate"] is None, -(d["vacancy_rate"] or 0)))
    # family-level summary
    seats = sum(d["seats"] or 0 for d in depts)
    vac = sum(d["vacancies"] or 0 for d in depts)
    with_pre = [d for d in depts if d["base_2019"] is not None]
    summary = {
        "family": fam, "n_departments": len(depts),
        "total_seats": seats, "total_vacancies": vac,
        "vacancy_rate": round(vac / seats, 3) if seats else None,
        "worst": (depts[0]["city"] if depts else None),
        "best": (depts[-1]["city"] if depts else None),
    }
    return {"summary": summary, "departments": depts}
