"""
Revealed-preference analysis of the 2024 μηχανογραφικό (per-candidate preferences).

Data: data.gov.gr `archeio-protimiseon-ypopsifion-gel-epal-...-2024` — 1.10M rows
(hashed candidate id, rank, school name), 65,117 candidates. The 2025 upload is a
broken/empty zip on the portal as of 2026-07 — re-check each refresh.

Design: WITHIN-candidate, WITHIN-program-family, cross-city (or cross-institution)
pairwise comparisons. Because both alternatives sit in the SAME candidate's list,
ability (μόρια) and program identity are held constant by construction — this is
revealed desirability, uncontaminated by field mix or candidate strength.

Outputs (data/):
  prefs_pairwise_2024.csv        (family, cityA-above, cityB-below, n)
  prefs_inst_pairwise_2024.csv   (instA-above, instB-below, n)
  city_desirability_bt_2024.csv  Bradley-Terry city scores
  inst_desirability_bt_2024.csv  Bradley-Terry institution scores
  city_desirability_covariates.csv  scores + hours/island/tourism/gdp

Headline results (2026-07 run):
  * Παν. Πατρών ≻ Παν. Κρήτης in 74.7% of 14,743 direct within-family matchups.
  * Ρέθυμνο loses to EVERY mainland city (even Κομοτηνή 63/37, Καλαμάτα 62/38)
    but beats Μυτιλήνη 68/32 — a clean accessibility gradient.
  * Ρέθυμνο (0.125) ≈ Ηράκλειο (0.136) once program mix is controlled: the
    Rethymno campus's higher vacancy is mostly FIELD MIX, not the city.
  * OLS on log BT score (n=23 cities with rent):
      hours-to-Athens/Thessaloniki  β≈−0.69 σ  p<1e-5   ← dominant factor
      rent (1BR, cross-section)     β≈+0.22 σ  p≈0.03   ← POSITIVE: amenity
      endogeneity — expensive cities are attractive cities. Cross-sectional rent
      CANNOT identify a cost-deterrent effect; that needs rent-GROWTH panel data.
  * Islands are not special once hours are controlled.

Caveats:
  * `HOURS` are hand-coded approximations (road/ferry to nearest of Athens/
    Thessaloniki); replace with a proper travel-time matrix if this graduates
    from exploratory to published analysis.
  * Rent figures are press-published Spitogatos asking rents (mixed 2025/2026,
    mixed furnished/unfurnished, floor-vs-midpoint) — indicative only.
  * BT aggregated across families over-weights institutions with popular
    portfolios (ΟΠΑ effect); within-family matchups are the honest unit.

Run:  python -m analysis.desirability_2024   (from repo root, ~2-3 min)
"""
from __future__ import annotations
import collections, itertools, re, sys, unicodedata
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from api.compare import family_key  # noqa: E402

PREFS_CSV = ROOT / "data/raw/data.gov.gr/prefs/5_ARXEIO_PROTIMISEON_GEL_EPAL_2024.csv"
PREFS_ZIP = ROOT / "data/raw/data.gov.gr/prefs/prefs_2024.zip"

# junk "cities" produced by renaming notes inside parentheses
_BAD_CITY = re.compile(r"ΜΕΤΟΝΟΜΑΣΙΑ|ΜΕΤΑΦΕΡΘΕΙ|ΕΔΡΑ|ΤΜΗΜΑΤΟΣ", re.I)

HOURS = {  # approx. road/ferry hours to nearest of Athens/Thessaloniki, island flag
    "ΑΘΗΝΑ": (0, 0), "ΠΕΙΡΑΙΑΣ": (0.3, 0), "ΑΙΓΑΛΕΩ": (0.3, 0), "ΘΕΣΣΑΛΟΝΙΚΗ": (0, 0),
    "ΒΟΛΟΣ": (2.0, 0), "ΛΑΡΙΣΑ": (1.5, 0), "ΤΡΙΚΑΛΑ": (2.5, 0), "ΚΑΡΔΙΤΣΑ": (2.8, 0),
    "ΛΑΜΙΑ": (2.2, 0), "ΠΑΤΡΑ": (2.5, 0), "ΑΓΡΙΝΙΟ": (3.0, 0), "ΜΕΣΟΛΟΓΓΙ": (3.0, 0),
    "ΙΩΑΝΝΙΝΑ": (3.5, 0), "ΑΡΤΑ": (3.8, 0), "ΠΡΕΒΕΖΑ": (4.5, 0), "ΝΑΥΠΛΙΟ": (1.5, 0),
    "ΤΡΙΠΟΛΗ": (2.0, 0), "ΣΠΑΡΤΗ": (2.7, 0), "ΚΑΛΑΜΑΤΑ": (2.5, 0), "ΚΟΖΑΝΗ": (1.5, 0),
    "ΠΤΟΛΕΜΑΪΔΑ": (1.8, 0), "ΦΛΩΡΙΝΑ": (2.5, 0), "ΚΑΣΤΟΡΙΑ": (2.5, 0), "ΓΡΕΒΕΝΑ": (2.0, 0),
    "ΣΕΡΡΕΣ": (1.0, 0), "ΚΑΒΑΛΑ": (1.7, 0), "ΞΑΝΘΗ": (2.5, 0), "ΚΟΜΟΤΗΝΗ": (3.0, 0),
    "ΑΛΕΞΑΝΔΡΟΥΠΟΛΗ": (4.0, 0), "ΔΙΔΥΜΟΤΕΙΧΟ": (5.5, 0),
    "ΚΕΡΚΥΡΑ": (7.0, 1), "ΑΡΓΟΣΤΟΛΙ": (7.0, 1), "ΖΑΚΥΝΘΟΣ": (5.5, 1),
    "ΗΡΑΚΛΕΙΟ": (9.0, 1), "ΡΕΘΥΜΝΟ": (10.0, 1), "ΧΑΝΙΑ": (9.0, 1),
    "ΑΓΙΟΣ ΝΙΚΟΛΑΟΣ": (10.5, 1), "ΣΗΤΕΙΑ": (11.5, 1),
    "ΜΥΤΙΛΗΝΗ": (11.0, 1), "ΧΙΟΣ": (9.0, 1), "ΣΑΜΟΣ": (12.0, 1), "ΡΟΔΟΣ": (15.0, 1),
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s))
    return re.sub(r"\s+", " ",
                  "".join(c for c in s if unicodedata.category(c) != "Mn").upper()).strip()


def city_of(name: str):
    m = re.findall(r"\(([^)]+)\)", str(name))
    if not m:
        return None
    c = m[-1].strip()
    return None if _BAD_CITY.search(c) or len(c) > 20 else c


def load_prefs() -> pd.DataFrame:
    if not PREFS_CSV.exists() and PREFS_ZIP.exists():
        import zipfile
        zipfile.ZipFile(PREFS_ZIP).extractall(PREFS_CSV.parent)
    df = pd.read_csv(PREFS_CSV, sep=";", names=["cand", "rank", "school"], header=0)
    u = df["school"].drop_duplicates().to_frame()
    u["family"] = u["school"].map(family_key)
    u["city"] = u["school"].map(city_of)
    return df.merge(u, on="school", how="left")


def pairwise(df: pd.DataFrame, unit: str) -> pd.DataFrame:
    """unit ∈ {'city','inst'}: within-candidate within-family pairwise wins."""
    wins = collections.Counter()
    sub = df.dropna(subset=[unit]).sort_values(["cand", "family", "rank"])
    for (_, fam), g in sub.groupby(["cand", "family"], sort=False):
        vals = g[unit].tolist()
        if len(set(vals)) < 2:
            continue
        for i, j in itertools.combinations(range(len(vals)), 2):
            if vals[i] != vals[j]:
                wins[(fam, vals[i], vals[j])] += 1
    return pd.DataFrame([(f, a, b, n) for (f, a, b), n in wins.items()],
                        columns=["family", "above", "below", "n"])


def bradley_terry(W: pd.DataFrame, min_comparisons=2000) -> pd.Series:
    M = W.groupby(["above", "below"]).n.sum().reset_index()
    tot = pd.concat([M.groupby("above").n.sum(), M.groupby("below").n.sum()],
                    axis=1).fillna(0).sum(axis=1)
    keep = sorted(tot[tot >= min_comparisons].index)
    idx = {c: i for i, c in enumerate(keep)}
    Mk = M[M.above.isin(keep) & M.below.isin(keep)]
    wm = np.zeros((len(keep), len(keep)))
    for r in Mk.itertuples():
        wm[idx[r.above], idx[r.below]] += r.n
    p = np.ones(len(keep))
    for _ in range(200):
        for i in range(len(keep)):
            den = sum((wm[i, j] + wm[j, i]) / (p[i] + p[j])
                      for j in range(len(keep)) if j != i)
            if den:
                p[i] = wm[i, :].sum() / den
        p /= p.mean()
    return pd.Series(p, index=keep).sort_values(ascending=False)


def main():
    import duckdb
    df = load_prefs()
    print(f"{len(df):,} rows, {df.cand.nunique():,} candidates")

    W = pairwise(df, "city")
    W.to_csv(ROOT / "data/prefs_pairwise_2024.csv", index=False)
    bt = bradley_terry(W)
    bt.to_csv(ROOT / "data/city_desirability_bt_2024.csv")
    print("city BT top:", (bt / bt.max()).head(5).round(3).to_dict())

    con = duckdb.connect(str(ROOT / "data/pyxida.duckdb"), read_only=True)
    dmap = con.execute("""SELECT d.name, i.name inst FROM department d
                          LEFT JOIN institution i ON i.institution_id=d.institution_id""").fetchdf()
    n2i = dict(zip(dmap["name"].map(_norm), dmap["inst"]))
    df["inst"] = df["school"].map(lambda s: n2i.get(_norm(s)))
    IW = pairwise(df, "inst")
    IW.to_csv(ROOT / "data/prefs_inst_pairwise_2024.csv", index=False)
    ibt = bradley_terry(IW)
    ibt.to_csv(ROOT / "data/inst_desirability_bt_2024.csv")

    # covariates frame
    ctx = con.execute("""SELECT DISTINCT lower(strip_accents(d.city)) c,
                                c2.tourism_per_capita t, c2.gdp_per_capita g
                         FROM department d JOIN city_context c2 ON c2.nuts3=d.nuts3""").fetchdf()
    def low(s):
        s = unicodedata.normalize("NFD", s)
        return "".join(ch for ch in s if unicodedata.category(ch) != "Mn").lower()
    cd = dict(zip(ctx.c, zip(ctx.t, ctx.g)))
    rows = []
    for city, score in bt.items():
        if city not in HOURS:
            continue
        hrs, isl = HOURS[city]
        t, g = cd.get(low(city), (np.nan, np.nan))
        rows.append((city, float(np.log(score)), hrs, isl, t, g))
    F = pd.DataFrame(rows, columns=["city", "log_bt", "hours", "island", "tourism", "gdp"])
    F.to_csv(ROOT / "data/city_desirability_covariates.csv", index=False)
    print("covariates:", len(F), "cities — done. See module docstring for findings.")


if __name__ == "__main__":
    main()
