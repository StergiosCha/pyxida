"""
Phase 0 · normalize.py — raw archives -> one canonical long table.

Handles three raw layouts discovered in /data/raw/data.gov.gr:
  2015, 2019  : ZIP of ISO-8859-7 CSVs, one file per candidate category
  2016-2018   : ZIP -> RAR -> per-category CSV/XLS (RAR extracted via bsdtar)
  2024, 2025  : single XLSX, category in the ΕΙΔΟΣ ΘΕΣΗΣ column

Output grain: (dept_code, year, category) — the schema's `admission` table.
We retain the four comparable mainstream categories:
  ΓΕΛ90 (ΓΕΛ γενική σειρά ημερήσια), ΓΕΛ10, ΕΠΑΛ90, ΕΠΑΛ10.
Special sub-categories (στρατιωτικές/αστυνομία/πολύτεκνοι/...) are not
βάση-comparable across departments and are dropped from the fact table
(counted in the QA "dropped rows" log instead).

μόρια encoding: CSVs use dot-as-thousands ('16.809' -> 16809); XLSX store
plain integers. Both normalised to int μόρια.
"""
from __future__ import annotations
import io, re, zipfile, subprocess, tempfile, shutil, csv as _csv
from pathlib import Path
import pandas as pd

RAW = Path(__file__).resolve().parent.parent / "data" / "raw" / "data.gov.gr"
ENC = "iso-8859-7"

# Category classification from the ΕΙΔΟΣ ΘΕΣΗΣ label / filename hint. -----------
# Note: Ministry files mix Latin I/K into "ΓΕΝIKH"; match on robust substrings.
def classify_category(label: str) -> str | None:
    if not label:
        return None
    s = str(label).upper().strip()
    s = s.replace("I", "Ι").replace("K", "Κ")           # latin -> greek homoglyphs
    is_epal = "ΕΠΑΛ" in s
    is_gel  = ("ΓΕΛ" in s) or (not is_epal and "ΗΜΕΡ" in s and "ΕΠΑΛ" not in s)
    ten = "10%" in s or "10 %" in s
    # drop special categories entirely
    special = any(t in s for t in ["ΣΤΡΑΤΙ", "ΑΣΤΥΝ", "ΠΟΛΥΤΕΚ", "ΤΡΙΤΕΚ", "ΠΟΛΥΤ",
                                     "ΚΟΙΝΩΝ", "ΣΟΒΑΡ", "ΠΑΘΗΣ", "ΠΛΗΓΕΝΤ", "ΑΛΛΟΓΕΝ",
                                     "ΑΛΛΟΔΑΠ", "ΕΞΩΤΕΡΙΚ", "ΜΟΥΣΟΥΛΜ", "ΕΚΚΛΗΣΙΑΣΤ",
                                     "ΕΣΠ", "ΕΣΠΕΡΙΝ", "3648", "4%"])
    if special:
        return None
    if is_epal:
        return "ΕΠΑΛ10" if ten else "ΕΠΑΛ90"
    if is_gel:
        return "ΓΕΛ10" if ten else "ΓΕΛ90"
    return None


# filename -> category hint for the per-file (2015-2019) layout
def category_from_filename(fn: str) -> str | None:
    n = fn.upper()
    if "ESPERINA" in n or "ΕΣΠΕΡΙΝ" in n:
        return None
    ten = "10%" in n or "10 %" in n
    if "EPAL" in n or "ΕΠΑΛ" in n:
        # exclude EPALA-only historical special files that aren't mainstream day
        if "EPALA" in n and "HMER" not in n:
            return None
        return "ΕΠΑΛ10" if ten else "ΕΠΑΛ90"
    if "GEL" in n or "ΓΕΛ" in n:
        return "ΓΕΛ10" if ten else "ΓΕΛ90"
    return None


def parse_moria(v) -> float | None:
    """Parse a μόρια cell to a number on the 0-30000 scale.

    Two encodings coexist:
      - XLSX/XLS numeric cells: already clean floats (10010.0) -> pass through.
      - ISO-8859-7 CSV strings: dot-as-thousands ('16.809' -> 16809), with an
        optional tie-break tail after a space ('8.468' from '8.468 ...').
    """
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    # numeric already (from pandas Excel read) -> trust it
    if isinstance(v, (int, float)):
        f = float(v)
        return f if 0 <= f <= 30000 else None
    s = str(v).strip()
    if not s or s in ("-", "nan"):
        return None
    s = s.split()[0]                                     # drop tie-break tail
    # Separator convention flips across years: some files use '.' as the
    # thousands separator ('16.809'), 2018 uses ',' ('15,842'). μόρια are
    # integers on a 0-20400 scale, so strip BOTH separators and read as int.
    digits = re.sub(r"[.,]", "", s)
    if not digits.isdigit():
        return None
    f = float(digits)
    return f if 0 <= f <= 30000 else None


def _to_int(v):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return int(float(str(v).replace(".", "").replace(",", ".")))
    except (ValueError, TypeError):
        return None


# ---- unwrap each year into a list of (category, DataFrame[std cols]) ----------
STD = ["dept_code", "institution", "dept_name", "eidos", "seats_initial",
       "seats_final", "admitted", "grade_first", "grade_last"]


def classify_from_title(title: str) -> str | None:
    """Classify from a file's embedded title line, e.g.
    'ΒΑΣΕΙΣ -- ΕΠΙΛΟΓΗ 90% ΓΕΛ,ΕΠΑΛΒ-ΗΜΕΡΗΣΙΑ -- ΠΑΝΕΛΛΑΔΙΚΕΣ 2015'.
    Pre-2016 combined ΓΕΛ+ΕΠΑΛΒ into one mainstream track -> ΓΕΛ90/ΓΕΛ10.
    """
    if not title:
        return None
    s = title.upper()
    if "ΕΣΠΕΡΙΝ" in s or "ΕΣΠ." in s:
        return None                                       # evening schools: not comparable
    if any(t in s for t in ["ΑΛΛΟΓΕΝ", "ΑΛΛΟΔΑΠ", "ΕΞΩΤΕΡΙΚ", "ΣΟΒΑΡ",
                             "ΠΑΘΗΣ", "ΠΛΗΓΕΝΤ", "ΜΟΥΣΟΥΛΜ", "ΑΘΛΗΤ"]):
        return None
    ten = "10%" in s or "10 %" in s
    # "ΓΕΛ,ΕΠΑΛΒ" combined = the GEL mainstream in the pre-2016 system
    if "ΓΕΛ" in s:
        return "ΓΕΛ10" if ten else "ΓΕΛ90"
    if "ΕΠΑΛ" in s:                                       # ΕΠΑΛΑ / ΕΠΑΛ-only tracks
        return "ΕΠΑΛ10" if ten else "ΕΠΑΛ90"
    return None


def _title_of(b: bytes) -> str:
    txt = b.decode(ENC, errors="replace")
    for line in txt.splitlines():
        if line.strip(" ;"):
            return line
    return ""


def _detect_cols(combined: list[str]) -> dict:
    """Map STD field -> column index from a combined (row-A + ' ' + row-B) header.
    Robust to column reordering across years (2016 swaps ΟΝΟΜΑ/ΙΔΡΥΜΑ; grade
    columns move); detects by Greek label keywords rather than fixed position.
    """
    U = [str(c).upper() for c in combined]
    def find(pred, start=0):
        for i in range(start, len(U)):
            if pred(U[i]):
                return i
        return None
    idx = {}
    idx["dept_code"]     = find(lambda s: "ΚΩΔΙΚΟΣ" in s)
    idx["institution"]   = find(lambda s: "ΙΔΡΥΜΑ" in s)
    idx["dept_name"]     = find(lambda s: ("ΟΝΟΜΑ" in s or "ΣΧΟΛΗ" in s)
                                          and "ΚΩΔΙΚΟΣ" not in s and "ΕΙΔΟΣ" not in s)
    idx["eidos"]         = find(lambda s: "ΕΙΔΟΣ" in s)
    idx["seats_initial"] = find(lambda s: "ΑΡΧΙΚΕΣ" in s)
    idx["seats_final"]   = find(lambda s: "ΚΑΤΟΠΙΝ" in s or "ΜΕΤΑΦ" in s or "ΘΕΣΕΙΣ (" in s)
    # 2015: single bare "ΘΕΣΕΙΣ" column (no initial/final split) -> use for both
    if idx["seats_initial"] is None and idx["seats_final"] is None:
        bare = find(lambda s: s.strip() == "ΘΕΣΕΙΣ")
        idx["seats_initial"] = idx["seats_final"] = bare
    idx["admitted"]      = find(lambda s: "ΕΠΙΤ" in s)            # ΕΠΙΤ/ΤΕΣ, ΕΠΙΤΥΧΟΝΤΕΣ
    idx["grade_first"]   = find(lambda s: "ΠΡΩΤΟΥ" in s and ("ΜΟΡΙΑ" in s or "ΒΑΘΜΟΣ" in s))
    idx["grade_last"]    = find(lambda s: "ΤΕΛΕΥΤΑΙΟΥ" in s and ("ΜΟΡΙΑ" in s or "ΒΑΘΜΟΣ" in s))
    return idx


def _parse_grid(rows: list[list]) -> pd.DataFrame | None:
    """Parse a 2D grid (list of rows) with a 2-line Ministry header into STD."""
    if len(rows) < 3:
        return None
    hdr_i = next((i for i, r in enumerate(rows)
                  if any("ΚΩΔΙΚΟΣ" in str(c).upper() for c in r)), None)
    if hdr_i is None:
        return None
    rowA = rows[hdr_i]
    rowB = rows[hdr_i + 1] if hdr_i + 1 < len(rows) else []
    ncol = max(len(rowA), len(rowB))
    combined = [f"{rowA[i] if i < len(rowA) else ''} "
                f"{rowB[i] if i < len(rowB) else ''}" for i in range(ncol)]
    idx = _detect_cols(combined)
    if idx["dept_code"] is None or idx["grade_last"] is None:
        return None
    # data starts after the 2-line header; but if row hdr_i+1 is actually data
    # (single-header files), detect: a data row has a numeric first cell.
    def cell(r, k):
        i = idx[k]
        return r[i] if (i is not None and i < len(r)) else None
    start = hdr_i + 1
    # skip the sub-label row if present (its dept_code cell is non-numeric)
    if start < len(rows):
        c0 = str(cell(rows[start], "dept_code") or "").strip()
        if not re.match(r"^\d+(\.0)?$", c0):
            start += 1
    out = []
    for r in rows[start:]:
        code_raw = str(cell(r, "dept_code") or "").strip()
        if not re.match(r"^\d+(\.0)?$", code_raw):
            continue
        out.append({
            "dept_code": str(_to_int(code_raw)),
            "institution": str(cell(r, "institution") or "").strip(),
            "dept_name": str(cell(r, "dept_name") or "").strip(),
            "eidos": str(cell(r, "eidos") or "").strip(),
            "seats_initial": _to_int(cell(r, "seats_initial")),
            "seats_final": _to_int(cell(r, "seats_final")),
            "admitted": _to_int(cell(r, "admitted")),
            "grade_first": parse_moria(cell(r, "grade_first")),
            "grade_last": parse_moria(cell(r, "grade_last")),
        })
    return pd.DataFrame(out) if out else None


def _read_csv_bytes(b: bytes) -> pd.DataFrame | None:
    """Parse a Ministry per-category CSV (semicolon, ISO-8859-7)."""
    txt = b.decode(ENC, errors="replace")
    rows = list(_csv.reader(io.StringIO(txt), delimiter=";"))
    return _parse_grid(rows)


def _extract_rar(rar_path: Path) -> Path:
    d = Path(tempfile.mkdtemp(prefix="pyx_rar_"))
    subprocess.run(["bsdtar", "-xf", str(rar_path), "-C", str(d)],
                   check=True, capture_output=True)
    return d


def unwrap_year(year: int):
    """Yield (category, DataFrame[STD]) for mainstream categories of a year."""
    base = RAW / str(year)
    # --- XLSX years (2024, 2025) ---
    xlsx = base / f"base_{year}.xlsx"
    if xlsx.exists():
        x = pd.read_excel(xlsx, header=1)
        x.columns = [str(c).strip() for c in x.columns]
        colmap = {
            "ΚΩΔΙΚΟΣ ΣΧΟΛΗΣ": "dept_code", "ΙΔΡΥΜΑ": "institution", "ΣΧΟΛΗ": "dept_name",
            "ΕΙΔΟΣ ΘΕΣΗΣ": "eidos", "ΑΡΧΙΚΕΣ ΘΕΣΕΙΣ": "seats_initial",
            "ΘΕΣΕΙΣ (ΚΑΤΟΠΙΝ ΜΕΤΑΦΟΡΑΣ)": "seats_final", "ΕΠΙΤΥΧΟΝΤΕΣ": "admitted",
            "ΜΟΡΙΑ ΠΡΩΤΟΥ": "grade_first", "ΜΟΡΙΑ ΤΕΛΕΥΤΑΙΟΥ": "grade_last",
        }
        x = x.rename(columns=colmap)
        x["category"] = x["eidos"].map(classify_category)
        x = x[x["category"].notna()].copy()
        x["dept_code"] = x["dept_code"].apply(lambda v: str(_to_int(v) or "").strip())
        for c in ("seats_initial", "seats_final", "admitted"):
            x[c] = x[c].apply(_to_int)
        for c in ("grade_first", "grade_last"):
            x[c] = x[c].apply(parse_moria)
        for cat, g in x.groupby("category"):
            yield cat, g
        return

    # --- ZIP years (2015-2019) ---
    zp = base / f"base_{year}.zip"
    if not zp.exists():
        return
    zf = zipfile.ZipFile(zp)
    members = zf.namelist()
    rar = [m for m in members if m.lower().endswith(".rar")]
    if rar:                                              # 2016-2018: RAR inside
        tmpz = Path(tempfile.mkdtemp(prefix="pyx_zip_"))
        zf.extractall(tmpz)
        rar_path = next(tmpz.rglob("*.rar"))
        rar_dir = _extract_rar(rar_path)
        files = [p for p in rar_dir.rglob("*") if p.suffix.lower() in (".csv", ".xls", ".xlsx")]
        agg = {}
        for p in files:
            try:
                if p.suffix.lower() == ".csv":
                    b = p.read_bytes()
                    cat = classify_from_title(_title_of(b)) or category_from_filename(p.name)
                    df = _read_csv_bytes(b) if cat else None
                else:
                    cat = category_from_filename(p.name)
                    df = _read_xls_generic(p) if cat else None
            except Exception:
                cat, df = None, None
            if cat and df is not None and len(df):
                agg.setdefault(cat, []).append(df)
        for cat, parts in agg.items():
            yield cat, pd.concat(parts, ignore_index=True)
        return
    # 2015, 2019: plain CSVs, one per category. Classify from the embedded
    # title line (filenames are unreliable: 2015 stores them non-UTF-8).
    agg = {}
    for m in members:
        if not m.lower().endswith(".csv"):
            continue
        b = zf.read(m)
        cat = classify_from_title(_title_of(b)) or category_from_filename(m)
        if cat is None:
            continue
        df = _read_csv_bytes(b)
        if df is not None and len(df):
            agg.setdefault(cat, []).append(df)
    for cat, parts in agg.items():
        yield cat, pd.concat(parts, ignore_index=True)


def _read_xls_generic(path: Path) -> pd.DataFrame | None:
    """Read a legacy .xls/.xlsx base file via the shared grid parser."""
    try:
        raw = pd.read_excel(path, header=None)
    except Exception:
        return None
    rows = raw.where(pd.notna(raw), "").astype(object).values.tolist()
    return _parse_grid(rows)


def normalize_all(years=(2015, 2016, 2017, 2018, 2019, 2024, 2025)) -> pd.DataFrame:
    """Return the canonical long admission frame across all available years."""
    frames = []
    for y in years:
        for cat, df in unwrap_year(y):
            df = df.copy()
            df["year"] = y
            df["category"] = cat
            frames.append(df)
    all_df = pd.concat(frames, ignore_index=True)
    # deduplicate on grain, prefer the row with a non-null base
    all_df["_has_base"] = all_df["grade_last"].notna().astype(int)
    all_df = (all_df.sort_values("_has_base", ascending=False)
                    .drop_duplicates(["dept_code", "year", "category"], keep="first")
                    .drop(columns="_has_base"))
    # seats: prefer final (post-transfer) else initial
    all_df["seats_offered"] = all_df["seats_final"].fillna(all_df["seats_initial"])
    all_df["vacancies"] = (all_df["seats_offered"] - all_df["admitted"])
    all_df["vacancies"] = all_df["vacancies"].where(all_df["vacancies"] >= 0)
    all_df["fill_rate"] = (all_df["admitted"] / all_df["seats_offered"]).round(4)
    return all_df


if __name__ == "__main__":
    df = normalize_all()
    print("canonical rows:", len(df))
    print(df.groupby(["year", "category"]).size().unstack(fill_value=0))
