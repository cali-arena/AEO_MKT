"""Shared test DB bootstrap (guard + schema creation). Used by root conftest for all test paths."""

import logging
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

_ROOT = Path(__file__).resolve().parent.parent

_LOG = logging.getLogger(__name__)

# Mixing guard: track which schema path ran in this session
_alembic_invoked = False
_ensure_tables_invoked = False

TEST_SCHEMA_STRATEGY_DEFAULT = "alembic"


def get_test_schema_strategy() -> str:
    """Return TEST_SCHEMA_STRATEGY: 'alembic' (default) or 'ensure_tables'."""
    v = (os.environ.get("TEST_SCHEMA_STRATEGY") or TEST_SCHEMA_STRATEGY_DEFAULT).strip().lower()
    if v not in ("alembic", "ensure_tables"):
        raise RuntimeError(
            f"TEST_SCHEMA_STRATEGY must be 'alembic' or 'ensure_tables'. Got: {v!r}. "
            "Fix: export TEST_SCHEMA_STRATEGY=alembic  # or ensure_tables"
        )
    return v


def assert_not_mixed_schema_setup(strategy: str) -> None:
    """Raise RuntimeError if both Alembic and ensure_tables paths have run in this session."""
    if _alembic_invoked and _ensure_tables_invoked:
        raise RuntimeError(
            "Mixed schema setup: both Alembic and ensure_tables/create_all ran. "
            "Set TEST_SCHEMA_STRATEGY=alembic (default) or TEST_SCHEMA_STRATEGY=ensure_tables "
            "and ensure only one path runs. Fix: export TEST_SCHEMA_STRATEGY=alembic"
        )
    if strategy == "alembic" and _ensure_tables_invoked:
        raise RuntimeError(
            "Cannot run Alembic: ensure_tables path already ran. "
            "Use TEST_SCHEMA_STRATEGY=alembic from the start. Fix: export TEST_SCHEMA_STRATEGY=alembic"
        )
    if strategy == "ensure_tables" and _alembic_invoked:
        raise RuntimeError(
            "Cannot run ensure_tables: Alembic path already ran. "
            "Use TEST_SCHEMA_STRATEGY=ensure_tables from the start. Fix: export TEST_SCHEMA_STRATEGY=ensure_tables"
        )


def parse_db_name(url: str) -> str:
    """Extract database name from postgres URL (path without leading slash)."""
    p = urlparse(url)
    path = (p.path or "").strip("/")
    return path.split("/")[0] if path else ""


def parse_db_user(url: str) -> str:
    """Extract database user from postgres URL. Returns 'postgres' if unparseable."""
    try:
        p = urlparse(url)
        u = (p.username or "postgres").strip()
        if u and all(c.isalnum() or c == "_" for c in u):
            return u
        return "postgres"
    except Exception:
        return "postgres"


def _assert_schema_reset_safe(url: str) -> None:
    """Raise RuntimeError if schema reset is not allowed (safety check).
    Allowed when: db name contains '_test' OR ALLOW_TEST_DB_RESET=true."""
    if os.environ.get("ALLOW_TEST_DB_RESET", "").lower() in ("1", "true", "yes"):
        return
    db_name = parse_db_name(url)
    if "_test" in db_name:
        return
    raise RuntimeError(
        f"Schema reset blocked: DATABASE_TEST_URL db name must contain '_test' "
        f"or set ALLOW_TEST_DB_RESET=true. Got db: {db_name!r}"
    )


def build_test_url(url: str) -> str:
    """Derive test DB URL by appending '_test' to db name. Idempotent if already ends with _test."""
    p = urlparse(url)
    db_name = parse_db_name(url)
    if db_name.endswith("_test"):
        return url
    test_db = f"{db_name}_test" if db_name else "ai_mkt_test"
    return urlunparse((p.scheme, p.netloc, f"/{test_db}", "", "", ""))


def postgres_reachable(url: str, timeout: int = 2) -> bool:
    """Return True if Postgres at url is reachable. Uses short timeout to avoid flaky CI."""
    if not url or not url.strip().lower().startswith("postgresql"):
        return False
    eng = None
    try:
        from sqlalchemy import create_engine

        eng = create_engine(url, connect_args={"connect_timeout": timeout})
        with eng.connect():
            return True
    except Exception:
        return False
    finally:
        if eng is not None:
            try:
                eng.dispose()
            except Exception:
                pass


def _is_local_postgres(url: str) -> bool:
    """Return True if URL points to local Postgres (localhost/127.0.0.1)."""
    p = urlparse(url)
    host = (p.hostname or "").lower()
    return host in ("localhost", "127.0.0.1", "")


def create_database_if_missing(url: str) -> None:
    """Create the database if it does not exist. Local Postgres only (no network)."""
    if not _is_local_postgres(url):
        _LOG.warning("Skipping create_database_if_missing: %s is not local", urlparse(url).hostname)
        return
    db_name = parse_db_name(url)
    if not db_name or not all(c.isalnum() or c == "_" for c in db_name):
        return
    p = urlparse(url)
    admin_url = urlunparse((p.scheme, p.netloc, "/postgres", "", "", ""))
    from sqlalchemy import create_engine, text

    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            r = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": db_name})
            if r.scalar() is None:
                conn.execute(text(f'CREATE DATABASE "{db_name}"'))
                _LOG.info("Created test database: %s", db_name)
    finally:
        engine.dispose()


def drop_all_tables(url: str) -> None:
    """Drop all tables in public schema. Local Postgres only (no network)."""
    if not _is_local_postgres(url):
        _LOG.warning("Skipping drop_all_tables: %s is not local", urlparse(url).hostname)
        return
    from sqlalchemy import create_engine, text

    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            r = conn.execute(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename NOT LIKE 'pg_%'"
                )
            )
            tables = [row[0] for row in r]
            if tables:
                conn.execute(text("DROP SCHEMA public CASCADE"))
                conn.execute(text("CREATE SCHEMA public"))
                conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
                _LOG.info("Dropped %d tables in public schema", len(tables))
    finally:
        engine.dispose()


def _alembic_config_with_url(db_url: str):
    """Build Alembic config with sqlalchemy.url set to db_url."""
    from alembic.config import Config

    alembic_ini = _ROOT / "alembic.ini"
    if not alembic_ini.exists():
        raise FileNotFoundError(f"alembic.ini not found at {alembic_ini}")
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _mark_alembic_invoked() -> None:
    global _alembic_invoked
    _alembic_invoked = True


def _mark_ensure_tables_invoked() -> None:
    global _ensure_tables_invoked
    _ensure_tables_invoked = True


def run_alembic_upgrade_head(db_url: str) -> None:
    """Run alembic upgrade head with the given db_url. Forces sqlalchemy.url dynamically."""
    assert_not_mixed_schema_setup("alembic")
    from alembic import command

    cfg = _alembic_config_with_url(db_url)
    prev = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    try:
        command.upgrade(cfg, "head")
        _mark_alembic_invoked()
        _LOG.info("Ran alembic upgrade head")
    finally:
        if prev is not None:
            os.environ["DATABASE_URL"] = prev
        else:
            os.environ.pop("DATABASE_URL", None)


def run_alembic_upgrade(db_url: str) -> None:
    """Run alembic upgrade head. Idempotent. Forces sqlalchemy.url dynamically."""
    run_alembic_upgrade_head(db_url)


def _run_alembic_downgrade_base(db_url: str) -> None:
    """Run alembic downgrade base. No-op safe (schema already dropped)."""
    assert_not_mixed_schema_setup("alembic")
    from alembic import command

    cfg = _alembic_config_with_url(db_url)
    try:
        command.downgrade(cfg, "base")
        _mark_alembic_invoked()
        _LOG.info("Ran alembic downgrade base")
    except Exception as e:
        _LOG.debug("alembic downgrade base skipped (expected if schema empty): %s", e)


def _recreate_schema_migration(db_url: str) -> bool:
    """Recreate schema via Alembic. Returns True on success. Never calls ensure_tables."""
    assert_not_mixed_schema_setup("alembic")
    from alembic import command

    cfg = _alembic_config_with_url(db_url)
    prev = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    try:
        _run_alembic_downgrade_base(db_url)
        command.upgrade(cfg, "head")
        _mark_alembic_invoked()
        _LOG.info("Schema recreated via alembic upgrade head")
        return True
    except Exception as e:
        _LOG.warning("Alembic schema recreation failed: %s", e)
        return False
    finally:
        if prev is not None:
            os.environ["DATABASE_URL"] = prev
        else:
            os.environ.pop("DATABASE_URL", None)


def _recreate_schema_ensure_tables(db_url: str) -> None:
    """Schema via ensure_tables() only. Never calls Alembic. DB must be empty (Step 2)."""
    assert_not_mixed_schema_setup("ensure_tables")
    from sqlalchemy import create_engine, text

    from apps.api.db import ensure_tables

    os.environ["DATABASE_URL"] = db_url
    os.environ["TEST_SCHEMA_STRATEGY"] = "ensure_tables"
    eng = create_engine(db_url, pool_pre_ping=True)
    try:
        if db_url.strip().lower().startswith("postgresql"):
            with eng.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        ensure_tables(bind=eng)
    finally:
        eng.dispose()
    # Clear global engine pool so tests get fresh connections after schema reset
    from apps.api.db import engine as global_engine
    global_engine.dispose()
    _mark_ensure_tables_invoked()
    _LOG.info("Schema created via ensure_tables (ensure_tables strategy)")


def _mask_password(url: str) -> str:
    """Mask password in DATABASE_URL for logging."""
    try:
        p = urlparse(url)
        netloc = p.netloc
        if p.password and "@" in netloc:
            user_part, host_part = netloc.rsplit("@", 1)
            if ":" in user_part:
                user, _ = user_part.split(":", 1)
                netloc = f"{user}:****@{host_part}"
            else:
                netloc = f"****@{host_part}"
        return urlunparse((p.scheme, netloc, p.path or "", "", "", ""))
    except Exception:
        return "***REDACTED***"


def ensure_test_db_guard() -> None:
    """Ensure tests use a *_test database. Run at session start."""
    in_test_mode = (
        os.environ.get("ENV") == "test" or os.environ.get("PYTEST_RUNNING") == "1"
    )
    if not in_test_mode:
        return

    test_url = os.environ.get("DATABASE_TEST_URL") or os.environ.get("DATABASE_URL_TEST")
    base_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ai_mkt")

    if test_url:
        effective = test_url
    else:
        effective = build_test_url(base_url)

    db_name = parse_db_name(effective)
    if not db_name.endswith("_test"):
        raise RuntimeError(
            f"Tests must use a *_test database. "
            f"Set DATABASE_URL_TEST or ensure DATABASE_URL db name ends with '_test'. "
            f"Current effective db: {db_name!r}"
        )

    os.environ["DATABASE_URL"] = effective
    masked = _mask_password(effective)
    _LOG.info("pytest using test DB: %s", masked)
    print(f"\n[pytest] using test DB: {masked}\n")

    create_database_if_missing(effective)
    if test_url:
        pass  # fixture will reset schema
    else:
        strategy = get_test_schema_strategy()
        if strategy == "alembic":
            if os.environ.get("RESET_TEST_DB", "").lower() in ("1", "true", "yes"):
                drop_all_tables(effective)
            run_alembic_upgrade_head(effective)


def _get_schema_authority() -> str:
    """Return SCHEMA_AUTHORITY or TEST_SCHEMA_STRATEGY (default alembic)."""
    v = (
        os.environ.get("SCHEMA_AUTHORITY")
        or os.environ.get("TEST_SCHEMA_STRATEGY")
        or "alembic"
    )
    v = v.strip().lower()
    if v not in ("alembic", "ensure_tables"):
        raise RuntimeError(
            f"SCHEMA_AUTHORITY must be 'alembic' or 'ensure_tables'. Got: {v!r}"
        )
    return v


def run_test_db_schema_fixture() -> None:
    """Reset test DB schema: drop public, recreate, apply schema via SCHEMA_AUTHORITY.
    DATABASE_TEST_URL only. Safety: db name must contain '_test' or ALLOW_TEST_DB_RESET=true."""
    url = os.environ.get("DATABASE_TEST_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_TEST_URL required for DB tests. "
            "export DATABASE_TEST_URL=postgresql://postgres:postgres@localhost:5432/ai_mkt_test"
        )
    _assert_schema_reset_safe(url)
    authority = _get_schema_authority()
    db_name = parse_db_name(url)
    db_user = parse_db_user(url)
    host = urlparse(url).hostname or "localhost"
    print(f"Reset test DB schema: {host}/{db_name} (authority={authority})")

    from sqlalchemy import create_engine, text

    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
            conn.execute(text(f"GRANT ALL ON SCHEMA public TO {db_user}"))
            conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
    finally:
        engine.dispose()

    if authority == "alembic":
        if not _recreate_schema_migration(url):
            raise RuntimeError(
                "Alembic schema creation failed. Fix migrations or run: alembic upgrade head"
            )
    else:
        _recreate_schema_ensure_tables(url)
    os.environ["DATABASE_URL"] = url
