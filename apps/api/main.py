"""FastAPI application entry point."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

logging.basicConfig(level=logging.INFO)
from fastapi.middleware.cors import CORSMiddleware

from apps.api.db import ensure_tables
from apps.api.routes import answer, eval as eval_routes, health, leakage, metrics, monitor, retrieve
from apps.api.services.auth import auth_middleware

# CORS: allow only specified origins (no wildcard).
# Env: CORS_ALLOW_ORIGINS="https://your-vercel-app.vercel.app,http://localhost:3000" (comma-separated).
# If not set, default to localhost only for local dev.
CORS_DEFAULT_ORIGINS = ["http://localhost:3000", "http://localhost:8501"]
_cors_origins_raw = os.getenv("CORS_ALLOW_ORIGINS", "").strip()
CORS_ORIGINS = (
    [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
    if _cors_origins_raw
    else CORS_DEFAULT_ORIGINS
)


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

app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])
app.middleware("http")(auth_middleware)

app.include_router(health.router, tags=["health"])
app.include_router(retrieve.router, prefix="/retrieve", tags=["retrieve"])
app.include_router(answer.router, tags=["answer"])
app.include_router(eval_routes.router, prefix="/eval", tags=["eval"])
app.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
app.include_router(monitor.router, prefix="/monitor", tags=["monitor"])
app.include_router(leakage.router, tags=["leakage"])

if (os.getenv("ENV") or os.getenv("ENVIRONMENT") or "").lower() == "test":
    from apps.api.routes import debug

    app.include_router(debug.router, prefix="/debug", tags=["debug"])
