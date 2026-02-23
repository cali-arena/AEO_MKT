"""Health check endpoint. No auth required."""

import os
from datetime import datetime, timezone

from fastapi import APIRouter

from apps.api.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check. Returns ok, version (GIT_SHA or dev), and current time (ISO)."""
    version = os.getenv("GIT_SHA", "dev").strip() or "dev"
    return HealthResponse(
        ok=True,
        version=version,
        time=datetime.now(timezone.utc).isoformat(),
    )
