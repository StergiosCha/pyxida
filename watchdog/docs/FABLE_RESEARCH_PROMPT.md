# Fable Deep-Research Brief — Greek Democratic-Accountability Dossier

**Copy everything below the line into Fable. It is a retrieval brief, not an
essay assignment.** The goal is a *sourced record*, not a verdict. Every datapoint
you return must carry a `source_url` from a primary or authoritative body. Where a
claim is contested or unproven, label it `ALLEGED` / `UNDER_INVESTIGATION`; where a
court or prosecutor has established it, label it `ESTABLISHED` / `CONVICTED`; where
you cannot confirm it, return the row with the value blank and status `UNVERIFIED`.
Respect the presumption of innocence for open cases — report the charge and the
prosecuting body, not a guilty verdict that has not been handed down.

This dossier feeds a provenance-gated database: **a row with no source_url is
discarded.** Prefer, in order: (1) courts, prosecutors, official gazettes,
parliamentary records; (2) EU institutions and treaty bodies (EPPO, European
Parliament, ECtHR, Council of Europe); (3) named monitoring organisations (RSF,
V-Dem, Freedom House, CPJ, Amnesty, the Racist Violence Recording Network); (4)
reported journalism from outlets with a masthead, clearly marked as reporting.

Output format: one CSV per section below, columns exactly as specified, UTF-8,
one fact per row.

---

## SECTION 1 — OPEKEPE / EU agricultural-subsidy fraud (the live corruption case)

This is the most heavily documented item and the spine of the corruption strand.
Source it primarily from **EPPO** (europa.eu), the European Parliament, Politico,
Kathimerini, Balkan Insight, and the Hellenic Parliament record.

**Verified anchor points (from EPPO's own newsroom — confirm and expand each):**
- EPPO opened the OPEKEPE probe — press release dated **20 May 2025**
  (`https://www.eppo.europa.eu/en/media/news/greece-eppo-probes-opekepe-officials-over-alleged-organised-agricultural-subsidy-fraud`).
- EPPO **submitted information to the Hellenic Parliament** — **19 June 2025**
  (`https://www.eppo.europa.eu/en/media/news/alleged-misuse-eu-agricultural-funds-eppo-submits-information-to-hellenic-parliament`).
- EPPO **arrested 37 members** of an organised group — **22 Oct 2025**
  (`https://www.eppo.europa.eu/en/media/news/greece-eppo-arrests-37-members-organised-criminal-group-involved-large-scale`).
- EPPO "new developments" release — **1 April 2026**
  (`https://www.eppo.europa.eu/en/media/news/greece-new-developments-eppos-probe-large-scale-agricultural-subsidy-fraud`).

**To CONFIRM (do NOT assume — these figures circulated in reporting but must be
sourced to a primary document before use; return each with status + source_url):**
- The exact size of the file EPPO sent to parliament (a "3,000-page" figure has
  been reported — verify against EPPO/parliament).
- Which ministers / MPs / officials were named, and each resignation date, ministry,
  party, and public response (most deny — record the denial verbatim with source).
- The financial scale: the EU financial correction/fine amount (a "€415m" figure
  has circulated — verify against the European Commission / EU decision), plus any
  flat-rate or young-farmer-scheme corrections.
- Any April 2026 request to lift MP immunity, and the number of MPs — confirm
  against the parliamentary record.
- Article 86 of the Greek Constitution and how it limits EPPO's competence over
  serving/former ministers — quote EPPO's own statement on this if it exists.
- The agency's closure / transfer of functions to the tax authority (AADE).

CSV columns: `date, event, person, role_party, financial_amount_eur, status,
source_body, source_url`

## SECTION 2 — Surveillance: Predator spyware & the wiretap scandal ("υποκλοπές")

Source from the **European Parliament PEGA committee** final report, **ADAE**
(the Greek communications-privacy authority), ECtHR filings, Citizen Lab, and
reporting by Reporters United, Inside Story, EfSyn.

Retrieve:
- The EYP (national intelligence service) wiretaps of journalists and politicians,
  including PASOK leader Nikos Androulakis (an MEP at the time) and journalist
  Thanasis Koukakis.
- The Predator commercial-spyware infections: who was targeted, on what dates, per
  Citizen Lab / PEGA.
- The PEGA committee's Greece findings and the ADAE rulings/fines.
- Any prosecutions, resignations (e.g. the general secretary to the PM, the EYP
  head, 2022), and the parliamentary-committee outcome.

CSV columns: `date, target_name, target_role, method, finding, oversight_body,
status, source_url`

## SECTION 3 — Press freedom & media capture

Source from **RSF**, the **Council of Europe Platform for the Safety of
Journalists**, the **Media Freedom Rapid Response (MFRR)**, **CMPF Media Pluralism
Monitor**, CPJ, and the EU Rule of Law reports (Greece chapter).

Retrieve:
- RSF sub-scores for Greece (political, economic, legislative, social, security
  context) 2022–2025, not just the headline rank.
- The murder of Giorgos Karaivaz (2021) and prosecution status.
- Media-ownership concentration: outlet → owner → owner's other business interests
  (shipping, energy, construction, telecoms), for the main TV/press groups. Flag
  every ownership figure as monitor-sourced/contested unless it is in a filing.
- **State advertising allocation** — the "λίστα Πέτσα" (2020 COVID public-health
  campaign, ~€20m) and any later state-advertising distributions, with the
  criteria used and criticism of them.

CSV columns: `indicator_or_outlet, owner_or_value, owner_interests, year,
is_official, source_body, source_url`

## SECTION 4 — Police violence & civil liberties

Source from the **ECtHR** (HUDOC database), the **Council of Europe CPT**, the
**Greek Ombudsman** (Συνήγορος του Πολίτη — the designated police-misconduct
mechanism), the **Racist Violence Recording Network (RVRN)**, Amnesty
International, and CIVICUS Monitor.

Retrieve:
- ECtHR judgments against Greece under Articles 2/3 (right to life; prohibition of
  ill-treatment) involving police, with case name, application number, date,
  finding.
- CPT periodic-visit reports on Greek police detention and any findings of
  ill-treatment.
- Ombudsman annual figures on police-arbitrariness complaints.
- Named cases in the public record (e.g. the 2008 killing of Alexis Grigoropoulos;
  deaths/injuries in custody or in protest policing) — with court outcome.
- The CIVICUS Monitor civic-space rating trajectory for Greece.

CSV columns: `date, case_or_report, body_or_court, article_or_scope, finding,
status, source_url`

## SECTION 5 — Far-right, antisemitism, and the Golden Dawn record

This is where "fact vs characterisation" matters most — pull **the documented
public record only**, and let it stand. Source from Greek court records, the
**RVRN**, the **Antisemitism monitors** (the EU FRA, the US State Department
Religious-Freedom reports, community bodies such as the Central Board of Jewish
Communities in Greece / KIS), and the European Parliament.

Retrieve:
- The 2020 Athens court ruling that **Golden Dawn (Χρυσή Αυγή) was a criminal
  organisation** — verdict date, sentences, the leadership convicted. This is
  ESTABLISHED (court judgment).
- Successor far-right parties in parliament (Spartans/Σπαρτιάτες, Greek
  Solution/Ελληνική Λύση, Niki/ΝΙΚΗ) — seats, dates entering parliament, any
  court/electoral-commission actions against them.
- RVRN annual counts of racist and antisemitic incidents, with year and the
  reporting methodology.
- Documented, on-the-record antisemitic acts/statements by public figures — with
  the exact source (video, transcript, court filing). **Attribute only what a
  primary source shows; do not infer.** For any sitting official, record the
  documented fact (e.g. prior membership of a specific party; a specific
  documented statement with date and source) and its status — never a bare
  "is a Nazi" label, which no source substantiates and which would sink the
  dossier's credibility.
- FRA / State Department findings on antisemitism in Greece.

CSV columns: `date, actor, documented_fact, category, court_or_monitor, status,
source_url`

## SECTION 6 — Named-individual public record (accountability index)

For each named public figure below, return **only sourced, on-the-record facts** —
offices held with dates, documented statements (with source), court cases /
investigations naming them (with prosecuting body and status), and party history.
Distinguish `ESTABLISHED` from `ALLEGED`/`UNDER_INVESTIGATION`. Include their
public responses/denials. Do NOT return characterisations, only the record.

- **Kyriakos Mitsotakis** (PM) — Predator/wiretap chain of command; Article 86
  invocations; OPEKEPE oversight questions.
- **Kyriakos Pierrakakis** (Education minister; former Digital Governance) — role
  in the non-state-universities law (ν.5094/2024); digital-governance tenure.
- **Adonis Georgiadis** (Health minister) — documented LAOS (Λαϊκός Ορθόδοξος
  Συναγερμός) party history; the documented record around books he promoted on his
  former TV channel; on-the-record statements. Source each precisely.
- **OPEKEPE-named ministers** (Voridis, Avgenakis, and others in the EPPO file) —
  the specific allegation, prosecuting body, status, and their denial.

CSV columns: `person, office, dated_fact, source_type, status, response, source_url`

---

## Discipline recap (read before returning)

1. **Every row needs a source_url.** No URL → drop the row.
2. **Status labels are mandatory:** ESTABLISHED / CONVICTED, ALLEGED /
   UNDER_INVESTIGATION, UNVERIFIED. Presumption of innocence on open cases.
3. **Primary sources beat reporting; reporting beats aggregators.**
4. **Report the record, not a verdict.** The dossier persuades by accumulation of
   sourced fact, not by adjectives. A reader hostile to the thesis should be unable
   to find a single unsourced or overstated line.
5. Return one CSV per section, plus a `sources.csv` (source_id, issuing_body, url,
   type) mapping every URL you used.
