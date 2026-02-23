/**
 * TypeScript types matching FastAPI responses (snake_case).
 */

export interface HealthResponse {
  ok: boolean;
  version: string;
  time: string;
}

export interface MetricsKPIs {
  mention_rate: number;
  citation_rate: number;
  attribution_accuracy: number;
  hallucinations: number;
  composite_index: number;
}

export interface MetricsLatestResponse {
  tenant_id: string;
  run_id: string;
  created_at: string;
  crawl_policy_version: string;
  ac_version_hash: string;
  ec_version_hash: string;
  kpis: MetricsKPIs;
}

export interface MetricsTrendPoint {
  ts: string;
  mention_rate: number;
  citation_rate: number;
  attribution_accuracy: number;
  hallucinations: number;
  composite_index: number;
  run_id: string | null;
}

export interface MetricsTrendsResponse {
  tenant_id: string;
  points: MetricsTrendPoint[];
}

export interface EvalRunListItem {
  run_id: string;
  created_at: string;
  crawl_policy_version: string;
  ac_version_hash: string;
  ec_version_hash: string;
  kpis_summary: MetricsKPIs;
}

export interface EvalRunsResponse {
  tenant_id: string;
  runs: EvalRunListItem[];
}

export interface EvalResultRow {
  query_id: string;
  domain: string;
  query_text: string;
  refused: boolean;
  refusal_reason: string | null;
  mention_ok: boolean;
  citation_ok: boolean;
  attribution_ok: boolean;
  hallucination_flag: boolean;
  evidence_count: number;
  avg_confidence: number;
  top_cited_urls: Record<string, unknown> | unknown[] | null;
  answer_preview: string | null;
}

export interface EvalRunResultsResponse {
  tenant_id: string;
  run_id: string;
  results: EvalResultRow[];
}

export interface EvalMetricsRates {
  mention_rate: number;
  citation_rate: number;
  attribution_rate: number;
  hallucination_rate: number;
}

export interface EvalMetricsLatestOut {
  run_id: string;
  overall: EvalMetricsRates;
  per_domain: Record<string, EvalMetricsRates>;
}

export interface LeakageLatestResponse {
  tenant_id: string;
  ok: boolean;
  last_checked_at: string;
  details_json: Record<string, unknown> | unknown[] | null;
}
