"""Single domain status derivation for API + UI. No domain shows DONE unless both indexed and eval completed."""

from __future__ import annotations

from typing import Any, Literal

from apps.api.services.domain_jobs import get_latest_domain_job_statuses
from apps.api.services.domain_orchestrate_jobs import get_running_orchestrate_current_domain
from apps.api.services.repo import get_domain_index_states_for_tenant, list_eval_domains
from apps.api.services.tenant_guard import require_tenant_id

DerivedStatus = Literal["UNINDEXED", "INDEXING", "FAILED", "DONE", "EVALUATING"]
IndexStatus = Literal["PENDING", "RUNNING", "DONE", "FAILED", "UNINDEXED"]
EvalStatus = Literal["PENDING", "RUNNING", "DONE", "FAILED", "NONE"]


def derive_domain_status(
    index_state: dict[str, Any] | None,
    eval_job_status: str | None,
    *,
    orchestrate_current_domain: str | None = None,
    domain: str | None = None,
) -> DerivedStatus:
    """
    Derive a single domain status from index state and latest eval job. Used by both API and UI.

    Rules:
    - UNINDEXED = no state OR state.status is null/empty
    - INDEXING = state.status in (PENDING, RUNNING)
    - FAILED = state.status == FAILED OR latest eval job FAILED
    - EVALUATING = state.status == DONE AND (eval job RUNNING/PENDING OR domain is current_domain of running orchestrate)
    - DONE = state.status == DONE AND latest eval job DONE (both indexed and eval completed)
    """
    state_status = None
    if index_state and index_state.get("status"):
        state_status = str(index_state["status"]).strip().upper()
    eval_status = (eval_job_status or "").strip().upper() if eval_job_status else None

    # UNINDEXED: no state or status empty
    if not index_state or not state_status:
        return "UNINDEXED"

    # INDEXING: index in progress
    if state_status in ("PENDING", "RUNNING"):
        return "INDEXING"

    # FAILED: index failed or eval failed
    if state_status == "FAILED":
        return "FAILED"
    if eval_status == "FAILED":
        return "FAILED"

    # EVALUATING only when backend has a PENDING/RUNNING domain_eval_job for this domain (eval_status from that job)
    if state_status == "DONE":
        if eval_status in ("RUNNING", "PENDING"):
            return "EVALUATING"
        if eval_status == "DONE":
            return "DONE"
        # Indexed but no eval job or eval result: do not show Running (no EVALUATING without real job)
        return "INDEXING"

    return "UNINDEXED"


def get_domains_with_status(tenant_id: str) -> list[dict[str, Any]]:
    """
    Load domains with joined domain_index_state and latest eval job status; derive ui_status per domain.
    Returns list of dicts per domain: domain, index_status, last_indexed_at, index_error, eval_status,
    orchestration_status (optional), ui_status. Use this so UI cannot show DONE when index is missing/stale.
    """
    tenant_id = require_tenant_id(tenant_id)
    monitored = list_eval_domains(tenant_id)
    index_states = get_domain_index_states_for_tenant(tenant_id)
    eval_statuses = get_latest_domain_job_statuses(tenant_id)
    orchestrate_current = get_running_orchestrate_current_domain(tenant_id)
    domains_set = set(monitored) | set(index_states) | set(eval_statuses)
    out: list[dict[str, Any]] = []
    for domain in sorted(domains_set):
        state = index_states.get(domain)
        index_status: IndexStatus = "UNINDEXED"
        last_indexed_at = None
        index_error = None
        if state:
            raw = (state.get("status") or "").strip().upper()
            if raw in ("PENDING", "RUNNING", "DONE", "FAILED"):
                index_status = raw  # type: ignore[assignment]
            last_indexed_at = state.get("last_indexed_at")
            index_error = state.get("last_error")
        eval_status_raw = eval_statuses.get(domain)
        eval_status: EvalStatus = "NONE"
        if eval_status_raw:
            raw = (eval_status_raw or "").strip().upper()
            if raw in ("PENDING", "RUNNING", "DONE", "FAILED"):
                eval_status = raw  # type: ignore[assignment]
        orchestration_status: str | None = "RUNNING" if (orchestrate_current and orchestrate_current == domain) else None
        index_state_for_derive = (
            {"status": state.get("status")} if state else None
        )
        ui_status = derive_domain_status(
            index_state_for_derive,
            eval_status_raw,
            orchestrate_current_domain=orchestrate_current,
            domain=domain,
        )
        out.append({
            "domain": domain,
            "index_status": index_status,
            "last_indexed_at": last_indexed_at,
            "index_error": index_error,
            "eval_status": eval_status,
            "orchestration_status": orchestration_status,
            "ui_status": ui_status,
        })
    return out
