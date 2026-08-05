-- Watchdog indicator DB — every row carries its own provenance.
-- Engine: DuckDB (MVP). No datapoint may exist without a source_url.

CREATE TABLE IF NOT EXISTS source (
    source_id     VARCHAR PRIMARY KEY,   -- 'worldbank_wgi', 'owid_vdem_libdem', ...
    name          VARCHAR NOT NULL,      -- full producer name
    url           VARCHAR NOT NULL,      -- landing / index page
    methodology   VARCHAR,               -- one-line method description
    methodology_url VARCHAR,
    coverage      VARCHAR                 -- e.g. '1996-2024'
);

-- One row per (source, indicator, year) measurement.
CREATE TABLE IF NOT EXISTS indicator (
    source_id     VARCHAR NOT NULL REFERENCES source(source_id),
    indicator     VARCHAR NOT NULL,      -- 'Liberal democracy index', 'Press Freedom rank', ...
    year          INTEGER NOT NULL,
    value         DOUBLE,                -- the measured value (NULL if only a rank)
    unit          VARCHAR,               -- '0-1', '0-100', 'rank', 'percentile'
    lower_bound   DOUBLE,                -- CI lower (WGI); NULL if none
    upper_bound   DOUBLE,
    rank          INTEGER,               -- global rank (RSF etc.); NULL if not a rank series
    total_ranked  INTEGER,
    direction     VARCHAR,               -- 'higher_better' | 'lower_better' | 'rank_lower_better'
    is_verified   BOOLEAN DEFAULT TRUE,  -- FALSE => manually entered, pending confirmation
    note          VARCHAR,
    source_url    VARCHAR NOT NULL,      -- the specific citation URL (mandatory)
    retrieved     DATE,
    PRIMARY KEY (source_id, indicator, year)
);

-- Discrete press-freedom / rule-of-law events (not time series).
CREATE TABLE IF NOT EXISTS alert (
    alert_id      INTEGER PRIMARY KEY,
    date          DATE NOT NULL,
    type          VARCHAR,               -- 'surveillance','journalist_killing','eu_report',...
    title_el      VARCHAR NOT NULL,
    description   VARCHAR,
    severity      VARCHAR,               -- 'high'|'medium'|'low'
    source_url    VARCHAR NOT NULL,
    is_verified   BOOLEAN DEFAULT TRUE
);

-- Media ownership (structured, sourced; contested figures flagged).
CREATE TABLE IF NOT EXISTS media_owner (
    outlet        VARCHAR NOT NULL,
    outlet_type   VARCHAR,               -- 'TV','newspaper','radio','digital'
    owner         VARCHAR,
    owner_interests VARCHAR,             -- principal non-media business interests
    is_official   BOOLEAN DEFAULT FALSE, -- FALSE => media/monitor-sourced, not a public filing
    source_url    VARCHAR NOT NULL,
    note          VARCHAR,
    PRIMARY KEY (outlet, owner)
);

-- Police violence / civil-liberties incidents (court rulings, oversight reports, named cases).
CREATE TABLE IF NOT EXISTS police_violence (
    pv_id         INTEGER PRIMARY KEY,
    date          VARCHAR,               -- YYYY-MM-DD or YYYY (some rows year-only)
    category      VARCHAR,               -- ecthr_judgment|ombudsman_report|ngo_report|individual_case|protest_policing|cpt_report
    title_en      VARCHAR NOT NULL,
    description   VARCHAR,
    victim_or_scope VARCHAR,
    body_or_court VARCHAR,
    outcome       VARCHAR,
    source_url    VARCHAR NOT NULL,
    methodology_url VARCHAR,
    note          VARCHAR
);

-- Accountability dossier (Fable sourced record): OPEKEPE, surveillance,
-- far-right/Golden Dawn, and named-individual public record. Every row carries a
-- status label (ESTABLISHED/CONVICTED/ALLEGED/UNDER_INVESTIGATION) and a source_url.
CREATE TABLE IF NOT EXISTS dossier (
    d_id          INTEGER PRIMARY KEY,
    section       VARCHAR NOT NULL,      -- Greek section label
    date          VARCHAR,               -- YYYY / YYYY-MM / YYYY-MM-DD, may be blank
    title         VARCHAR NOT NULL,
    detail        VARCHAR,
    actor         VARCHAR,               -- person/entity
    role          VARCHAR,               -- office/party/category
    status        VARCHAR NOT NULL,      -- ESTABLISHED|CONVICTED|ALLEGED|UNDER_INVESTIGATION|UNVERIFIED
    response      VARCHAR,               -- subject's public response/denial where recorded
    source_body   VARCHAR,               -- issuing body (court/prosecutor/monitor/reporting)
    source_url    VARCHAR NOT NULL,
    amount_eur    VARCHAR
);

-- Convenience view: latest value per indicator.
CREATE VIEW IF NOT EXISTS v_indicator_latest AS
SELECT i.* FROM indicator i
JOIN (SELECT source_id, indicator, MAX(year) my FROM indicator GROUP BY 1,2) m
  ON i.source_id=m.source_id AND i.indicator=m.indicator AND i.year=m.my;
