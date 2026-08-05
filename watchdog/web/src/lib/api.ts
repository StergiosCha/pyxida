const BASE = (import.meta as any).env?.VITE_API ?? "http://127.0.0.1:8010";
export type SeriesPt = { year:number; value:number|null; lower_bound:number|null; upper_bound:number|null; rank:number|null; total_ranked:number|null; unit:string; direction:string; source_url:string; note:string|null; is_verified:boolean };
export type Source = { source_id:string; name:string; url:string; methodology:string; methodology_url:string; coverage:string };
export type SeriesResp = { indicator:string; source:Source; series:SeriesPt[] };
export type Indicator = { indicator:string; source_id:string; source_name:string; unit:string; direction:string; latest_year:number; latest_value:number|null };
export type Alert = { date:string; type:string; title_el:string; description:string; severity:string; source_url:string; is_verified:boolean };
export type Media = { outlet:string; outlet_type:string; owner:string; owner_interests:string; is_official:boolean; source_url:string; note:string|null };
export type Police = { date:string; category:string; title_en:string; description:string; victim_or_scope:string; body_or_court:string; outcome:string; source_url:string; methodology_url:string|null; note:string|null };
export type GovPoint = { year:number; value:number|null; lo:number|null; hi:number|null };
export type GovInd = { indicator:string; source_url:string; points:GovPoint[] };
export type GovResp = { unit:string; indicators:GovInd[] };
export type DossierRow = { section:string; date:string|null; title:string; detail:string|null;
  actor:string|null; role:string|null; status:string; response:string|null;
  source_body:string|null; source_url:string; amount_eur:string|null };
export type DossierSection = { section:string; rows:DossierRow[] };
export type DossierResp = { n:number; status_counts:Record<string,number>; sections:DossierSection[] };
export type AssessResp = { used_llm:boolean; grounded:boolean; backend:string;
  section:string|null; n_facts:number; assessment:string; note?:string };
export type EntitySummary = { id:string; name:string; role:string; n:number;
  status_counts:Record<string,number> };
export type EntityDetail = { id:string; name:string; role:string; n:number;
  status_counts:Record<string,number>; rows:DossierRow[] };
export type EuRow = { label:string; year:number; greece:number; eu_rank:number;
  eu_total:number; eu_median:number; eu_best:number; eu_worst:number; source_url:string };
export type EuResp = { available:boolean; note?:string; rows:EuRow[] };
export type FlowNode = { id:string; label:string; kind:string; interests?:string; source_url?:string };
export type FlowLink = { source:string; target:string };
export type FlowResp = { total_eur:number|null; total_label:string; total_source:string;
  note:string; nodes:FlowNode[]; links:FlowLink[] };
export type CompPoint = { year:number; value:number; z:number };
export type CompComponent = { label:string; indicator:string; direction:string;
  source_url:string; points:CompPoint[] };
export type CompResp = { is_derived:boolean; reference_year:number; note:string;
  components:CompComponent[]; composite:{year:number; z:number; n:number}[] };
export type BARow = { indicator:string; before_year:number; before:number;
  after_year:number; after:number; delta:number; direction:string;
  improved:boolean|null; source_url:string };
export type BAResp = { split_year:number; n:number; rows:BARow[] };
export type ImpCase = { case:string; year:number|null; date:string|null; outcome_text:string; outcome:string;
  years_elapsed:number|null; source_url:string; kind:string };
export type ImpResp = { n:number; counts:Record<string,number>; cases:ImpCase[] };
export type NetNode = { id:string; label:string; kind:string; role?:string; n?:number;
  status?:string; source_url?:string };
export type NetResp = { n_nodes:number; n_links:number; note:string;
  nodes:NetNode[]; links:FlowLink[] };
async function j<T>(p:string):Promise<T>{ const r=await fetch(BASE+p); if(!r.ok) throw new Error(p+" "+r.status); return r.json(); }
export const api = {
  meta: ()=>j<any>("/meta"),
  indicators: ()=>j<Indicator[]>("/indicators"),
  series: (i:string)=>j<SeriesResp>("/indicators/"+encodeURIComponent(i)+"/series"),
  governance: ()=>j<GovResp>("/governance"),
  dossier: ()=>j<DossierResp>("/dossier"),
  assessment: (body:{section?:string|null; entity?:string|null})=>fetch(BASE+"/assessment",{method:"POST",
    headers:{"Content-Type":"application/json"},body:JSON.stringify(body)})
    .then(r=>{if(!r.ok)throw new Error("assessment "+r.status);return r.json() as Promise<AssessResp>;}),
  euComparison: ()=>j<EuResp>("/eu-comparison"),
  stateAdFlow: ()=>j<FlowResp>("/state-ad-flow"),
  compositeIndex: ()=>j<CompResp>("/composite-index"),
  beforeAfter: ()=>j<BAResp>("/before-after"),
  impunity: ()=>j<ImpResp>("/impunity"),
  network: ()=>j<NetResp>("/network"),
  entities: ()=>j<{entities:EntitySummary[]}>("/entities"),
  entity: (id:string)=>j<EntityDetail>("/entities/"+encodeURIComponent(id)),
  alerts: ()=>j<Alert[]>("/alerts"),
  media: ()=>j<Media[]>("/media"),
  police: ()=>j<Police[]>("/police"),
  exportUrl: (table:string, format:"csv"|"json"="csv")=>`${BASE}/export/${table}?format=${format}`,
};
