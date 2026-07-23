"""
Phase 0 · ebe.py — ΕΒΕ (Ελάχιστη Βάση Εισαγωγής, ν.4777/2021) loader.

Parses the Ministry ΕΒΕ-per-school files (data.gov.gr, 2024 & 2025) into:
  - dept_ebe:  (dept_code, year) -> coefficient (ΣΥΝΤ. ΕΒΕ, 0.80-1.20),
               field, ΕΒΕ threshold ΓΕΛ, ΕΒΕ threshold ΕΠΑΛ
  - field_ebe: (year, field) -> implied field ΕΒΕ base = threshold / coefficient
               (ν.4777 mechanics: threshold = field_base × dept_coefficient,
                field_base = field mean-of-means × 0.80)

Scale note: the ΕΒΕ thresholds in these files are on the /20 school-grade
scale (e.g. 11.84), while βάσεις μόρια are on the /20000 scale. We store the
raw ΕΒΕ value and expose a ×1000 helper so callers can compare like-for-like.
"""
from __future__ import annotations
import io, zipfile
from pathlib import Path
import pandas as pd

RAW = Path(__file__).resolve().parent.parent / "data" / "raw" / "data.gov.gr"


def _to_code(v):
    try:
        return str(int(float(str(v).replace(".", "").replace(",", "."))))
    except (ValueError, TypeError):
        return None


def _num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def load_ebe(year: int) -> pd.DataFrame:
    """Return dept-level ΕΒΕ frame for a year, or empty if the file is absent."""
    zp = RAW / str(year) / f"ebe_{year}.zip"
    if not zp.exists():
        return pd.DataFrame()
    zf = zipfile.ZipFile(zp)
    member = next((n for n in zf.namelist() if n.lower().endswith((".xlsx", ".xls"))), None)
    if member is None:
        return pd.DataFrame()
    x = pd.read_excel(io.BytesIO(zf.read(member)), header=1)
    x.columns = [str(c).strip() for c in x.columns]
    def col(*keys):
        for c in x.columns:
            cu = c.upper()
            if all(k in cu for k in keys):
                return c
        return None
    c_code = col("ΚΩΔΙΚΟΣ")
    c_coef = col("ΣΥΝΤ", "ΕΒΕ")
    c_field = col("ΕΠ", "ΠΕΔΙΟ", "ΕΒΕ")
    c_gel = col("ΕΒΕ", "ΣΧΟΛΗΣ", "ΓΕΛ")
    c_epal = col("ΕΒΕ", "ΣΧΟΛΗΣ", "ΕΠΑΛ")
    out = pd.DataFrame({
        "dept_code": x[c_code].map(_to_code),
        "year": year,
        "ebe_coefficient": x[c_coef].map(_num) if c_coef else None,
        "ebe_field": x[c_field].astype(str).str.strip() if c_field else None,
        "ebe_threshold_gel": x[c_gel].map(_num) if c_gel else None,
        "ebe_threshold_epal": x[c_epal].map(_num) if c_epal else None,
    })
    out = out[out["dept_code"].notna()].drop_duplicates(["dept_code", "year"])
    return out


def load_all_ebe(years=(2024, 2025)) -> pd.DataFrame:
    parts = [load_ebe(y) for y in years]
    parts = [p for p in parts if len(p)]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


FEK_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "fek"


def load_fek_coefficients() -> pd.DataFrame:
    """Coefficients announced by ΥΑ/ΦΕΚ ahead of the exam year (no results yet).
    Reads every data/raw/fek/ebe_coef_<year>.csv (extracted from the ΦΕΚ PDF;
    2026: ΥΑ Φ.253/160742/Α5/10-12-2025, ΦΕΚ Β' 6782/16-12-2025)."""
    parts = []
    if FEK_DIR.exists():
        for p in sorted(FEK_DIR.glob("ebe_coef_*.csv")):
            df = pd.read_csv(p, dtype={"dept_code": str})
            parts.append(df)
    if not parts:
        return pd.DataFrame(columns=["dept_code", "year", "ebe_coefficient",
                                     "ebe_special_coefficient", "source"])
    return pd.concat(parts, ignore_index=True)


def coef_by_year() -> pd.DataFrame:
    """Unified (year, dept_code) -> coefficient frame for dept_ebe_coef:
    open-data years (2024/2025) + ΦΕΚ-announced years (2026+)."""
    rows = []
    od = load_all_ebe()
    if len(od):
        for r in od.itertuples():
            rows.append({"year": int(r.year), "dept_code": r.dept_code,
                         "ebe_coefficient": r.ebe_coefficient,
                         "ebe_special_coefficient": None,
                         "source_note": f"data.gov.gr ΕΒΕ file {int(r.year)}"})
    fek = load_fek_coefficients()
    for r in fek.itertuples():
        rows.append({"year": int(r.year), "dept_code": r.dept_code,
                     "ebe_coefficient": r.ebe_coefficient,
                     "ebe_special_coefficient": (None if pd.isna(r.ebe_special_coefficient)
                                                 else float(r.ebe_special_coefficient)),
                     "source_note": r.source})
    out = pd.DataFrame(rows)
    return out.drop_duplicates(["year", "dept_code"], keep="last") if len(out) else out


def field_ebe_table(dept_ebe: pd.DataFrame) -> pd.DataFrame:
    """Derive per-(year, field) ΕΒΕ base from department rows.
    threshold = field_base × coefficient  =>  field_base = threshold / coef.
    Take the modal/median implied base per field-year (robust to rounding).
    """
    if dept_ebe.empty:
        return pd.DataFrame(columns=["year", "field", "ebe_base"])
    d = dept_ebe.dropna(subset=["ebe_coefficient", "ebe_threshold_gel", "ebe_field"]).copy()
    d = d[d["ebe_coefficient"] > 0]
    d["implied_base"] = d["ebe_threshold_gel"] / d["ebe_coefficient"]
    fb = (d.groupby(["year", "ebe_field"])["implied_base"]
            .median().round(3).reset_index()
            .rename(columns={"ebe_field": "field", "implied_base": "ebe_base"}))
    return fb


if __name__ == "__main__":
    de = load_all_ebe()
    print("dept-ΕΒΕ rows:", len(de))
    print(de.groupby("year").agg(n=("dept_code", "size"),
          coef_min=("ebe_coefficient", "min"), coef_max=("ebe_coefficient", "max"),
          thr_med=("ebe_threshold_gel", "median")).to_string())
    print("\nfield_ebe:")
    print(field_ebe_table(de).to_string(index=False))
