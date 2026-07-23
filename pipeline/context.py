"""
Phase (analysis) · context.py — regional context loader for the state-vs-private
erosion analysis. Reads the Eurostat NUTS-3 pulls + city→region map (both under
data/raw/context/) and returns:
  - city_context_df: one row per NUTS-3 unit (tourism/GDP/metro)
  - city_to_nuts3:   normalised-city -> NUTS-3 code (for the department join)

Provenance: Eurostat REST API (tourism tour_occ_nin2 2023, GDP nama_10r_3gdp
2022, population demo_r_pjangrp3 2023). GDP/capita is the cost-of-living proxy.
No per-region rent series is available from Eurostat and the research report
contains none, so no rent variable is included — do not fabricate one.
"""
from __future__ import annotations
from pathlib import Path
import json
import pandas as pd

CTX = Path(__file__).resolve().parent.parent / "data" / "raw" / "context"


def load_context():
    raw = json.load(open(CTX / "eurostat_nuts3.json", encoding="utf-8"))
    cmap = json.load(open(CTX / "city_region_map.json", encoding="utf-8"))
    tour = {k: v["value"] for k, v in raw["tourism_nights_2023"].items()}
    gdp = {k: v["value"] for k, v in raw["gdp_per_capita_eur_2022"].items()}
    popn = {k: v["value"] for k, v in raw["population_2023"].items()}
    labels = {k: v["label"] for k, v in raw["tourism_nights_2023"].items()}
    metro = set(cmap["metro"])
    city_to_nuts3 = cmap["city_to_nuts3"]

    used = sorted(set(city_to_nuts3.values()))
    rows = []
    for n in used:
        tpc = tour.get(n, 0) / popn[n] if n in popn and popn[n] else None
        rows.append(dict(
            nuts3=n, region=labels.get(n, n),
            tourism_nights=tour.get(n), population=popn.get(n),
            tourism_per_capita=round(tpc, 3) if tpc else None,
            gdp_per_capita=gdp.get(n),
            is_metro=n in metro,
            source_note="Eurostat NUTS-3: tourism tour_occ_nin2 2023, GDP nama_10r_3gdp 2022, pop demo_r_pjangrp3 2023"))
    return pd.DataFrame(rows), city_to_nuts3
