"""
Phase 0 · crosswalk.py — department identity resolution across years.

The Ministry κωδικός τμήματος is stable for departments that persist, but the
2018->2019 ΤΕΙ absorption (ν.4485/2017 & follow-ups) retired ~185 ΤΕΙ codes,
most re-emerging as university departments under NEW codes. This module:

  1. Treats the raw dept_code as the canonical key when it appears in the
     "modern" era (2019+), i.e. survives to today.
  2. For codes that appear ONLY pre-2019 (disappeared), attempts to map them to
     a surviving department by normalised-name similarity within the same city,
     tagging the relation as 'tei_absorption' (if the old row was a ΤΕΙ) or
     'rename'/'recode' otherwise.
  3. Logs every code it cannot confidently map to `unmatched_dept`.

Confidence: 'high' (exact normalised name+city), 'medium' (token-set ratio >=
THRESH), else unmatched. No external fuzzy lib needed — uses a lightweight
token Jaccard + SequenceMatcher blend from the stdlib.
"""
from __future__ import annotations
import re, unicodedata
from difflib import SequenceMatcher
import pandas as pd

THRESH = 0.72

_GREEK_ACCENTS = str.maketrans("άέήίόύώϊϋΐΰ", "αεηιουωιυιυ")
_STOP = {"και", "της", "του", "στην", "στη", "στο", "με", "σχολη", "τμημα"}


def norm_name(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFC", str(s)).lower().translate(_GREEK_ACCENTS)
    s = re.sub(r"\(.*?\)", " ", s)                        # drop "(ΑΘΗΝΑ)" city tags
    s = re.sub(r"[^a-zα-ω0-9 ]", " ", s)
    toks = [t for t in s.split() if t not in _STOP and len(t) > 1]
    return " ".join(toks)


def city_of(name: str) -> str:
    m = re.search(r"\(([^)]+)\)", str(name or ""))
    return norm_name(m.group(1)) if m else ""


def city_display_of(name: str) -> str:
    """Display-cased city: the department name's parenthetical in proper Greek
    title-case (e.g. 'ΒΙΟΛΟΓΙΑΣ (ΗΡΑΚΛΕΙΟ)' -> 'Ηράκλειο'), for UI/labels.
    Falls back to the parenthetical as-is when accents can't be restored.
    `city_of` stays the normalised (lowercase, accent-stripped) matching key.
    """
    m = re.search(r"\(([^)]+)\)", str(name or ""))
    if not m:
        return ""
    raw = m.group(1).strip()
    # a parenthetical that is a track/category tag, not a city — skip
    if any(t in raw.upper() for t in ("ΕΠΑΛ", "ΓΕΛ", "%", "ΗΜΕΡ", "ΕΣΠΕΡ")):
        return ""
    key = norm_name(raw)
    return _CITY_TITLECASE.get(key, raw.title())


# accent-correct display forms for the cities present in the data (key = norm_name)
_CITY_TITLECASE = {
    "αθηνα": "Αθήνα", "θεσσαλονικη": "Θεσσαλονίκη", "πατρα": "Πάτρα",
    "ηρακλειο": "Ηράκλειο", "ρεθυμνο": "Ρέθυμνο", "χανια": "Χανιά",
    "ιωαννινα": "Ιωάννινα", "βολος": "Βόλος", "λαρισα": "Λάρισα",
    "πειραιας": "Πειραιάς", "αιγαλεω": "Αιγάλεω", "καλαματα": "Καλαμάτα",
    "κοζανη": "Κοζάνη", "κομοτηνη": "Κομοτηνή", "ξανθη": "Ξάνθη",
    "αλεξανδρουπολη": "Αλεξανδρούπολη", "σερρες": "Σέρρες", "καβαλα": "Καβάλα",
    "τριπολη": "Τρίπολη", "κερκυρα": "Κέρκυρα", "μυτιληνη": "Μυτιλήνη",
    "σαμος": "Σάμος", "χιος": "Χίος", "ρ+ οδος": "Ρόδος", "ροδος": "Ρόδος",
    "συρος": "Σύρος", "ναυπλιο": "Ναύπλιο", "σπαρτη": "Σπάρτη",
    "αγρινιο": "Αγρίνιο", "μεσολογγι": "Μεσολόγγι", "λαμια": "Λαμία",
    "καρδιτσα": "Καρδίτσα", "τρικαλα": "Τρίκαλα", "λευκαδα": "Λευκάδα",
    "φλωρινα": "Φλώρινα", "καστορια": "Καστοριά", "γρεβενα": "Γρεβενά",
    "πτολεμαιδα": "Πτολεμαΐδα", "εδεσσα": "Έδεσσα", "κιλκις": "Κιλκίς",
    "διδυμοτειχο": "Διδυμότειχο", "ορεστιαδα": "Ορεστιάδα",
    "καρπενησι": "Καρπενήσι", "θηβα": "Θήβα", "χαλκιδα": "Χαλκίδα",
    "λιβαδεια": "Λιβαδειά", "αμφισσα": "Άμφισσα", "αργος": "Άργος",
    "κορινθος": "Κόρινθος", "πυργος": "Πύργος", "αιγιο": "Αίγιο",
    "ναυπακτος": "Ναύπακτος", "ηγουμενιτσα": "Ηγουμενίτσα", "αρτα": "Άρτα",
    "πρεβεζα": "Πρέβεζα", "κατερινη": "Κατερίνη", "βεροια": "Βέροια",
    "ναουσα": "Νάουσα", "γιαννιτσα": "Γιαννιτσά", "δραμα": "Δράμα",
    "νιγριτα": "Νιγρίτα", "σητεια": "Σητεία", "ιεραπετρα": "Ιεράπετρα",
    "αγιοσνικολαος": "Άγιος Νικόλαος", "ναξος": "Νάξος",
}


def _sim(a: str, b: str) -> float:
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    jac = len(ta & tb) / len(ta | tb)
    seq = SequenceMatcher(None, a, b).ratio()
    return 0.5 * jac + 0.5 * seq


def build_crosswalk(gel90: pd.DataFrame):
    """Return (alias_df, unmatched_df, canonical_map).

    canonical_map: raw_code -> canonical_code (identity for survivors).
    alias_df: rows for the dept_alias table.
    unmatched_df: rows for the unmatched_dept table.
    """
    df = gel90.copy()
    years = sorted(df["year"].unique())
    modern_years = [y for y in years if y >= 2019]
    codes_by_year = {y: set(df[df.year == y].dept_code) for y in years}
    survivors = set().union(*[codes_by_year[y] for y in modern_years]) if modern_years else set()

    # latest name/city/institution per surviving code (for matching targets)
    latest = (df[df.dept_code.isin(survivors)]
              .sort_values("year").groupby("dept_code").last().reset_index())
    latest["nn"] = latest["dept_name"].map(norm_name)
    latest["cc"] = latest["dept_name"].map(city_of)

    disappeared = set(df.dept_code) - survivors
    alias_rows, unmatched_rows = [], []
    cmap = {c: c for c in survivors}                     # survivors map to themselves

    # one representative old row per disappeared code
    old = (df[df.dept_code.isin(disappeared)]
           .sort_values("year").groupby("dept_code").last().reset_index())

    for _, r in old.iterrows():
        code, nm, inst = r["dept_code"], r["dept_name"], str(r["institution"] or "")
        nn, cc = norm_name(nm), city_of(nm)
        is_tei = "ΤΕΙ" in inst.upper() or "Τ.Ε.Ι" in inst.upper()

        # City is a GATE, not a bonus. ΤΕΙ absorptions (ν.4485/2017) kept
        # departments in-region: ΤΕΙ Πειραιά -> ΠΑΔΑ (Αθήνα/Πειραιάς), never
        # a ~500km jump. Restrict candidates to the SAME city; a department
        # with a different city is not a valid absorption target. Only when the
        # old row carries no parseable city do we fall back to a name-only pool
        # (and cap that at 'medium' confidence).
        if cc:
            pool = latest[latest["cc"] == cc]
            city_gated = True
        else:
            pool = latest
            city_gated = False

        if len(pool) == 0:
            best_score, best = 0.0, None
        else:
            scored = pool.assign(score=pool["nn"].map(lambda x: _sim(nn, x)))
            best = scored.sort_values("score", ascending=False).iloc[0]
            best_score = float(best["score"])

        # confidence: same-city + near-exact name = high; same-city + >=THRESH =
        # medium; name-only fallback never exceeds medium.
        if best is not None and best_score >= 0.90 and city_gated:
            conf = "high"
        elif best is not None and best_score >= THRESH:
            conf = "medium"
        else:
            conf = None

        if conf:
            canon = best["dept_code"]
            cmap[code] = canon
            alias_rows.append({
                "alias_code": code, "alias_name": nm, "canonical_code": canon,
                "year_from": int(df[df.dept_code == code].year.min()),
                "year_to": int(df[df.dept_code == code].year.max()),
                "relation": "tei_absorption" if is_tei else "recode",
                "confidence": conf,
                "note": f"matched -> {best['dept_name']} (score {best_score:.2f}, "
                        f"city={'gated' if city_gated else 'name-only'})",
            })
        else:
            cmap[code] = code                            # keep as its own (historical-only)
            best_desc = f"best {best_score:.2f} vs '{best['dept_name']}'" if best is not None \
                        else "no same-city survivor"
            unmatched_rows.append({
                "raw_code": code, "raw_name": nm,
                "year": int(df[df.dept_code == code].year.max()),
                "category": "ΓΕΛ90",
                "reason": f"no in-city survivor match ({best_desc}); "
                          f"city='{cc}'; institution='{inst}'",
            })
    alias_df = pd.DataFrame(alias_rows)
    unmatched_df = pd.DataFrame(unmatched_rows)
    return alias_df, unmatched_df, cmap


if __name__ == "__main__":
    import warnings; warnings.filterwarnings("ignore")
    from pipeline.normalize import normalize_all
    g = normalize_all()
    g = g[g.category == "ΓΕΛ90"]
    alias, unmatched, cmap = build_crosswalk(g)
    print(f"aliases: {len(alias)} | unmatched: {len(unmatched)} | canonical codes: {len(set(cmap.values()))}")
    if len(alias):
        print("\nalias relations:", alias["relation"].value_counts().to_dict())
        print("confidence:", alias["confidence"].value_counts().to_dict())
        print("\nsample TEI-absorption aliases:")
        print(alias[alias.relation == "tei_absorption"].head(8)[["alias_code", "alias_name", "canonical_code", "confidence", "note"]].to_string(index=False))
    print(f"\nunmatched sample ({len(unmatched)}):")
    print(unmatched.head(10).to_string(index=False))
