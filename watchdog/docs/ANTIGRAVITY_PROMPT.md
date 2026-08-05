# Antigravity retrieval prompt — killer data pull (v2, adds police violence)

Paste the block below into Antigravity. It returns 4 CSVs that map directly to
the watchdog DB tables (indicator / alert / police_violence / source). Drop the
returned files in `watchdog/data/raw/manual/` for ingestion.

Priority additions over v1: police violence & civil liberties (ECtHR Art.2/3,
Ombudsman arbitrary-incidents mechanism, CIVICUS downgrade, named cases),
RSF sub-scores, Freedom House + EIU Democracy Index, full CoE-Platform/MFRR/PEGA
journalist-incident registries.

---

ROLE: You are a data-retrieval assistant. Return SOURCED data as neutral source
reports. Do NOT editorialize, characterize, or add opinions. If a value is
uncertain or you cannot find a primary source, write UNVERIFIED in the note and
leave the value blank rather than guessing. Every single row MUST have a working
source_url. Prefer primary sources (the issuing body's own site/PDF) over news
summaries.

CONTEXT: I am populating a Greek democracy/press-freedom/rule-of-law watchdog
database. All figures are for GREECE. I need machine-ingestible CSVs.

OUTPUT: Return FOUR CSV files, each in a separate fenced code block, with these
EXACT headers.

FILE 1 — indicators.csv
headers:
source_name,indicator,year,value,unit,direction,lower_bound,upper_bound,greece_rank,total_ranked,eu_comparison,source_url,methodology_url,retrieved_date,note
A. Democracy/governance: Freedom House Freedom in the World (total /100 + PR /40
+ CL /60); Freedom House Nations in Transit (Democracy Score + Democracy %);
EIU Democracy Index (overall 0–10 + 5 categories + global rank); V-Dem (Liberal
Democracy, Electoral Democracy, Freedom of Expression, Rule of Law, 0–1); World
Bank WGI (Control of Corruption, Rule of Law, Voice & Accountability, Government
Effectiveness: percentile + 90% CI bounds). All per year 2013–2025.
B. Press freedom: RSF overall score + 5 sub-indicators (political, economic,
legislative, social, safety) per year 2022–2025 + rank + total(180); CMPF Media
Pluralism Monitor risk scores (%) for the 4 areas.
C. Corruption: TI CPI score (0–100) + rank per year.
D. Civic space: CIVICUS Monitor Greece rating + year of each rating change.

FILE 2 — events.csv
headers:
date,type,title_en,description,severity,greece_specific,source_url,methodology_url,retrieved_date,note
type ∈ surveillance|journalist_killing|journalist_attack|press_freedom|eu_report|court_ruling
Sources: CoE Platform for protection of journalism (all Greece alerts); MFRR /
Mapping Media Freedom (all Greece incidents); CPJ Greece database; EP PEGA
committee full Greece spyware timeline; ADAE wiretapping rulings; EU Rule of Law
Report Greece chapter per year 2020–2024 (one row/year, URL to that chapter).

FILE 3 — police_violence.csv
headers:
date,category,title_en,description,victim_or_scope,body_or_court,outcome,source_url,methodology_url,retrieved_date,note
category ∈ ecthr_judgment|ombudsman_report|ngo_report|individual_case|protest_policing|cpt_report
Sources: ECtHR HUDOC judgments vs Greece under Art.2 & Art.3 (police/coast-guard/
detention) — one row/judgment (case, date, article, violation found?) + per-decade
count if summarized; CoE CPT Greece visit reports; Greek Ombudsman National
Mechanism for Investigation of Arbitrary Incidents — annual complaint counts vs
police; Amnesty International Greek policing/protest reports; CIVICUS & Greek
Helsinki Monitor entries; named cases one row each (facts + legal outcome only,
no adjectives): Grigoropoulos 2008, Zak Kostopoulos 2018, Nikos Sampanis 2021,
Kostas Fragkoulis 2022, Pylos shipwreck 2023, Nea Smyrni 2021.

FILE 4 — sources.csv
headers:
source_name,issuing_body,url,methodology_url,coverage_years,indicator_type,note

RULES: Greece only; every row a real source_url; primary sources preferred;
neutral facts/dates/figures/outcomes, no characterizations; UNVERIFIED + blank
value if unconfirmed; dates YYYY-MM-DD (or YYYY); each CSV in its own code block.
