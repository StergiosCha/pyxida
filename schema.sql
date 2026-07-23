-- ============================================================================
-- «Πυξίδα ΑΕΙ» — Canonical schema (DuckDB dialect; Postgres notes inline)
-- ν.4777/2021 (ΕΒΕ) + ν.5094/2024 (ΝΠΠΕ) aware.
-- Grain of the central fact: one row per (τμήμα_code, year, candidate_category).
-- Every fact row is source-traceable via a FK into `source`.
-- ----------------------------------------------------------------------------
-- Portability: DuckDB uses INTEGER/DOUBLE/VARCHAR/BOOLEAN and sequences via
-- CREATE SEQUENCE. On Postgres: swap `INTEGER DEFAULT nextval(...)` for SERIAL/
-- IDENTITY, DOUBLE -> DOUBLE PRECISION, BOOLEAN identical. No DuckDB-only types
-- are used so a single `sed` migration is viable.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 0. SOURCE REGISTRY  (provenance is first-class — NON-NEGOTIABLE)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS source (
    source_id       INTEGER PRIMARY KEY,
    name            VARCHAR NOT NULL,        -- 'data.gov.gr minedu', 'aeitei.gr', 'ΦΕΚ', 'press'
    kind            VARCHAR NOT NULL,        -- 'official' | 'mirror' | 'press' | 'analyst' | 'synthetic'
    url             VARCHAR,                 -- exact download/landing URL
    local_path      VARCHAR,                 -- /data/raw/{source}/{year}/{file}
    retrieved_at    TIMESTAMP,
    checksum_sha256 VARCHAR,
    license         VARCHAR,                 -- 'open data' | 'terms apply' | 'n/a'
    is_official     BOOLEAN DEFAULT FALSE,   -- drives the "unofficial" UI flag
    note            VARCHAR
);

-- ---------------------------------------------------------------------------
-- 1. INSTITUTIONS (ίδρυμα)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS institution (
    institution_id  INTEGER PRIMARY KEY,
    name            VARCHAR NOT NULL,        -- 'Εθνικό & Καποδιστριακό Παν. Αθηνών'
    short_name      VARCHAR,                 -- 'ΕΚΠΑ'
    inst_type       VARCHAR NOT NULL,        -- 'ΑΕΙ' | 'former_ΤΕΙ' | 'ΝΠΠΕ' | 'στρατιωτική' | 'αστυνομική' | 'εκκλησιαστική'
    is_state        BOOLEAN DEFAULT TRUE,    -- FALSE for ΝΠΠΕ (ν.5094/2024)
    city            VARCHAR,
    region          VARCHAR,                 -- περιφέρεια (for regional-hardest-hit analysis)
    founded_year    INTEGER,
    parent_name     VARCHAR,                 -- ΝΠΠΕ: foreign parent (e.g. 'University of Nicosia')
    note            VARCHAR
);

-- ---------------------------------------------------------------------------
-- 2. DEPARTMENTS (τμήμα) — keyed by the stable Ministry κωδικός
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS department (
    dept_code       VARCHAR PRIMARY KEY,     -- Ministry κωδικός τμήματος (canonical, stable)
    name            VARCHAR NOT NULL,        -- current canonical name
    institution_id  INTEGER NOT NULL REFERENCES institution(institution_id),
    city            VARCHAR,                 -- normalised matching key (lowercase, accent-stripped)
    city_display    VARCHAR,                 -- display-cased city for UI/labels (e.g. 'Ηράκλειο')
    nuts3           VARCHAR,                 -- NUTS-3 regional-unit code -> city_context(nuts3)
    scientific_field VARCHAR,                -- '1ο' | '2ο' | '3ο' | '4ο' (επιστημονικό πεδίο); multi-field depts -> see dept_field
    status          VARCHAR DEFAULT 'active',-- 'active' | 'abolished' | 'merged' | 'moved' | 'suspended'
    status_year     INTEGER,                 -- year the status change took effect
    merger_signal   BOOLEAN DEFAULT FALSE,   -- from report §3 restructuring watch-list
    first_seen_year INTEGER,
    last_seen_year  INTEGER,
    note            VARCHAR
);

-- Regional context per NUTS-3 unit (Eurostat) — joined to departments via city.
-- Tourism intensity, cost proxy (GDP/capita), metro flag. Used by
-- the state-vs-private erosion analysis (does regional cost/tourism predict
-- post-ΕΒΕ demand collapse?). Provenance: Eurostat NUTS-3 (no rent series exists).
CREATE TABLE IF NOT EXISTS city_context (
    nuts3              VARCHAR PRIMARY KEY,   -- NUTS-3 regional-unit code (e.g. EL431 Ηράκλειο)
    region             VARCHAR,               -- English label from Eurostat
    tourism_nights     BIGINT,                -- nights at tourist accommodation, 2023
    population         BIGINT,                -- resident population, 2023
    tourism_per_capita DOUBLE,                -- nights / resident (tourism intensity)
    gdp_per_capita     INTEGER,               -- EUR, 2022 (cost-of-living proxy)
    is_metro           BOOLEAN DEFAULT FALSE, -- Athens core / Piraeus / Thessaloniki
    source_note        VARCHAR
);

-- A department can belong to more than one επιστημονικό πεδίο. M:N side table.
CREATE TABLE IF NOT EXISTS dept_field (
    dept_code       VARCHAR NOT NULL REFERENCES department(dept_code),
    field           VARCHAR NOT NULL,        -- '1ο'..'4ο'
    PRIMARY KEY (dept_code, field)
);

-- ---------------------------------------------------------------------------
-- 3. CROSSWALK / ALIAS  (handles 2018–2019 ΤΕΙ absorption, renames, merges)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dept_alias (
    alias_id        INTEGER PRIMARY KEY,
    alias_code      VARCHAR,                 -- historical code as it appeared that year (nullable if name-only match)
    alias_name      VARCHAR NOT NULL,        -- historical name as printed
    canonical_code  VARCHAR NOT NULL REFERENCES department(dept_code),
    year_from       INTEGER,
    year_to         INTEGER,
    relation        VARCHAR NOT NULL,        -- 'rename' | 'merge' | 'split' | 'tei_absorption' | 'move' | 'recode'
    confidence      VARCHAR DEFAULT 'high',  -- 'high' | 'medium' | 'low' (fuzzy match)
    note            VARCHAR
);

-- Unmatched departments log (QA requirement: "Log every unmatched department")
CREATE TABLE IF NOT EXISTS unmatched_dept (
    raw_code        VARCHAR,
    raw_name        VARCHAR,
    year            INTEGER,
    category        VARCHAR,
    source_id       INTEGER REFERENCES source(source_id),
    reason          VARCHAR
);

-- ---------------------------------------------------------------------------
-- 4. CENTRAL FACT — admissions per department / year / category
--    grain: (dept_code, year, category)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS admission (
    dept_code       VARCHAR NOT NULL REFERENCES department(dept_code),
    year            INTEGER NOT NULL,
    category        VARCHAR NOT NULL,        -- 'ΓΕΛ90' | 'ΓΕΛ10' | 'ΕΠΑΛ90' | 'ΕΠΑΛ10' | 'ειδικές' | 'σειρά'
    base_last       DOUBLE,                  -- βάση = μόρια τελευταίου εισαχθέντος
    grade_first     DOUBLE,                  -- μόρια πρώτου εισαχθέντος
    seats_offered   INTEGER,                 -- εισακτέοι
    admitted        INTEGER,                 -- εισαχθέντες
    vacancies       INTEGER,                 -- κενές θέσεις (seats_offered - admitted, or reported)
    fill_rate       DOUBLE,                  -- admitted / seats_offered
    ebe_coefficient DOUBLE,                  -- department coefficient 0.80–1.20 (post-2021)
    ebe_threshold   DOUBLE,                  -- ΕΒΕ absolute μόρια floor applied this dept/year
    vacancy_cause   VARCHAR,                 -- 'ebe' | 'demand' | 'mixed' | NULL (from analyst attribution where known)
    source_id       INTEGER NOT NULL REFERENCES source(source_id),
    provenance_note VARCHAR,
    PRIMARY KEY (dept_code, year, category)
);

-- ---------------------------------------------------------------------------
-- 5. ΕΒΕ FIELD BASE  (ν.4777/2021 mechanics: field mean-of-means × 0.80)
--    department ΕΒΕ threshold = field_ebe_base × ebe_coefficient
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS field_ebe (
    year            INTEGER NOT NULL,
    field           VARCHAR NOT NULL,        -- '1ο'..'4ο'
    field_mean      DOUBLE,                  -- μέσος όρος επιδόσεων του πεδίου
    ebe_base        DOUBLE,                  -- field_mean × 0.80 (statutory minimum multiplier)
    source_id       INTEGER REFERENCES source(source_id),
    PRIMARY KEY (year, field)
);

-- ---------------------------------------------------------------------------
-- 5b. ΕΒΕ COEFFICIENTS BY YEAR  (incl. pre-announced years with no results yet)
--     2024/2025 come from the open-data ΕΒΕ files (same values that sit on the
--     admission rows); 2026 comes from ΥΑ Φ.253/160742/Α5 (ΦΕΚ Β' 6782/2025),
--     published December 2025 — i.e. before any 2026 admission row can exist.
--     The what-if simulator reads next-year coefficients from here.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dept_ebe_coef (
    year                    INTEGER NOT NULL,
    dept_code               VARCHAR NOT NULL,
    ebe_coefficient         DOUBLE,          -- 0.80-1.20
    ebe_special_coefficient DOUBLE,          -- ειδικά/μουσικά μαθήματα, if any
    source_note             VARCHAR,
    PRIMARY KEY (year, dept_code)
);

-- ---------------------------------------------------------------------------
-- 6. CANDIDATE VOLUME  (demand feature for forecasting)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS candidate_volume (
    year            INTEGER NOT NULL,
    category        VARCHAR NOT NULL,        -- 'ΓΕΛ' | 'ΕΠΑΛ'
    field           VARCHAR,                 -- '1ο'..'4ο' | NULL for totals
    n_candidates    INTEGER,
    cohort_size     INTEGER,                 -- demographic cohort (18-yr-old population proxy)
    source_id       INTEGER REFERENCES source(source_id),
    PRIMARY KEY (year, category, field)
);

-- ---------------------------------------------------------------------------
-- 7. ΝΠΠΕ — non-state universities (ν.5094/2024)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS nppe_program (
    nppe_id         INTEGER PRIMARY KEY,
    institution     VARCHAR NOT NULL,        -- 'UNIC Athens', 'CITY/York', 'Keele Greece', 'Anatolia/Open University'
    parent_uni      VARCHAR,                 -- 'University of Nicosia' etc.
    city            VARCHAR,
    program         VARCHAR NOT NULL,        -- 'Ιατρική', 'Νομική', ...
    degree_years    INTEGER,                 -- 4 (ν.5094 requires 4-year)
    tuition_eu      DOUBLE,                  -- €/yr EU students
    tuition_intl    DOUBLE,                  -- €/yr international
    certified       BOOLEAN,                 -- certified for 2025-26?
    certified_date  DATE,
    enrollment      INTEGER,                 -- first-year enrollment IF known
    enrollment_is_official BOOLEAN DEFAULT FALSE,  -- FALSE => UI flags as media-sourced
    public_analog_dept VARCHAR,  -- descriptive public-programme comparison anchor (free text)
    source_id       INTEGER REFERENCES source(source_id),
    note            VARCHAR
);

-- ---------------------------------------------------------------------------
-- 8. PREDICTIONS  (Phase 3 — always with intervals; no bare point forecast)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prediction (
    dept_code       VARCHAR NOT NULL REFERENCES department(dept_code),
    target_year     INTEGER NOT NULL,
    category        VARCHAR NOT NULL,
    model_name      VARCHAR NOT NULL,        -- 'baseline_carry' | 'hbayes' | 'gbm' | 'ensemble'
    point           DOUBLE,                  -- = max(ebe_floor_est, demand_est)
    lower_80        DOUBLE,
    upper_80        DOUBLE,
    lower_95        DOUBLE,
    upper_95        DOUBLE,
    ebe_floor_est   DOUBLE,                  -- modelled ΕΒΕ_t+1 floor (separate from demand)
    demand_est      DOUBLE,                  -- demand-driven βάση estimate
    baseline_pred   DOUBLE,                  -- last-year carry-forward
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (dept_code, target_year, category, model_name)
);

-- Backtest scorecard (must beat baseline to ship — NON-NEGOTIABLE)
CREATE TABLE IF NOT EXISTS backtest_score (
    model_name      VARCHAR NOT NULL,
    test_year       INTEGER NOT NULL,        -- 2022..2025
    segment         VARCHAR,                 -- 'all' | field | region
    mae             DOUBLE,                  -- mean absolute error in μόρια
    baseline_mae    DOUBLE,
    skill           DOUBLE,                  -- 1 - mae/baseline_mae
    coverage_80     DOUBLE,                  -- empirical PI coverage
    coverage_95     DOUBLE,
    n               INTEGER,
    PRIMARY KEY (model_name, test_year, segment)
);

-- ---------------------------------------------------------------------------
-- Convenience views
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW v_department_latest AS
SELECT d.dept_code, d.name, i.short_name AS institution, d.city, d.scientific_field,
       d.status, d.merger_signal,
       a.year, a.category, a.base_last, a.seats_offered, a.admitted,
       a.vacancies, a.fill_rate, a.ebe_coefficient, a.ebe_threshold
FROM department d
JOIN institution i USING (institution_id)
LEFT JOIN admission a ON a.dept_code = d.dept_code
WHERE a.year = (SELECT MAX(year) FROM admission a2 WHERE a2.dept_code = d.dept_code);

-- "Departments at risk" scoring inputs (low demand + high vacancy + merger signal)
CREATE OR REPLACE VIEW v_risk_inputs AS
SELECT a.dept_code, a.year, a.category,
       a.fill_rate,
       1.0 - a.fill_rate                              AS vacancy_rate,
       a.admitted,
       d.merger_signal,
       (a.base_last - a.ebe_threshold)                AS margin_over_ebe
FROM admission a
JOIN department d USING (dept_code)
WHERE a.category = 'ΓΕΛ90';
