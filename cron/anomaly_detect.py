#!/usr/bin/env python3
"""Anomaly detection: compare latest eval run vs baseline, insert monitor_event on threshold breach.

- Look back LOOKBACK_RUNS (default 10).
- Baseline = average of runs 2..N (exclude latest).
- Compare latest vs baseline:
  - refusal_spike if refusal_rate >= baseline + REFUSAL_SPIKE_ABS
  - citation_drop if citation_rate <= baseline - CITATION_DROP_ABS
  - cache_hit_drop: skip cleanly if cache stats not available.

Event spam control: do not insert if same event_type within EVENT_COOLDOWN_HOURS.
"""

import sys
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))

from cron.config import config
from cron.logging import get_logger

logger = get_logger("anomaly_detect")


def _run_tenant(tenant_id: str) -> int:
    """Process one tenant. Returns count of events inserted."""
    from apps.api.services.repo import (
        aggregate_kpis_for_run,
        create_monitor_event,
        list_eval_runs,
        list_monitor_events,
    )

    lookback = config.LOOKBACK_RUNS
    if lookback < 2:
        return 0

    runs = list_eval_runs(tenant_id, limit=lookback, offset=0)
    if len(runs) < 2:
        logger.debug("tenant=%s runs=%s, need >=2", tenant_id, len(runs))
        return 0

    latest = runs[0]
    baseline_runs = runs[1:lookback]

    kpis_per_run: dict[UUID, dict[str, Any]] = {}
    for r in baseline_runs:
        kpis = aggregate_kpis_for_run(tenant_id, r.id)
        kpis_per_run[r.id] = kpis

    latest_kpis = aggregate_kpis_for_run(tenant_id, latest.id)
    latest_refusal = latest_kpis.get("refusal_rate", 0.0) or 0.0
    latest_citation = latest_kpis.get("citation_rate", 0.0) or 0.0

    baseline_refusal = sum(k.get("refusal_rate", 0) or 0 for k in kpis_per_run.values()) / len(kpis_per_run)
    baseline_citation = sum(k.get("citation_rate", 0) or 0 for k in kpis_per_run.values()) / len(kpis_per_run)

    inserted = 0
    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.EVENT_COOLDOWN_HOURS)

    def _recent_event(event_type: str) -> bool:
        events = list_monitor_events(
            tenant_id,
            event_type=event_type,
            limit=1,
            offset=0,
        )
        if not events:
            return False
        created = events[0].created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return created >= cutoff

    refusal_threshold = baseline_refusal + config.REFUSAL_SPIKE_ABS
    if latest_refusal >= refusal_threshold:
        if not _recent_event("refusal_spike"):
            delta = latest_refusal - baseline_refusal
            extreme = delta >= 2 * config.REFUSAL_SPIKE_ABS
            create_monitor_event(
                tenant_id=tenant_id,
                event_type="refusal_spike",
                severity="high" if extreme else "medium",
                details_json={
                    "tenant_id": tenant_id,
                    "latest_run_id": str(latest.id),
                    "baseline_value": round(baseline_refusal, 4),
                    "latest_value": round(latest_refusal, 4),
                    "delta": round(delta, 4),
                    "threshold": round(refusal_threshold, 4),
                    "refusal_spike_abs": config.REFUSAL_SPIKE_ABS,
                },
            )
            inserted += 1
            logger.info("tenant=%s refusal_spike latest=%.2f baseline=%.2f", tenant_id, latest_refusal, baseline_refusal)

    citation_threshold = baseline_citation - config.CITATION_DROP_ABS
    if latest_citation <= citation_threshold:
        if not _recent_event("citation_drop"):
            delta = baseline_citation - latest_citation
            extreme = delta >= 2 * config.CITATION_DROP_ABS
            create_monitor_event(
                tenant_id=tenant_id,
                event_type="citation_drop",
                severity="high" if extreme else "medium",
                details_json={
                    "tenant_id": tenant_id,
                    "latest_run_id": str(latest.id),
                    "baseline_value": round(baseline_citation, 4),
                    "latest_value": round(latest_citation, 4),
                    "delta": round(delta, 4),
                    "threshold": round(citation_threshold, 4),
                    "citation_drop_abs": config.CITATION_DROP_ABS,
                },
            )
            inserted += 1
            logger.info("tenant=%s citation_drop latest=%.2f baseline=%.2f", tenant_id, latest_citation, baseline_citation)

    # cache_hit_drop: skip cleanly - no cache stats in eval_result
    # (cache stats would require separate source; skip when not available)

    return inserted


def main() -> int:
    tenants = config.TENANTS
    if not tenants:
        logger.warning("TENANTS env empty, nothing to run")
        return 0

    logger.info("anomaly_detect start tenants=%s", tenants)
    total = 0
    for tenant_id in tenants:
        try:
            n = _run_tenant(tenant_id)
            total += n
        except Exception as e:
            logger.exception("tenant=%s error: %s", tenant_id, e)
            return 1

    logger.info("anomaly_detect done inserted=%s", total)
    return 0


if __name__ == "__main__":
    sys.exit(main())
