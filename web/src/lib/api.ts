// Typed client for the Πυξίδα ΑΕΙ FastAPI backend.
const BASE = import.meta.env.VITE_API_BASE ?? "/api";

async function get<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  const url = new URL(BASE + path, window.location.origin);
  if (params)
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
    });
  const r = await fetch(url.toString());
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json() as Promise<T>;
}

// ── types ────────────────────────────────────────────────────────────────
export interface Meta {
  years: number[];
  categories: string[];
  fields: { id: string; label: string }[];
  subjects: { id: string; label: string }[];
  counts: Record<string, number>;
  gap_years: number[];
  features: { predictions: boolean; rag: boolean };
}

export interface DeptRow {
  dept_code: string; name: string; institution: string | null; city: string | null;
  scientific_field: string | null; base_last: number | null;
  seats_offered: number | null; admitted: number | null;
  vacancies: number | null; fill_rate: number | null;
  ebe_coefficient: number | null; ebe_threshold: number | null;
}
export interface DeptList { total: number; limit: number; offset: number; items: DeptRow[]; }

export interface HistoryRow {
  year: number; category: string; base_last: number | null; grade_first: number | null;
  seats_offered: number | null; admitted: number | null; vacancies: number | null;
  fill_rate: number | null; ebe_coefficient: number | null; ebe_threshold: number | null;
  provenance_note: string | null;
}
export interface DemandRow {
  year: number; pref1: number; pref2: number; pref3: number;
  pref_other: number; pref_total: number;
}
export interface DeptProfile {
  department: Record<string, unknown> & { dept_code: string; name: string; institution: string | null };
  category: string; history: HistoryRow[];
  aliases: { alias_code: string; alias_name: string; relation: string; confidence: string }[];
  demand?: DemandRow[] | null;
}

export interface DemandPoint {
  dept_code: string; name: string; city: string; field: string;
  seats: number; vac: number; base: number; pref1: number; pref_total: number;
  vacancy_rate: number | null; demand_per_seat: number | null;
}
export interface DemandResp {
  available: boolean; year?: number; category?: string; n?: number;
  rows: DemandPoint[]; note?: string;
}

export interface FieldStat {
  year: number; field: string; n: number; median_base: number; mean_base: number; vacancies: number;
}
export interface CityStat {
  city: string; n_depts: number; n_institutions: number; institutions: string;
}
export interface VacancyStats {
  by_year: { year: number; vacancies: number; seats: number; vacancy_rate: number }[];
  worst_latest: { dept_code: string; name: string; institution: string; year: number;
    vacancies: number; seats_offered: number; fill_rate: number }[];
}
export interface RiskItem {
  dept_code: string; name: string; institution: string | null; city: string | null;
  scientific_field: string | null; base_last: number | null; seats_offered: number;
  vacancies: number; fill_rate: number; vacancy_rate: number; risk_score: number;
  components: { vacancy: number; low_fill: number; merger: number }; risk_band: string;
}
export interface RiskStats { year: number; category: string; n: number; items: RiskItem[]; }
export interface RegionRow { nuts3: string; region: string; n_dept: number;
  avg_vacancy: number; admitted: number; avg_margin_ebe: number | null;
  is_metro: boolean; population: number | null; gdp_per_capita: number | null; }
export interface RegionsResp { year: number; category: string; n_regions: number;
  source_note: string; regions: RegionRow[]; }
export interface ProjRegion { region: string; nuts3: string; is_metro: boolean; n_points: number;
  latest_year: number; latest_vacancy: number; proj_vacancy: number; proj_lo: number;
  proj_hi: number; slope_per_year: number; at_ceiling: boolean; }
export interface ProjResp { target_year: number; category: string; model: string;
  n_regions: number; n_suppressed: number; is_scenario: boolean; observed_years: number[];
  caveat: string; regions: ProjRegion[]; }
export interface WFRegion { region: string; nuts3: string; gdp_per_capita: number;
  is_metro: boolean; fill: number; vac: number; n: number; }
export interface WFResp { year: number; category: string; n_regions: number;
  corr_gdp_fill: number; t_stat: number; p_approx: number; significant_05: boolean;
  strength_el: string; finding: string; caveat: string; regions: WFRegion[]; }
export interface PubDept { name: string; city_display: string | null; base_last: number;
  ebe_threshold: number | null; vacancies: number; reachable: boolean; gap: number | null; }
export interface PrivAlt { institution: string; city: string; tuition_eu: number;
  degree_years: number; total_cost_eur: number; note: string | null; }
export interface PrivPathResp { program: string; public_family: string; moria: number | null;
  year: number; category: string; reaches_any_public: boolean | null;
  public_departments: PubDept[]; private_alternatives: PrivAlt[]; note: string; }
export interface AbandonDept { name: string; city_display: string | null; vacancies: number;
  seats_offered: number; annual_cost_eur: number; }
export interface AbandonResp { year: number; category: string; empty_seats: number;
  total_seats: number; per_student_eur: number; per_student_year: number;
  annual_cost_eur: number; degree_years_example: number; degree_cost_eur: number;
  per_student_source: string; per_student_url: string; caveat: string;
  top_departments: AbandonDept[]; }
export interface IntentProgram { program: string; public_family: string; n_public_depts: number;
  public_mean_vacancy: number; vs_national: number; tuition_eu: number | null; }
export interface IntentResp { year: number; category: string; national_mean_vacancy: number;
  note: string; programs: IntentProgram[]; }
export interface TrendRow { year: number; nuts3: string; region: string; is_metro: boolean;
  avg_vacancy: number; n_dept: number; }
export interface TrendResp { category: string; years: number[]; gap_note: string;
  source_note: string; rows: TrendRow[]; }

export interface NppeItem {
  nppe_id: number; institution: string; parent_uni: string; city: string; program: string;
  degree_years: number; tuition_eu: number | null; tuition_intl: number | null;
  certified: boolean; enrollment: number | null; enrollment_is_official: boolean;
  public_analog_dept: string | null; note: string | null;
}
export interface NppeResp { n: number; items: NppeItem[]; note: string; }

export interface EligibleItem {
  dept_code: string; name: string; institution: string | null; city: string | null;
  base_last: number | null; your_moria: number; margin: number | null;
  ebe_threshold: number | null; your_field_avg: number; ebe_coefficient: number | null;
  vacancies: number | null; fill_rate: number | null; passes_ebe: boolean; likely_admit: boolean;
}
export interface EligibilityResp {
  profile: { field_id: string; field_label: string; moria: number; field_average: number;
    complete: boolean; missing: string[]; year_compared: number; category: string };
  eligible: EligibleItem[]; blocked_by_ebe: EligibleItem[]; n_eligible: number; n_likely: number;
}

// ── endpoints ──────────────────────────────────────────────────────────────
export interface FamilyItem { family: string; n_departments: number; }
export interface CompareDept {
  dept_code: string; name: string; city: string; field: string;
  base_2019: number | null; base_2025: number | null;
  seats: number; admitted: number; vacancies: number; vacancy_rate: number | null;
  ebe_coefficient: number | null;
  forecast_2026: number | null; forecast_2026_lo80: number | null; forecast_2026_hi80: number | null;
}
export interface CompareResp {
  summary: { family: string; n_departments: number; total_seats: number;
    total_vacancies: number; vacancy_rate: number | null; worst: string | null; best: string | null; };
  departments: CompareDept[];
}

export interface WhatIfPrediction {
  point: number; lower_80: number; upper_80: number; lower_95: number; upper_95: number;
}
export interface WhatIfDefaults {
  dept_code: string; category: string; target_year: number; field: string | null;
  prediction: WhatIfPrediction | null;
  coefficient_2026: number | null; coefficient_source: string | null;
  field_ebe_base_latest: number | null; field_ebe_base_year: number | null;
  history: { year: number; base_last: number | null; ebe_threshold: number | null }[];
}
export interface WhatIfResp {
  inputs: { demand_shift_pct: number; ebe_base_shift_pct: number; coefficient: number | null };
  defaults: WhatIfDefaults;
  adjusted_prediction: WhatIfPrediction | null;
  ebe_floor_est: { threshold_20: number; threshold_moria_approx: number;
    coefficient_used: number; field_base_assumed: number; note: string } | null;
  ebe_bound?: boolean;
  disclaimer: string;
}

export interface PlacesOptions {
  cities: { label: string; key: string; n: number }[];
  institutions: { label: string; n: number }[];
}
export interface PlacesFamily {
  family: string;
  a: { dept_code: string; name: string; base_2019: number | null; base_2025: number | null; vacancy_rate_2025: number | null };
  b: { dept_code: string; name: string; base_2019: number | null; base_2025: number | null; vacancy_rate_2025: number | null };
  d_base_2025: number | null;
  pref_wins_a: number | null; pref_wins_b: number | null;
}
export interface PlacesCompareResp {
  summary: {
    kind: string; a: string; b: string; n_shared_families: number;
    mean_d_base_2025: number | null;
    a_higher_base_count: number; b_higher_base_count: number;
    pref_total: { a_wins: number; b_wins: number; a_share: number } | null;
    pref_source: string; note: string;
    triangulation?: { opponent: string; a_share: number; a_n: number; b_share: number; b_n: number }[];
  };
  families: PlacesFamily[];
}

export const api = {
  meta: () => get<Meta>("/meta"),
  compareFamilies: (min_n = 2, category = "ΓΕΛ90") =>
    get<{ n: number; families: FamilyItem[] }>("/compare/families", { min_n, category }),
  compareFamily: (family: string, category = "ΓΕΛ90") =>
    get<CompareResp>(`/compare/${encodeURIComponent(family)}`, { category }),
  departments: (p: Record<string, unknown>) => get<DeptList>("/departments", p),
  department: (code: string, category = "ΓΕΛ90") => get<DeptProfile>(`/departments/${code}`, { category }),
  statsFields: (category = "ΓΕΛ90") => get<FieldStat[]>("/stats/fields", { category }),
  statsVacancies: (category = "ΓΕΛ90") => get<VacancyStats>("/stats/vacancies", { category }),
  statsCities: (category = "ΓΕΛ90") => get<CityStat[]>("/stats/cities", { category }),
  statsRisk: (p: Record<string, unknown> = {}) => get<RiskStats>("/stats/risk", p),
  statsRegions: (category = "ΓΕΛ90") => get<RegionsResp>("/stats/regions", { category }),
  statsRegionsTrend: (category = "ΓΕΛ90") => get<TrendResp>("/stats/regions/trend", { category }),
  statsProjection: (model = "linear", target_year = 2030) =>
    get<ProjResp>("/stats/projection", { model, target_year }),
  statsWealthFill: (category = "ΓΕΛ90") => get<WFResp>("/stats/wealth-fill", { category }),
  nppeIntent: (category = "ΓΕΛ90") => get<IntentResp>("/nppe/intent", { category }),
  abandonmentCost: (category = "ΓΕΛ90") => get<AbandonResp>("/stats/abandonment-cost", { category }),
  privatePath: (program: string, moria?: number) =>
    get<PrivPathResp>("/nppe/private-path", moria != null ? { program, moria } : { program }),
  statsDemand: (year = 2025, category = "ΓΕΛ90") =>
    get<DemandResp>("/stats/demand", { year, category }),
  nppe: () => get<NppeResp>("/nppe"),
  eligibility: (body: unknown) => post<EligibilityResp>("/calc/eligibility", body),
  advisor: (body: unknown) => post<AdvisorResp>("/advisor", body),
  whatifDefaults: (code: string, category = "ΓΕΛ90") =>
    get<WhatIfDefaults>(`/whatif/${code}`, { category }),
  whatifSimulate: (body: unknown) => post<WhatIfResp>("/whatif", body),
  placesOptions: () => get<PlacesOptions>("/places/options"),
  placesCompare: (kind: string, a: string, b: string) =>
    get<PlacesCompareResp>("/places/compare", { kind, a, b }),
};

export interface AdvisorResp {
  answer: string; grounded: boolean; used_llm: boolean; n_facts: number;
  llm_verified?: boolean | null; ungrounded_numbers?: number[];
  citations: { text: string; year: number | null; source: string }[];
  disclaimer: string;
}
