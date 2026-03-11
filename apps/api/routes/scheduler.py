"""Scheduler status endpoint. Read-only; no auth required (same as health)."""

import logging
import os

from fastapi import APIRouter

from apps.api.services.repo import get_scheduler_last_tick

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/status")
async def scheduler_status() -> dict:
    """
    Return auto-eval scheduler status: enabled, interval_minutes, last_tick_at.
    Used by dashboard for optional "auto evaluation enabled" / "last auto evaluation" UI.
    """
    enabled = (os.getenv("AUTO_EVAL_ENABLED") or "").strip().lower() in ("1", "true", "yes")
    interval_minutes = 5
    raw_interval = (os.getenv("AUTO_EVAL_INTERVAL_MINUTES") or "").strip()
    try:
        if raw_interval:
            interval_minutes = max(1, int(raw_interval))
    except ValueError:
        logger.warning(
            "scheduler_status_invalid_interval key=AUTO_EVAL_INTERVAL_MINUTES value=%s fallback=%s",
            raw_interval,
            interval_minutes,
        )
    last_tick_at = None
    try:
        dt = get_scheduler_last_tick()
        if dt is not None and hasattr(dt, "isoformat"):
            last_tick_at = dt.isoformat()
    except Exception:
        pass
    return {
        "enabled": enabled,
        "interval_minutes": interval_minutes,
        "last_tick_at": last_tick_at,
    }
