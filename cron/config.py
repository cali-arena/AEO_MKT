"""Cron config from environment."""

import os


def _int(val: str | None, default: int) -> int:
    if val is None or val.strip() == "":
        return default
    try:
        return int(val.strip())
    except ValueError:
        return default


def _float(val: str | None, default: float) -> float:
    if val is None or val.strip() == "":
        return default
    try:
        return float(val.strip())
    except ValueError:
        return default


def _list(val: str | None) -> list[str]:
    if val is None or val.strip() == "":
        return []
    return [s.strip() for s in val.split(",") if s.strip()]


class Config:
    """Cron configuration from env vars."""

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ai_mkt")
    API_BASE: str = os.getenv("API_BASE", "http://localhost:8000")
    TENANTS: list[str] = _list(os.getenv("TENANTS"))
    LOOKBACK_RUNS: int = _int(os.getenv("LOOKBACK_RUNS"), 10)
    REFUSAL_SPIKE_ABS: float = _float(os.getenv("REFUSAL_SPIKE_ABS"), 0.05)
    CITATION_DROP_ABS: float = _float(os.getenv("CITATION_DROP_ABS"), 0.1)
    EVENT_COOLDOWN_HOURS: int = _int(os.getenv("EVENT_COOLDOWN_HOURS"), 24)


config = Config()
