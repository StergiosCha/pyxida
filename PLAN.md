# PLAN.md — «Πυξίδα ΑΕΙ»

Build plan, schema rationale, deviations, and Phase 0 download manifest.
Source of truth: *Greek AEI Admissions Data Landscape 2016–2026* (attached report).
**Status: awaiting schema approval + network grants before Phase 0 executes.**

---

## 0. The one blocker that gates everything: network allowlist

This agent runs in a network-sandboxed environment. I probed all six primary
data hosts from the sandbox; **every one is currently blocked**:

| Host | Probe result | Meaning |
|---|---|---|
| `www.data.gov.gr` | `000` (conn refused at proxy) | blocked |
| `catalog.data.gov.gr` | `403` from proxy | blocked |
| `aeitei.gr` | `000` | blocked |
| `results.it.minedu.gov.gr` | `000` | blocked |
| `www.minedu.gov.gr` | `000` | blocked |

These are Greek government / third-party mirror domains, not on the science-API
allowlist. **Nothing in Phase 0 downloads until these are granted.** I have
issued `request_network_access` for the required domains — approve them (or tell
me to proceed on synthetic seed data) and Phase 0 runs end-to-end without
further check-ins, as instructed.

Second-order blockers anticipated (from report §7 Caveats):
- **minedu.gov.gr & data.gov.gr search disallow automated fetching.** Plan: hit
  the data.gov.gr *dataset download endpoints* and aeitei *direct file URLs*
  only (not the search UI); rate-limit ≥2s/request; cache to `/data/raw`; one
  fetch per file, ever (idempotent — skip if checksum present).
- **aeitei.gr is a third-party mirror** — its files are the cleanest machine-
  readable copy of Ministry Excel, but for any authoritative/legal display we
  cross-check against the Ministry results portal. Provenance table records
  `kind='mirror'` vs `'official'` so the UI can flag it.
- **data.gov.gr may need an API token.** If the download endpoint 401/403s on
  auth (not sandbox), I'll surface it and fall back to the aeitei Excel spine.
- **ΟΠΕΣΠ micro-data is credential-gated** — out of scope for automated Phase 0;
  flagged as a manual professor-via-ΜΟΔΙΠ enrichment in README.

**Fallback if grants are denied:** I generate a small, clearly-labelled
`kind='synthetic'` seed dataset (realistic shapes, anchored to the report's
published figures — Ιατρική Αθήνας range, εισακτέοι totals, κενές θέσεις per
year) so the pipeline, DB, API, MVP UI, and backtest harness are all built and
demonstrable. Every synthetic row is `is_official=FALSE` and visually flagged.
Swapping in real data later is one ingestion run.

---

## 1. Data model rationale (see `schema.sql` for full DDL)

- **Central fact `admission`** at grain **(dept_code, year, category)**. Category
  is part of the key because ΓΕΛ90 / ΓΕΛ10 / ΕΠΑΛ90 / ΕΠΑΛ10 / ειδικές each have
  their own βάση and seat pool — collapsing them would corrupt fill-rate and ΕΒΕ
  logic. Most analysis/forecasting uses `category='ΓΕΛ90'` (the 90% mainstream).
- **Stable key = Ministry `dept_code`** (κωδικός τμήματος), per the prompt.
  Historical codes/names that don't match resolve through **`dept_alias`**
  (relation ∈ rename/merge/split/tei_absorption/move/recode). The 2018–2019 ΤΕΙ
  absorption is the big discontinuity — modelled as `tei_absorption` alias rows.
- **Provenance is a table, not a column-afterthought.** `source` holds URL, local
  path, checksum, license, `is_official`. Every `admission`/`field_ebe`/`nppe`
  row carries `source_id` (NOT NULL on facts). This satisfies "every displayed
  number traceable to a source file + year."
- **ΕΒΕ modelled per ν.4777/2021 exactly:** `field_ebe(year, field)` stores the
  field mean and `ebe_base = field_mean × 0.80`; department threshold =
  `ebe_base × ebe_coefficient` (coefficient 0.80–1.20 on `admission`). This lets
  the forecaster model the ΕΒΕ floor as a *separate constraint* from demand:
  `predicted βάση = max(ebe_floor_est, demand_est)`.
- **`vacancy_cause`** ('ebe'|'demand'|'mixed') captures the report's key finding
  that ~85% of 2025 vacancies were ΕΒΕ-driven, where analyst attribution exists.
- **Predictions never point-only:** `prediction` stores 80% and 95% intervals +
  the separate `ebe_floor_est`/`demand_est`; `backtest_score` enforces the
  ship-only-if-beats-baseline rule with MAE, skill, and PI coverage.
- **ΝΠΠΕ** in its own table with `enrollment_is_official` → the UI "media-sourced"
  flag (UNIC ~300 stays unofficial); `public_analog_dept` anchors side-by-side.

**Deviation flags (asking per prompt's "ask before deviating on data model"):**
1. **DuckDB for MVP, not Postgres.** Report and prompt both allow it; DDL is
   written portable (no DuckDB-only types) so a `sed` migration to Postgres is
   trivial. → *confirm DuckDB is fine for MVP.*
2. **Split `admission` by category rather than one wide row per dept-year.**
   This is a normalization choice not spelled out in the prompt's column list
   (which reads as one flat table). I believe per-category is correct for ΕΒΕ
   and fill-rate fidelity. → *confirm, or I flatten to ΓΕΛ90-only wide.*
3. **`dept_field` M:N side table** because some τμήματα accept from multiple
   πεδία. Minor addition to the prompt's single `επιστημονικό πεδίο` column.

Everything else follows the prompt's column list verbatim.

---

## 2. Phase 0 download manifest (exact files, in fetch order)

Archived under `/data/raw/{source}/{year}/`. Rate-limited ≥2s, checksummed,
idempotent.

**A. aeitei.gr — Ministry Excel mirror (primary spine, machine-readable XLS)**
- `https://aeitei.gr/vaseis/2025/baseis-2025.zip`  (all categories, 2025)
- `https://aeitei.gr/vaseis/2025/sig-2025-2024.zip` (2025-vs-2024 comparison)
- `https://aeitei.gr/vaseis/2025/gel-2025.xls`  (ΓΕΛ 90% 2025)
- `https://aeitei.gr/vaseis/2025/epal-2025.xls`  (ΕΠΑΛ 90% 2025)
- Per-year bundles 2016→2024: `https://aeitei.gr/vaseis/{year}/baseis-{year}.zip`
  (probe pattern per year; log any 404 to fall back to data.gov.gr for that year)

**B. data.gov.gr — minedu open datasets (CSV, authoritative, 2015→)**
- Dataset landing (per year): `catalog.data.gov.gr/dataset/vaseis-eisagwgis-{year}`
- CSV resource download endpoints harvested from each dataset's resource list
  (βάσεις, γραπτοί βαθμοί, προτιμήσεις, στατιστικά μορίων).
- Years: 2015 → 2025.

**C. Enrichment (lower priority, feature-flagged consumers)**
- ΕΒΕ 2026 coefficients: Υ.Α. Φ.253/160742/A5/10-12-2025 (ΦΕΚ) — for what-if sim.
- ΕΘΑΑΕ 2024 annual report PDF (employability indicators) — PDF extraction.
- ΝΠΠΕ: hand-curated from report §4 (4 institutions, ~26 programs, tuition,
  UNIC≈300 media-sourced) → `nppe_program` seed, all `is_official=FALSE` unless
  ΦΕΚ-backed.

---

## 3. Build order (deliverables map to prompt §DELIVERABLES)

1. **PLAN.md + schema.sql** ← *this step; awaiting approval.*
2. **Pipeline** (`pipeline/`): `fetch.py` (per-source, idempotent), `normalize.py`
   (→ canonical), `crosswalk.py` (alias resolution + unmatched log), `build_db.py`
   (one command rebuilds DB from `/data/raw`), `qa.py` (row counts/year, missing
   profile, 5 sanity checks). **QA gate must pass before Phase 2.**
3. **QA report** (`docs/qa_report.md` + figures): per-year row counts, missing-
   value heatmap, sanity-check table.
4. **MVP app (Phase 2)**: FastAPI (`/departments`, `/departments/{id}/history`,
   `/stats/fields`, `/stats/vacancies`, `/nppe`, `/calc/eligibility`) + React/TS
   frontend (search & dept profile, stats dashboard w/ κενές θέσεις heatmap +
   at-risk index, μόρια+eligibility calculator, ΝΠΠΕ module). Greek UI.
5. **Backtest report** (`models/`): baseline carry-forward vs candidate models
   (hierarchical Bayesian / GBM), MAE-vs-baseline table over 2022–2025, PI
   coverage, "structural break 2021" caveat. Ship only if it beats baseline.
6. **RAG advisor** (`rag/`, feature-flagged): retrieval over DB rows + report;
   never free-generates βάσεις; 10 Greek Q&A transcripts demonstrating grounding.
7. **README.md** (EL + EN): setup, July data-refresh procedure, retraining.

---

## 4. QA gate — the 5 sanity checks (from prompt §Phase0.4)

1. Ιατρική Αθήνας (ΕΚΠΑ) βάση within a known plausible band (~18,000–19,500 μόρια).
2. Σum(seats_offered) per year matches report εισακτέοι series (±tolerance):
   2024-25 ≈ 68,851; 2025-26 ≈ 68,788 base.
3. Σκενές θέσεις per year ≈ report figures (2021≈17k, 2022≈11k, 2023≈10k,
   2024≈10k, 2025 ΓΕΛ = 10,636).
4. No `admission` row with `admitted > seats_offered`; `0 ≤ fill_rate ≤ 1`.
5. All `ebe_coefficient` (post-2021) within [0.80, 1.20]; ΕΒΕ absent pre-2021.

Plus: every unmatched dept logged to `unmatched_dept`; every fact row has a
`source_id`; row counts per year reported.
