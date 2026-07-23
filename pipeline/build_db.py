"""
Phase 0 · build_db.py — one command rebuilds the DuckDB from /data/raw.

    python -m pipeline.build_db            # rebuild pyxida.duckdb from raw

Pipeline: normalize -> crosswalk -> attach ΕΒΕ -> load schema.sql -> insert.
Idempotent: drops & recreates the .duckdb each run. Every fact row carries a
source_id resolved from the fetch manifest.
"""
from __future__ import annotations
import warnings, re
from pathlib import Path
import pandas as pd
import duckdb

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "pyxida.duckdb"
SCHEMA = ROOT / "schema.sql"

from pipeline.normalize import normalize_all
from pipeline.crosswalk import build_crosswalk, norm_name, city_of, city_display_of
from pipeline.context import load_context
from pipeline.ebe import load_all_ebe, field_ebe_table, coef_by_year

FIELD_CANON = {"1": "1ο", "2": "2ο", "3": "3ο", "4": "4ο",
               "1ο": "1ο", "2ο": "2ο", "3ο": "3ο", "4ο": "4ο"}

_CITY2NUTS: dict = {}   # populated by build() from pipeline.context.load_context()


def _sources_from_manifest():
    mpath = RAW / "fetch_manifest.csv"
    m = pd.read_csv(mpath)
    rows = []
    for sid, (_, r) in enumerate(m.iterrows(), start=1):
        rows.append({
            "source_id": sid, "name": "data.gov.gr (minedu)",
            "kind": "official" if r["status"] in ("fetched", "cached") else "gap",
            "url": r.get("url"), "local_path": r.get("path"),
            "retrieved_at": None, "checksum_sha256": r.get("sha256"),
            "license": "open data", "is_official": True,
            "note": f"{r['kind']} {int(r['year'])} [{r['status']}]",
        })
    # map (kind, year) -> source_id for fact provenance
    idx = {(r["kind"], int(rr["year"])): r["source_id"]
           for r, (_, rr) in zip(rows, m.iterrows())}
    return pd.DataFrame(rows), idx, m


def build():
    # 0. regional context (Eurostat NUTS-3) + city→region map for the join
    global _CITY2NUTS
    city_context_df, _CITY2NUTS = load_context()

    # 1. normalize + crosswalk on the mainstream ΓΕΛ90 spine (all cats retained)
    allcat = normalize_all()
    gel90 = allcat[allcat.category == "ΓΕΛ90"].copy()
    alias_df, unmatched_df, cmap = build_crosswalk(gel90)

    # apply canonical mapping to ALL categories
    allcat["canonical_code"] = allcat["dept_code"].map(lambda c: cmap.get(c, c))

    # 2. ΕΒΕ
    dept_ebe = load_all_ebe()
    fld_ebe = field_ebe_table(dept_ebe)
    ebe_map = {(r.dept_code, r.year): r for r in dept_ebe.itertuples()}

    # 3. sources / provenance
    src_df, src_idx, _ = _sources_from_manifest()

    def src_for(year):
        return src_idx.get(("base", year)) or 1

    # 4. institution + department dimension (from latest appearance)
    latest = (gel90.sort_values("year").groupby("dept_code").last().reset_index())
    latest["canonical_code"] = latest["dept_code"].map(lambda c: cmap.get(c, c))
    # collapse to canonical departments
    canon = (allcat.sort_values("year")
             .groupby("canonical_code").last().reset_index())
    inst_names = sorted(set(allcat["institution"].dropna().astype(str)))
    inst_df = pd.DataFrame({
        "institution_id": range(1, len(inst_names) + 1),
        "name": inst_names,
    })
    inst_df["short_name"] = inst_df["name"]
    inst_df["inst_type"] = inst_df["name"].apply(
        lambda s: "former_ΤΕΙ" if "ΤΕΙ" in s.upper() else "ΑΕΙ")
    inst_df["is_state"] = True
    inst_df["city"] = None
    inst_df["region"] = None
    inst_df["founded_year"] = None
    inst_df["parent_name"] = None
    inst_df["note"] = None
    inst_id = dict(zip(inst_df["name"], inst_df["institution_id"]))

    dept_rows = []
    for _, r in canon.iterrows():
        code = r["canonical_code"]
        yrs = allcat[allcat.canonical_code == code]["year"]
        # attach ebe field if present
        efield = None
        for y in (2025, 2024):
            e = ebe_map.get((code, y))
            if e is not None and pd.notna(getattr(e, "ebe_field", None)):
                efield = FIELD_CANON.get(str(e.ebe_field).strip(), None)
                break
        dept_rows.append({
            "dept_code": code, "name": r["dept_name"],
            "institution_id": inst_id.get(str(r["institution"]), None),
            "city": city_of(r["dept_name"]) or None,
            "city_display": city_display_of(r["dept_name"]) or None,
            "nuts3": _CITY2NUTS.get(city_of(r["dept_name"]) or "", None),
            "scientific_field": efield,
            "status": "active" if 2025 in set(yrs) or 2024 in set(yrs) else "abolished",
            "status_year": None, "merger_signal": False,
            "first_seen_year": int(yrs.min()), "last_seen_year": int(yrs.max()),
            "note": None,
        })
    dept_df = pd.DataFrame(dept_rows)

    # 5. admission facts (all categories), remapped to canonical codes
    fact = allcat.copy()
    fact["dept_code"] = fact["canonical_code"]
    # collapse duplicate canonical rows per (code, year, cat): keep max base
    fact = (fact.sort_values("grade_last", ascending=False, na_position="last")
                .drop_duplicates(["dept_code", "year", "category"], keep="first"))
    # attach ebe coefficient/threshold
    def ebe_coef(row):
        e = ebe_map.get((row["dept_code"], row["year"]))
        return getattr(e, "ebe_coefficient", None) if e is not None else None
    def ebe_thr(row):
        e = ebe_map.get((row["dept_code"], row["year"]))
        if e is None:
            return None
        v = getattr(e, "ebe_threshold_gel", None)
        return v * 1000 if pd.notna(v) else None          # /20 -> /20000 scale
    fact["ebe_coefficient"] = fact.apply(ebe_coef, axis=1)
    fact["ebe_threshold"] = fact.apply(ebe_thr, axis=1)
    fact["source_id"] = fact["year"].map(src_for)
    fact["vacancy_cause"] = None
    fact["provenance_note"] = fact["year"].map(lambda y: f"data.gov.gr base {y}")
    admission_df = fact[[
        "dept_code", "year", "category", "grade_last", "grade_first",
        "seats_offered", "admitted", "vacancies", "fill_rate",
        "ebe_coefficient", "ebe_threshold", "vacancy_cause",
        "source_id", "provenance_note",
    ]].rename(columns={"grade_last": "base_last", "grade_first": "grade_first"})
    admission_df["seats_offered"] = admission_df["seats_offered"].astype("Int64")
    admission_df["admitted"] = admission_df["admitted"].astype("Int64")
    admission_df["vacancies"] = admission_df["vacancies"].astype("Int64")

    # 6. field_ebe rows
    fld_rows = []
    for _, r in fld_ebe.iterrows():
        fld_rows.append({"year": int(r["year"]),
                         "field": FIELD_CANON.get(str(r["field"]).strip(), str(r["field"])),
                         "field_mean": round(r["ebe_base"] / 0.80, 3),
                         "ebe_base": r["ebe_base"], "source_id": None})
    field_ebe_df = pd.DataFrame(fld_rows)

    # 7. write DB
    if DB.exists():
        DB.unlink()
    con = duckdb.connect(str(DB))
    con.execute(SCHEMA.read_text())
    con.register("src_df", src_df); con.execute("INSERT INTO source SELECT * FROM src_df")
    con.register("inst_df", inst_df[["institution_id", "name", "short_name", "inst_type",
        "is_state", "city", "region", "founded_year", "parent_name", "note"]])
    con.execute("INSERT INTO institution SELECT * FROM inst_df")
    con.register("dept_df", dept_df); con.execute("INSERT INTO department SELECT * FROM dept_df")
    con.register("ctx_df", city_context_df[["nuts3", "region", "tourism_nights",
        "population", "tourism_per_capita", "gdp_per_capita", "is_metro",
        "source_note"]])
    con.execute("INSERT INTO city_context SELECT * FROM ctx_df")
    if len(alias_df):
        alias_df = alias_df.reset_index(drop=True)
        alias_df.insert(0, "alias_id", range(1, len(alias_df) + 1))
        con.register("alias_df", alias_df)
        con.execute("""INSERT INTO dept_alias
            SELECT alias_id, alias_code, alias_name, canonical_code,
                   year_from, year_to, relation, confidence, note FROM alias_df""")
    if len(unmatched_df):
        unmatched_df = unmatched_df.copy(); unmatched_df["source_id"] = None
        con.register("un_df", unmatched_df)
        con.execute("""INSERT INTO unmatched_dept
            SELECT raw_code, raw_name, year, category, source_id, reason FROM un_df""")
    con.register("adm_df", admission_df); con.execute("INSERT INTO admission SELECT * FROM adm_df")
    if len(field_ebe_df):
        con.register("fld_df", field_ebe_df)
        con.execute("INSERT INTO field_ebe SELECT year, field, field_mean, ebe_base, source_id FROM fld_df")
    coef_df = coef_by_year()
    if len(coef_df):
        con.register("coef_df", coef_df)
        con.execute("""INSERT INTO dept_ebe_coef
            SELECT year, dept_code, ebe_coefficient, ebe_special_coefficient, source_note
            FROM coef_df""")
    con.close()
    return {
        "departments": len(dept_df), "institutions": len(inst_df),
        "admission_rows": len(admission_df), "aliases": len(alias_df),
        "unmatched": len(unmatched_df), "field_ebe": len(field_ebe_df),
        "dept_ebe": len(dept_ebe), "dept_ebe_coef": len(coef_df), "city_context": len(city_context_df),
    }


if __name__ == "__main__":
    stats = build()
    print("DB built ->", DB)
    for k, v in stats.items():
        print(f"  {k:16} {v}")
