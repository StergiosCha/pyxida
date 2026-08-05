#!/usr/bin/env python3
"""Φορτώνει τις βάσεις 2026 (μόνο βάσεις) στην Πυξίδα.

Το data.gov.gr ΔΕΝ έχει dataset βάσεων 2026 (έλεγχος 7.144 datasets, 05/08/2026).
Πηγή: aeitei.gr, mirror υπουργικών αρχείων -> ΑΝΕΠΙΣΗΜΟ.
Επαληθεύτηκε σε 13/13 τμήματα 1ου πεδίου έναντι ανεξάρτητης άντλησης.

Θέσεις / εισαχθέντες / κενές 2026 ΔΕΝ υπάρχουν. Οι στήλες μένουν NULL και
το provenance_note το δηλώνει ρητά, ώστε καμία πληρότητα ή ποσοστό κενών
να μη μπορεί να υπολογιστεί κατά λάθος για το 2026.

Χρήση:  σταμάτα το uvicorn, μετά:  python pipeline/load_2026_bases.py
"""

import duckdb, pandas as pd, hashlib, datetime, pathlib, sys

DB  = pathlib.Path(__file__).resolve().parents[1] / "data" / "pyxida.duckdb"
CSV = pathlib.Path(__file__).resolve().parents[1] / "data/raw/aeitei/2026/vaseis_2026_all_fields.csv"
NOTE = ("ΜΟΝΟ ΒΑΣΗ 2026. Θέσεις/εισαχθέντες/κενές ΔΕΝ διαθέσιμα. "
        "Πηγή aeitei.gr (mirror, ΑΝΕΠΙΣΗΜΟ). data.gov.gr: κανένα dataset 2026.")

COEF = pathlib.Path(__file__).resolve().parents[1] / "data/raw/fek/ebe_coef_2026.csv"
# Επίσημες τιμές αναφοράς πεδίων 2026 (ανακοίνωση Υπ. Παιδείας 23/07/2026),
# σε κλίμακα /20. Το κατώφλι ΕΒΕ ενός τμήματος = αναφορά πεδίου × συντελεστής.
REF26 = {"1ο": 11.20, "2ο": 13.09, "3ο": 12.32, "4ο": 10.33}

df = pd.read_csv(CSV, dtype={"dept_code": str})
assert len(df) and df.base_2026.notna().all(), "άδειο ή ελλιπές CSV"
sha = hashlib.sha256(CSV.read_bytes()).hexdigest()

# Συντελεστές ΕΒΕ 2026: ΕΠΙΣΗΜΟΙ (ΦΕΚ), σε αντίθεση με τις βάσεις.
k = pd.read_csv(COEF, dtype={"dept_code": str})
k["ebe_coefficient"] = pd.to_numeric(k["ebe_coefficient"], errors="coerce")
df = df.merge(k[["dept_code", "ebe_coefficient"]], on="dept_code", how="left")
# Η στήλη ebe_threshold της βάσης είναι σε ΜΟΡΙΑ (2025: 8.400-15.810), όχι /20.
df["ebe_threshold"] = df.apply(
    lambda r: round(REF26[r["field"]] * 1000 * r["ebe_coefficient"], 1)
    if pd.notna(r["ebe_coefficient"]) and r["field"] in REF26 else None, axis=1)
_t = df["ebe_threshold"].dropna()
assert _t.between(6000, 18000).all(), f"κατώφλια εκτός κλίμακας μορίων: {_t.min()}-{_t.max()}"
print(f"συντελεστές ΕΒΕ 2026 (ΦΕΚ): {df.ebe_coefficient.notna().sum()}/{len(df)} τμήματα")

con = duckdb.connect(str(DB))
try:
    con.execute("BEGIN")
    sid = con.execute("SELECT COALESCE(MAX(source_id),0)+1 FROM source").fetchone()[0]
    con.execute("""INSERT INTO source
        (source_id,name,kind,url,local_path,retrieved_at,checksum_sha256,license,is_official,note)
        VALUES (?,?,?,?,?,?,?,?,?,?)""",
        [sid, "aeitei.gr (mirror υπουργικών αρχείων)", "mirror",
         "https://www.aeitei.gr/index.php?year=2026", str(CSV),
         datetime.datetime.now(), sha, "unknown", False,
         "βάσεις 2026 ΓΕΛ90 μόνο· επαληθεύτηκε 13/13 στο 1ο πεδίο"])

    con.execute("DELETE FROM admission WHERE year=2026 AND category='ΓΕΛ90'")
    con.register("inc", df[["dept_code", "base_2026", "ebe_coefficient", "ebe_threshold"]])
    con.execute("""INSERT INTO admission
        (dept_code,year,category,base_last,grade_first,seats_offered,admitted,
         vacancies,fill_rate,ebe_coefficient,ebe_threshold,vacancy_cause,
         source_id,provenance_note)
        SELECT i.dept_code, 2026, 'ΓΕΛ90', i.base_2026,
               NULL, NULL, NULL, NULL, NULL,
               i.ebe_coefficient, i.ebe_threshold, NULL, ?, ?
        FROM inc i JOIN department d USING(dept_code)""", [sid, NOTE])
    n = con.execute("SELECT COUNT(*) FROM admission WHERE year=2026").fetchone()[0]
    con.execute("COMMIT")
except Exception:
    con.execute("ROLLBACK"); raise

print(f"φορτώθηκαν {n} γραμμές για το 2026 (source_id={sid})")
print("έλεγχος NULL:", con.execute("""SELECT
   SUM(seats_offered IS NULL) s_null, SUM(admitted IS NULL) a_null,
   SUM(base_last IS NULL) b_null FROM admission WHERE year=2026""").fetchdf().to_dict("records")[0])
con.close()
