"""Database session factory and bootstrap."""

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from apps.api.models import Base
from apps.api.models.ac_embedding import ACEmbedding
from apps.api.models.ec_embedding import ECEmbedding
from apps.api.models.entity import Entity
from apps.api.models.entity_mention import EntityMention
from apps.api.models.ec_version import ECVersion
from apps.api.models.evidence import Evidence
from apps.api.models.raw_page import RawPage
from apps.api.models.relation import Relation
from apps.api.models.section import Section

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ai_mkt")

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=os.getenv("SQL_ECHO", "").lower() in ("1", "true", "yes"),
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Provide a transactional scope for DB operations. Always filter by tenant_id in queries."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def ensure_tables(bind=None):
    """Create all tables if they do not exist. Idempotent (checkfirst=True).
    bind: optional engine/connection; if None, uses global engine.
    """
    url = os.environ.get("DATABASE_URL", "")
    is_postgres = url.strip().lower().startswith("postgresql")
    in_test = os.environ.get("ENV") == "test" or os.environ.get("PYTEST_RUNNING") == "1"
    strategy = (os.environ.get("TEST_SCHEMA_STRATEGY") or "alembic").strip().lower()

    # Test guard: in tests, only run when strategy=ensure_tables (alembic default => no-op)
    if in_test and strategy != "ensure_tables":
        return
    # Postgres guard: prefer Alembic in dev/prod; only run create_all for ensure_tables in tests
    if is_postgres and not (in_test and strategy == "ensure_tables"):
        return
    _create_all_safe(bind if bind is not None else engine)


def _create_all_safe(bind) -> None:
    """Run create_all with checkfirst=True; ignore Postgres 'already exists' errors for idempotency.
    Uses AUTOCOMMIT so partial progress persists when a duplicate index is hit."""
    import sqlalchemy.exc
    from sqlalchemy.engine import Engine

    conn = bind.connect().execution_options(isolation_level="AUTOCOMMIT") if isinstance(bind, Engine) else bind
    try:
        Base.metadata.create_all(bind=conn, checkfirst=True)
    except sqlalchemy.exc.ProgrammingError as e:
        orig = e.orig
        ok = False
        if orig is not None:
            err_name = getattr(orig.__class__, "__module__", "") + "." + getattr(orig.__class__, "__name__", "")
            ok = "DuplicateTable" in err_name or "DuplicateObject" in err_name
        if not ok:
            ok = "already exists" in str(e).lower()
        if not ok:
            raise
    finally:
        if isinstance(bind, Engine):
            conn.close()
