"""FastAPI application entry point."""

import logging
import os
import re
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)

from apps.api.db import ensure_tables
from apps.api.routes import (
    answer,
    domains,
    eval as eval_routes,
    health,
    leakage,
    metrics,
    monitor,
    retrieve,
    scheduler,
)
from apps.api.services.auth import auth_middleware

# CORS: allow explicit trusted origins + Vercel preview domains.
# Env: CORS_ALLOW_ORIGINS="https://dashboard.citarionai.com,https://your-app.vercel.app"
CORS_DEFAULT_ORIGINS = [
    "https://dashboard.citarionai.com",
    "http://localhost:3000",
    "http://localhost:8501",
]
_cors_origins_raw = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
CORS_ORIGINS = (
    [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
    if _cors_origins_raw
    else CORS_DEFAULT_ORIGINS
)
CORS_ORIGIN_REGEX = os.getenv("CORS_ALLOW_ORIGIN_REGEX", r"^https://.*\.vercel\.app$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ensure tables exist on startup (MVP, no migrations)."""
    ensure_tables()
    yield


app = FastAPI(
    title="AI MKT API",
    version="0.1.0",
    lifespan=lifespan,
)

# Keep CORS middleware outermost so preflight is handled before auth checks.
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "authorization",
        "Content-Type",
        "content-type",
        "X-Tenant",
        "x-tenant",
    ],
)
app.middleware("http")(auth_middleware)


@app.options("/{full_path:path}")
async def options_preflight(_full_path: str) -> Response:
    return Response(status_code=200)


def _cors_headers_for_request(origin: str | None) -> dict[str, str]:
    """Return CORS headers if origin is allowed (so error responses still satisfy CORS)."""
    if origin and (
        origin in CORS_ORIGINS or (CORS_ORIGIN_REGEX and re.match(CORS_ORIGIN_REGEX, origin))
    ):
        return {"Access-Control-Allow-Origin": origin}
    return {}


@app.exception_handler(Exception)
async def add_cors_to_errors(request: Request, exc: Exception):
    """Ensure 500 and other error responses include CORS so the browser does not show a CORS block."""
    origin = request.headers.get("origin")
    headers = _cors_headers_for_request(origin)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
        headers=headers,
    )


app.include_router(health.router, tags=["health"])
app.include_router(retrieve.router, prefix="/retrieve", tags=["retrieve"])
app.include_router(answer.router, tags=["answer"])
app.include_router(domains.router, tags=["domains"])
app.include_router(eval_routes.router, prefix="/eval", tags=["eval"])
app.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
app.include_router(monitor.router, prefix="/monitor", tags=["monitor"])
app.include_router(leakage.router, tags=["leakage"])
app.include_router(scheduler.router, prefix="/scheduler", tags=["scheduler"])

if (os.getenv("ENV") or os.getenv("ENVIRONMENT") or "").lower() == "test":
    from apps.api.routes import debug

    app.include_router(debug.router, prefix="/debug", tags=["debug"])
    app.include_router(debug.index_stats_router, prefix="/tenants", tags=["debug"])
