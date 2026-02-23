"""Cron DB session. Reuses apps.api.db session helpers."""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy.orm import Session

from apps.api.db import get_db


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """Provide a transactional DB session. Same as apps.api.db.get_db."""
    with get_db() as session:
        yield session
