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

export type UiStatus = "UNINDEXED" | "INDEXING" | "EVALUATING" | "DONE" | "FAILED";
export type ResolvedDomainStatus = "PENDING" | "EVALUATING" | "DONE" | "FAILED";

export interface DomainListItem {
  domain: string;
  status: "pending" | "running" | "done" | "failed";
  latest_rates: EvalMetricsRates | null;
  total_results?: number;
  refused_count?: number;
  ok_count?: number;
  last_run_id: string | null;
  last_run_created_at: string | null;
  failure_reason: string | null;
  /** Index state: PENDING | RUNNING | DONE | FAILED | UNINDEXED */
  index_status?: string | null;
  last_indexed_at?: string | null;
  last_error?: string | null;
  /** API: index_error (same as last_error when present) */
  index_error?: string | null;
  /** Latest eval job status: PENDING | RUNNING | DONE | FAILED | NONE */
  eval_status?: string | null;
  /** RUNNING when this domain is current_domain of a running orchestrate job */
  orchestration_status?: string | null;
  /** Single source of truth for badge: UNINDEXED | INDEXING | EVALUATING | DONE | FAILED */
  ui_status?: UiStatus | null;
  /** Optional fields for UI status resolver (when API aggregation is job-based) */
  eval_result_count?: number;
  last_result_at?: string | null;
  running_count?: number;
  failed_count?: number;
  done_count?: number;
}

export interface DomainsListResponse {
  tenant_id: string;
  run_id: string | null;
  domains: DomainListItem[];
}

export interface DomainsCreateResponse {
  status: string;
  created: string[];
  existing: string[];
}

export interface DesiredHashesRow {
  domain: string;
  ac_version_hash: string;
  ec_version_hash: string;
  crawl_policy_version: string;
}

export interface DomainsEvaluateResponse {
  status: string;
  message: string;
  job_id: string;
  status_url: string;
  run_id: string | null;
  started_domains: string[];
  index_status?: "pending" | "up_to_date" | "running";
  index_job_id?: string | null;
  eval_job_id?: string | null;
  orchestration_job_id?: string | null;
  desired_hashes?: DesiredHashesRow[];
}

export interface DomainJobStatusResponse {
  job_id: string;
  tenant_id: string;
  status: "pending" | "running" | "done" | "failed";
  total: number;
  completed: number;
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface LeakageLatestResponse {
  tenant_id: string;
  ok: boolean;
  last_checked_at: string;
  details_json: Record<string, unknown> | unknown[] | null;
}

export interface CrawlerEvalResult {
  domain: string;
  score: number;
  max_score: number;
  grade: string;
  weaknesses: string[];
  opportunities: string[];
  summary: string;
}

// ---------------------------------------------------------------------------
// Citarion Crawler types (source: /crawler/* endpoints)
// ---------------------------------------------------------------------------

export interface RoamSyncRun {
  id: number;
  source: string;
  worker: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  processed: number;
  skipped: number;
  failed: number;
  checkpoint: string | null;
  error: string | null;
}

export interface RoamStatus {
  configured: boolean;
  base_url: string | null;
  workspace_id: string | null;
  webhook_secret_set: boolean;
  poll_interval_seconds?: number;
  last_run: RoamSyncRun | null;
}

export interface SourceMessage {
  id: string | number;
  source_system: string;
  source_id: string;
  workspace_id: string;
  chat_id: string | null;
  received_at: string;
  processed: number;
  payload_keys?: string[];
}

export interface SourceMessagesResponse {
  source: string;
  count: number;
  messages: SourceMessage[];
}

export interface BolUpload {
  id: string;
  filename: string;
  mime_type: string | null;
  file_size: number;
  status: string;
  created_at: string;
  extracted_chars: number;
}

export interface BolUploadsResponse {
  count: number;
  uploads: BolUpload[];
}

export interface ParsedJob {
  id: number;
  source_type: string;
  source_ref: string;
  shipment_reference: string | null;
  carrier_name: string | null;
  pickup_date: string | null;
  delivery_date: string | null;
  origin: string | null;
  destination: string | null;
  confidence_score: number;
  parsing_status: string;
  parsed_at: string;
}

export interface JobsResponse {
  count: number;
  jobs: ParsedJob[];
}

export interface Shipment {
  id: number;
  shipment_reference: string;
  carrier_name: string | null;
  pickup_date: string | null;
  delivery_date: string | null;
  origin: string | null;
  destination: string | null;
  job_id: number;
  created_at: string;
}

export interface ShipmentsResponse {
  count: number;
  shipments: Shipment[];
}

export interface BolUploadResult {
  upload_id: string;
  filename: string;
  status: string;
  file_size: number;
  message: string;
}

export interface RoamSyncResult {
  started_at: string;
  finished_at: string | null;
  chats_seen: number;
  chats_synced: string[];
  pages_fetched: number;
  processed: number;
  skipped: number;
  failed: number;
  errors: string[];
}
