"""Load candidate-preference statistics (Στατιστικά Προτιμήσεων Μηχανογραφικών)
into the pyxida DuckDB as a `preference` table.

First-preference count = demand intensity, independent of who was admitted.
Source: data.gov.gr CKAN, 4_statistika_protimiseon_gel_epal_{year}.xlsx (ΓΕΛ rows).
Idempotent: DROP + CREATE. Run after build_db (department table must exist).

    python -m pipeline.load_preferences
"""
import os, duckdb, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "pyxida.duckdb")
AUX = os.path.join(ROOT, "data", "raw", "data.gov.gr", "aux")
FILES = {
    2024: "statistika-michanografikon-deltion-ypopsifion-gel-epal-stis-panelladikes-exetaseis-2024/4_statistika_protimiseon_gel_epal_2024.xlsx",
    2025: "statistika-michanografikon-deltion-ypopsifion-gel-epal-stis-panelladikes-exetaseis-2025/4_statistika_protimiseon_gel_epal_2025.xlsx",
}
COLMAP = {"ΕΠΙΛΟΓΗ": "choice", "ΙΔΡΥΜΑ": "inst", "ΚΩΔΙΚΟΣ ΣΧΟΛΗΣ": "dept_code",
          "ΣΧΟΛΗ": "name", "ΠΡΟΤΙΜΗΣΗ 1Η": "pref1", "ΠΡΟΤΙΜΗΣΗ 2Η": "pref2",
          "ΠΡΟΤΙΜΗΣΗ 3Η": "pref3", "ΠΡΟΤΙΜΗΣΗ (ΑΛΛΗ ΣΕΙΡΑ)": "pref_other",
          "ΠΡΟΤΙΜΗΣΗ (ΣΥΝΟΛΙΚΑ)": "pref_total"}


def _load_year(path, year):
    raw = pd.read_excel(path, header=1)
    raw = raw.rename(columns={c: c.strip() for c in raw.columns})
    df = raw[[c for c in COLMAP if c in raw.columns]].rename(columns=COLMAP)
    df = df[df.dept_code.notna()].copy()
    df["dept_code"] = df.dept_code.astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
    for c in ["pref1", "pref2", "pref3", "pref_other", "pref_total"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df.choice.astype(str).str.contains("ΓΕΛ")]          # ΓΕΛ backbone
    df["year"] = year
    df["source_file"] = os.path.basename(path)
    return df[["dept_code", "year", "name", "pref1", "pref2", "pref3",
               "pref_other", "pref_total", "source_file"]]


def main():
    frames = [_load_year(os.path.join(AUX, rel), yr) for yr, rel in FILES.items()
              if os.path.exists(os.path.join(AUX, rel))]
    if not frames:
        print("No preference files found under", AUX)
        return
    pref = pd.concat(frames, ignore_index=True)
    con = duckdb.connect(DB)
    con.execute("DROP TABLE IF EXISTS preference")
    con.execute("""CREATE TABLE preference (
        dept_code VARCHAR, year INTEGER, name VARCHAR,
        pref1 INTEGER, pref2 INTEGER, pref3 INTEGER,
        pref_other INTEGER, pref_total INTEGER, source_file VARCHAR)""")
    con.register("pref_df", pref)
    con.execute("INSERT INTO preference SELECT * FROM pref_df")
    # coverage against department spine
    n = con.execute("SELECT COUNT(*) FROM preference").fetchone()[0]
    matched = con.execute("""SELECT COUNT(DISTINCT p.dept_code) FROM preference p
        JOIN department d ON d.dept_code = p.dept_code""").fetchone()[0]
    yrs = con.execute("SELECT year, COUNT(*) FROM preference GROUP BY 1 ORDER BY 1").fetchall()
    con.close()
    print(f"preference table: {n} rows, {matched} dept codes matched to department spine")
    print("by year:", dict(yrs))


if __name__ == "__main__":
    main()
