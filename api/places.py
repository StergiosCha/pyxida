"""
places.py — «Σύγκριση πόλεων & ιδρυμάτων» (city-vs-city, institution-vs-institution).

THE FAIR WAY: never raw averages (those measure program mix). Every comparison is
built from WITHIN-FAMILY pairs — only program families present on BOTH sides
contribute, each as a matched pair. Two evidence layers per matchup:

  1. Outcomes (DB): per shared family, βάση 2019/2025, vacancy 2025 — paired diffs.
  2. Revealed preference (μηχανογραφικό 2024): within-candidate win rate, i.e. how
     often candidates who listed BOTH sides in the same family ranked side A above
     side B. Loaded from data/prefs_pairwise_2024.csv (cities) and
     data/prefs_inst_pairwise_2024.csv (institutions), produced by
     analysis/desirability_2024.py.
"""
from __future__ import annotations
import unicodedata
from functools import lru_cache
from pathlib import Path
from . import db
from .compare import family_key

DATA = Path(__file__).resolve().parent.parent / "data"
PREF_YEAR = 2024


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").upper().strip()


@lru_cache(maxsize=1)
def _pref_city():
    import pandas as pd
    p = DATA / "prefs_pairwise_2024.csv"
    return pd.read_csv(p) if p.exists() else None


@lru_cache(maxsize=1)
def _pref_inst():
    import pandas as pd
    p = DATA / "prefs_inst_pairwise_2024.csv"
    return pd.read_csv(p) if p.exists() else None


def _pref_winrate(table, a: str, b: str, family: str | None = None):
    """(wins_a, wins_b) in within-candidate matchups; None if no data."""
    if table is None:
        return None
    t = table
    if family is not None and "family" in t.columns:
        t = t[t["family"] == family]
    wa = int(t[(t["above"] == a) & (t["below"] == b)]["n"].sum())
    wb = int(t[(t["above"] == b) & (t["below"] == a)]["n"].sum())
    return (wa, wb) if (wa + wb) else None


def _side_rows(kind: str, key: str):
    """All ΓΕΛ90 rows (2019+2025) for a city or institution."""
    col = "lower(strip_accents(d.city))" if kind == "city" else "i.name"
    val = key.lower() if kind == "city" else key
    return db.q(f"""
        SELECT d.dept_code, d.name, d.city, i.name AS inst, a.year,
               CAST(a.base_last AS DOUBLE) AS base_last,
               CAST(a.seats_offered AS DOUBLE) AS seats,
               CAST(a.vacancies AS DOUBLE) AS vacancies
        FROM admission a JOIN department d ON d.dept_code=a.dept_code
        LEFT JOIN institution i ON i.institution_id=d.institution_id
        WHERE a.category='ΓΕΛ90' AND a.year IN (2019, {PREF_YEAR+1})
          AND {col} = ?""", [val])


def _accless_lower(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def compare_places(kind: str, a: str, b: str) -> dict:
    """kind ∈ {'city','institution'}; a, b are city names (any accents) or
    institution names exactly as stored (e.g. 'ΠΑΝ. ΠΑΤΡΩΝ')."""
    ka = _accless_lower(a) if kind == "city" else a
    kb = _accless_lower(b) if kind == "city" else b
    rows_a = _side_rows("city" if kind == "city" else "inst", ka)
    rows_b = _side_rows("city" if kind == "city" else "inst", kb)

    def index(rows):
        out = {}
        for r in rows:
            fam = family_key(r["name"])
            e = out.setdefault(fam, {})
            e[r["year"]] = r
        return out

    ia, ib = index(rows_a), index(rows_b)
    shared = sorted(set(ia) & set(ib))
    pref_tbl = _pref_city() if kind == "city" else _pref_inst()
    pa = _norm(a) if kind == "city" else a
    pb = _norm(b) if kind == "city" else b

    fams = []
    for fam in shared:
        ra25, rb25 = ia[fam].get(2025), ib[fam].get(2025)
        ra19, rb19 = ia[fam].get(2019), ib[fam].get(2019)
        if not (ra25 and rb25):
            continue
        va = (ra25["vacancies"] / ra25["seats"]) if ra25["seats"] else None
        vb = (rb25["vacancies"] / rb25["seats"]) if rb25["seats"] else None
        wr = _pref_winrate(pref_tbl, pa, pb, fam)
        fams.append({
            "family": fam,
            "a": {"dept_code": ra25["dept_code"], "name": ra25["name"],
                  "base_2019": ra19 and ra19["base_last"], "base_2025": ra25["base_last"],
                  "vacancy_rate_2025": va and round(va, 3)},
            "b": {"dept_code": rb25["dept_code"], "name": rb25["name"],
                  "base_2019": rb19 and rb19["base_last"], "base_2025": rb25["base_last"],
                  "vacancy_rate_2025": vb and round(vb, 3)},
            "d_base_2025": (ra25["base_last"] - rb25["base_last"])
                            if ra25["base_last"] is not None and rb25["base_last"] is not None else None,
            "pref_wins_a": wr and wr[0], "pref_wins_b": wr and wr[1],
        })

    total = _pref_winrate(pref_tbl, pa, pb)  # across ALL shared families

    # triangulation via common opponents — the only comparison available when the
    # two sides share no program families (e.g. Ρέθυμνο vs Ηράκλειο: disjoint
    # campuses). For each third place both sides face, report each side's win
    # share; require >=200 comparisons per side for stability.
    triangulation = []
    if pref_tbl is not None:
        agg = pref_tbl.groupby(["above", "below"])["n"].sum()
        def share_vs(x, opp):
            w = int(agg.get((x, opp), 0)); l = int(agg.get((opp, x), 0))
            return (w, l)
        opps = set()
        for (x, y) in agg.index:
            if x in (pa, pb): opps.add(y)
            if y in (pa, pb): opps.add(x)
        opps -= {pa, pb}
        for opp in sorted(opps):
            wa_, la_ = share_vs(pa, opp)
            wb_, lb_ = share_vs(pb, opp)
            if wa_ + la_ >= 200 and wb_ + lb_ >= 200:
                triangulation.append({
                    "opponent": opp,
                    "a_share": round(wa_ / (wa_ + la_), 3), "a_n": wa_ + la_,
                    "b_share": round(wb_ / (wb_ + lb_), 3), "b_n": wb_ + lb_,
                })
        triangulation.sort(key=lambda t: -(t["a_n"] + t["b_n"]))
    n_base = [f for f in fams if f["d_base_2025"] is not None]
    summary = {
        "kind": kind, "a": a, "b": b,
        "n_shared_families": len(fams),
        "mean_d_base_2025": (round(sum(f["d_base_2025"] for f in n_base) / len(n_base))
                             if n_base else None),
        "a_higher_base_count": sum(1 for f in n_base if f["d_base_2025"] > 0),
        "b_higher_base_count": sum(1 for f in n_base if f["d_base_2025"] < 0),
        "pref_total": (
            {"a_wins": total[0], "b_wins": total[1],
             "a_share": round(total[0] / (total[0] + total[1]), 3)}
            if total else None),
        "pref_source": f"μηχανογραφικό {PREF_YEAR} (within-candidate, within-family)",
        "triangulation": triangulation[:12],
        "note": ("Μόνο κοινές οικογένειες προγραμμάτων συγκρίνονται — ποτέ ακατέργαστοι "
                 "μέσοι όροι, που μετρούν σύνθεση προγραμμάτων και όχι τόπο/ίδρυμα."),
    }
    fams.sort(key=lambda f: -(abs(f["d_base_2025"]) if f["d_base_2025"] is not None else -1))
    return {"summary": summary, "families": fams}


def list_options() -> dict:
    """Cities and institutions available for the pickers."""
    cities = db.q("""SELECT DISTINCT COALESCE(d.city_display, d.city) AS label,
                            lower(strip_accents(d.city)) AS key, COUNT(*) n
                     FROM department d JOIN admission a ON a.dept_code=d.dept_code
                     WHERE a.category='ΓΕΛ90' AND a.year=2025 AND d.city IS NOT NULL
                     GROUP BY 1,2 HAVING COUNT(*) >= 2 ORDER BY n DESC""")
    insts = db.q("""SELECT i.name AS label, COUNT(DISTINCT d.dept_code) n
                    FROM institution i JOIN department d ON d.institution_id=i.institution_id
                    JOIN admission a ON a.dept_code=d.dept_code
                    WHERE a.category='ΓΕΛ90' AND a.year=2025
                    GROUP BY 1 HAVING COUNT(DISTINCT d.dept_code) >= 2 ORDER BY n DESC""")
    return {"cities": cities, "institutions": insts}
