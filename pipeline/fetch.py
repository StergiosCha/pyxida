"""
Phase 0 · fetch.py — idempotent raw-data acquisition for «Πυξίδα ΑΕΙ».

Downloads official Greek Ministry of Education admission datasets from the
data.gov.gr CKAN open-data API into /data/raw/{source}/{year}/, with:
  - checksum + skip-if-present (idempotent: re-running downloads nothing new)
  - polite rate-limiting (>= RATE_LIMIT_S between requests)
  - a fetch manifest CSV logging url / path / sha256 / bytes / status per file

Authoritative source: data.gov.gr (CKAN 2.11.3). Files are stored on Azure
Blob Storage behind 302 redirects. The aeitei.gr mirror (report's suggested
fallback) refuses automated clients from this environment, so years missing
from official open data (2020-2023) are logged as gaps, not fetched.

Usage:  python -m pipeline.fetch            # fetch all
        python -m pipeline.fetch --list     # show manifest only
"""
from __future__ import annotations
import hashlib, json, time, sys, csv
from pathlib import Path
import requests

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
SRC = "data.gov.gr"
RATE_LIMIT_S = 2.0
UA = {"User-Agent": "pyxida-aei-research/1.0", "Accept": "*/*"}

# ---- Dataset slugs (one canonical base file per year) ------------------------
# Live download URLs are resolved at runtime from the CKAN package_show API
# (see resolve()), so the manifest never goes stale against Azure signed-URL
# expiry. Slug transliteration drifts across years:
#   arxeio-basewn... (2016-18) -> basewn... (2019) -> archeio-vaseon... /
#   vaseis-eisagogis... (2024-25).
BASE_SLUGS = {
    2015: "vaseis-eisagwgis-2015",
    2016: "arxeio-basewn-eisagwghs-sthn-tritoba8mia-ekpaideysh-epityxontwn-stis-panelladikes-e3etaseis",
    2017: "arxeio-basewn-eisagwghs-gel-kai-epal-epityxontwn-stis-panelladikes-e3etaseis-2017",
    2018: "arxeio-basewn-eisagwghs-gel-kai-epal-sthn-tritoba8mia-ekpaideysh-epityxontwn-stis-pan-e3-2018",
    2019: "basewn-eisagwghs-gel-epal-sthn-tritoba8mia-panelladikes-e3etaseis-2019",
    2024: "archeio-vaseon-eisagogis-katigorion-gel-epal-stin-tritovathmia-ekpaideysi-stis-panelladikes-exetasei",
    2025: "vaseis-eisagogis-gel-epal-tritovathmia-panelladikes-2025",
}
EBE_SLUGS = {
    2024: "archeio-me-tis-elachistes-vaseis-eisagogis-e-v-e-scholon-stis-panelladikes-exetaseis-2024",
    2025: "archeio-me-tis-elachistes-vaseis-eisagogis-e-v-e-scholon-stis-panelladikes-exetaseis-2025",
}
# Years with NO official open-data base file (aeitei mirror blocked here).
GAP_YEARS = [2020, 2021, 2022, 2023]

API = "https://data.gov.gr/api/3/action"
# Preferred format per year (parseable + one-file-per-year where possible)
PREF = {2015: "ZIP", 2016: "ZIP", 2017: "ZIP", 2018: "ZIP", 2019: "ZIP",
        2024: "XLSX", 2025: "XLSX"}


def _get(url, **kw):
    return requests.get(url, timeout=60, headers=UA, **kw)


def resolve():
    """Query CKAN for fresh signed download URLs. Returns list of dicts."""
    s = requests.Session(); s.headers.update({"Accept": "application/json"})
    out = []
    for kind, slugs, pref in (("base", BASE_SLUGS, PREF), ("ebe", EBE_SLUGS, None)):
        for yr, slug in slugs.items():
            r = s.get(f"{API}/package_show", params={"id": slug}, timeout=40).json()
            if not r.get("success"):
                out.append({"kind": kind, "year": yr, "status": "slug_not_found",
                            "slug": slug, "url": None, "format": None})
                continue
            res = r["result"]["resources"]
            want = (pref or {}).get(yr)
            chosen = None
            if want:
                chosen = next((x for x in res if (x.get("format") or "").upper() == want), None)
            if chosen is None:  # fall back to first ZIP, then first XLSX/CSV
                for f in ("ZIP", "XLSX", "CSV"):
                    chosen = next((x for x in res if (x.get("format") or "").upper() == f), None)
                    if chosen:
                        break
            if chosen is None:
                out.append({"kind": kind, "year": yr, "status": "no_resource",
                            "slug": slug, "url": None, "format": None})
                continue
            out.append({"kind": kind, "year": yr, "status": "resolved",
                        "slug": slug, "url": chosen["url"],
                        "format": (chosen.get("format") or "bin").lower()})
            time.sleep(0.3)
    return out


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fetch_all(dry=False):
    manifest = resolve()
    rows = []
    last = 0.0
    for m in manifest:
        yr, kind, fmt = m["year"], m["kind"], m["format"]
        if m["status"] != "resolved":
            rows.append({**m, "path": None, "sha256": None, "bytes": 0})
            continue
        ext = {"xlsx": "xlsx", "zip": "zip", "csv": "csv", "rar": "rar"}.get(fmt, "bin")
        dest = RAW / SRC / str(yr) / f"{kind}_{yr}.{ext}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():                                   # idempotent skip
            b = dest.read_bytes()
            rows.append({**m, "path": str(dest.relative_to(RAW.parent)),
                         "sha256": sha256(b), "bytes": len(b), "status": "cached"})
            continue
        if dry:
            rows.append({**m, "path": str(dest), "sha256": None, "bytes": 0,
                         "status": "would_fetch"})
            continue
        dt = time.time() - last                             # rate limit
        if dt < RATE_LIMIT_S:
            time.sleep(RATE_LIMIT_S - dt)
        last = time.time()
        try:
            resp = _get(m["url"])
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            rows.append({**m, "path": str(dest.relative_to(RAW.parent)),
                         "sha256": sha256(resp.content), "bytes": len(resp.content),
                         "status": "fetched"})
        except Exception as e:
            rows.append({**m, "path": str(dest), "sha256": None, "bytes": 0,
                         "status": f"error:{type(e).__name__}"})
    # gap years
    for gy in GAP_YEARS:
        rows.append({"kind": "base", "year": gy, "format": None, "url": None,
                     "slug": None, "status": "gap_no_official_opendata",
                     "path": None, "sha256": None, "bytes": 0})
    # write manifest CSV
    mpath = RAW / "fetch_manifest.csv"
    cols = ["kind", "year", "format", "status", "bytes", "sha256", "slug", "url", "path"]
    with open(mpath, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in cols})
    return rows, mpath


if __name__ == "__main__":
    dry = "--list" in sys.argv
    rows, mpath = fetch_all(dry=dry)
    for r in rows:
        print(f"{r['year']} {r['kind']:4} {str(r.get('format')):5} "
              f"{r['status']:24} {r.get('bytes',0):>9,}  {r.get('sha256') or ''}")
    print(f"\nmanifest -> {mpath}")
