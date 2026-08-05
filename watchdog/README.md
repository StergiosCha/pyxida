# Παρατηρητήριο Δημοκρατίας — Ελλάδα / Democracy Watchdog — Greece

A sourced-indicator watchdog tracking democracy, press freedom, and rule-of-law
in Greece using data from independent international bodies (RSF, V-Dem, World
Bank WGI, Transparency International, CMPF). **Every number carries a source,
date, and methodology link. The tool assigns no verdict-labels in its own
voice** — the sourced data speaks for itself. See `docs/METHODOLOGY.md` for what
each indicator does and does **not** show.

---

## Τι δείχνει / The honest headline

- **Press freedom & liberal democracy: real, documented decline.** V-Dem liberal
  democracy 0.76 (2019) → 0.57 (2024); RSF: last in the EU four years running
  (2022–2025).
- **Corruption (perception): essentially flat.** TI-CPI and World Bank Control
  of Corruption show no deterioration. We show this too — hiding it would
  discredit the whole thing.

---

## Run it locally

Two terminals.

### 1. Backend (FastAPI, port 8010)
```bash
cd watchdog
# reuse an existing venv with fastapi/uvicorn/duckdb, e.g.:
source ../pyxida/.venv-pyxida/bin/activate
# — or make one —
# python3 -m venv .venv && source .venv/bin/activate && pip install fastapi uvicorn duckdb
uvicorn api.main:app --port 8010
```
Health check: http://127.0.0.1:8010/health → `{"status":"ok"}`

### 2. Frontend (React + Vite, port 5174)
```bash
cd watchdog/web
npm install     # one-time
npm run dev
```
Open **http://127.0.0.1:5174** (use `127.0.0.1`, not `localhost` — avoids the
macOS IPv6 resolution trap).

The DB (`data/watchdog.duckdb`) ships pre-built, so you do **not** need to run
the pipeline to view the app. No API key or LLM is required — this app is pure
sourced data.

---

## Endpoints

| Endpoint | Returns |
|---|---|
| `GET /health` | liveness |
| `GET /meta` | sources, indicator list, year range, row counts |
| `GET /indicators` | distinct indicators + latest value |
| `GET /indicators/{indicator}/series` | full time-series + source + provenance |
| `GET /alerts` | dated rule-of-law / surveillance events |
| `GET /media` | media-ownership rows (all `is_official=FALSE`) |

---

## Data model

DuckDB, four tables, **provenance gate enforced at build time** — no indicator
or alert row may exist without a `source_url` (`pipeline/build_db.py` asserts
this and fails the build otherwise).

- `source` — one row per data provider (name, url, methodology_url, coverage)
- `indicator` — annual numeric series (value, 90% CI bounds, rank, unit,
  direction, source_url, is_verified)
- `alert` — dated events (type, title, description, severity, source_url)
- `media_owner` — outlet → owner → non-media interests (all `is_official=FALSE`)

---

## Rebuild the DB from raw

```bash
cd watchdog
python -m pipeline.build_db      # reads data/raw/**, writes data/watchdog.duckdb
```
Idempotent. Raw sources are archived under `data/raw/{worldbank,rsf,vdem,
transparency,manual}/` with a `PROVENANCE.json` manifest listing every machine-
fetched source and the still-pending manual-ingest list.

---

## Add new data (the Antigravity workflow)

The watchdog is designed to grow. `docs/ANTIGRAVITY_PROMPT.md` is a copy-paste
retrieval prompt that pulls **killer additional data** as neutral, sourced CSVs:

1. **indicators.csv** — Freedom House, EIU Democracy Index, RSF sub-scores,
   CMPF Media Pluralism Monitor, CIVICUS civic-space rating.
2. **events.csv** — the full CoE-Platform / MFRR / CPJ / PEGA journalist-
   incident registries (dozens of sourced events vs the 5 hand-picked now).
3. **police_violence.csv** — the new dimension: ECtHR Art.2/3 judgments vs
   Greece, CoE CPT reports, Greek Ombudsman arbitrary-incidents counts, Amnesty
   reports, and named cases (Grigoropoulos, Zak Kostopoulos, Sampanis,
   Fragkoulis, Pylos, Nea Smyrni).
4. **sources.csv** — one row per provider (feeds the `source` table).

**To ingest returned CSVs:**
1. Drop them in `data/raw/manual/`.
2. Add a loader block in `pipeline/build_db.py` (mirror the existing
   `media_ownership.csv` block — read the CSV, `INSERT` into the matching
   table). For `police_violence.csv`, either add a `category='police_violence'`
   feed into `alert` or add a dedicated `police_violence` table + a `/police`
   endpoint.
3. Update `PROVENANCE.json` (move the source from `pending_manual_ingest` to the
   fetched list).
4. `python -m pipeline.build_db` — the provenance gate will reject any row
   missing a `source_url`.

---

## Data refresh procedure (when new figures drop each year)

- **RSF** (usually May): update `data/raw/manual/rsf_post2021.csv` with the new
  rank + verified score. Verify the rank before adding; leave the score blank if
  unverified rather than guessing.
- **V-Dem** (usually March): re-fetch the OWID grapher CSVs into `data/raw/vdem/`.
- **World Bank WGI** (usually Sept): re-fetch `wgi_greece.json` (source 3 codes
  `GOV_WGI_{CC,RL,VA,GE}.{SC,SC_LB,SC_UB}`).
- **CPI** (usually Feb): re-fetch `data/raw/transparency/owid_cpi.csv`.
- Then `python -m pipeline.build_db` and restart the API.

---

## Ethics & limits

See `docs/METHODOLOGY.md`. In short: every number is sourced; perception indices
are shown as trends with confidence intervals, not verdicts; contested data
(media ownership, state advertising) is visually flagged as unofficial; the tool
never characterizes anyone in its own voice; and correlation of declining
indicators does not by itself prove intent — the data show *what* is happening,
not *why* someone willed it.
