import type { DomainListItem, ResolvedDomainStatus } from "@/lib/types";

/**
 * Resolve display status from API row. Prefer result-based signals so domains with
 * eval results show DONE even when job-level aggregation still says EVALUATING.
 */
export function resolveDomainStatus(row: DomainListItem): ResolvedDomainStatus {
  const hasResults =
    (row.total_results ?? 0) > 0 ||
    (row.eval_result_count ?? 0) > 0 ||
    !!row.last_run_created_at ||
    !!row.last_result_at;
  if (hasResults) return "DONE";
  if (!!row.last_error || !!row.failure_reason || (row.failed_count ?? 0) > 0) return "FAILED";
  if (
    row.status === "running" ||
    row.ui_status === "EVALUATING" ||
    row.ui_status === "INDEXING" ||
    (row.running_count ?? 0) > 0
  ) {
    return "EVALUATING";
  }
  return "PENDING";
}

export function resolvedStatusBadgeClass(status: ResolvedDomainStatus): string {
  if (status === "DONE") return "bg-emerald-100 text-emerald-800";
  if (status === "FAILED") return "bg-rose-100 text-rose-800";
  if (status === "EVALUATING") return "bg-blue-100 text-blue-800";
  return "bg-gray-100 text-gray-700";
}

