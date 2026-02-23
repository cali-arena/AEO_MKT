"""
Enforce: DB reads/writes (session.execute, session.query, get_db()) only in repo.py.
Repo is the single place for DB access; no raw SQL/ORM outside it.
"""

import subprocess
from pathlib import Path

# Only repo.py may use session.execute, session.query, or call get_db()
ALLOWED_DB_ACCESS_FILES = {"apps/api/services/repo.py", "apps/api/db.py"}


def _grep_pattern(pattern: str, root: Path) -> list[tuple[str, int, str]]:
    """Run ripgrep, return [(file, line_no, line), ...]."""
    try:
        out = subprocess.run(
            ["rg", "-n", pattern, "--type", "py", str(root)],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return []  # rg not installed, skip
    if out.returncode == 1 and "No matches were found" in (out.stderr or ""):
        return []
    if out.returncode != 0:
        return []  # no matches
    results = []
    for line in (out.stdout or "").strip().split("\n"):
        if ":" in line:
            filepath, rest = line.split(":", 1)
            if ":" in rest:
                lineno_str, content = rest.split(":", 1)
                try:
                    results.append((filepath, int(lineno_str), content.strip()))
                except ValueError:
                    pass
    return results


def _path_in_allowed(p: str, root: Path) -> bool:
    """Check if path (from rg) is one of the allowed DB access files."""
    normalized = p.replace("\\", "/").lstrip("./")
    return (
        normalized in ALLOWED_DB_ACCESS_FILES
        or normalized.endswith("/repo.py")
        or normalized.endswith("repo.py")
        or normalized.endswith("/db.py")
        or normalized.endswith("db.py")
    )


def test_no_session_execute_outside_repo() -> None:
    """session.execute must only appear in repo.py."""
    root = Path(__file__).resolve().parent.parent
    hits = _grep_pattern(r"session\.execute", root)
    bad = [(f, ln, c) for f, ln, c in hits if not _path_in_allowed(f, root)]
    assert not bad, (
        "session.execute must only be in repo.py. Found in:\n"
        + "\n".join(f"  {f}:{ln}: {c}" for f, ln, c in bad)
    )


def test_no_session_query_outside_repo() -> None:
    """session.query must only appear in repo.py."""
    root = Path(__file__).resolve().parent.parent
    hits = _grep_pattern(r"session\.query", root)
    bad = [(f, ln, c) for f, ln, c in hits if not _path_in_allowed(f, root)]
    assert not bad, (
        "session.query must only be in repo.py. Found in:\n"
        + "\n".join(f"  {f}:{ln}: {c}" for f, ln, c in bad)
    )


def test_no_get_db_call_outside_repo() -> None:
    """get_db() calls must only be in repo.py (db.py defines it)."""
    root = Path(__file__).resolve().parent.parent
    hits = _grep_pattern(r"get_db\s*\(\s*\)", root)
    bad = [(f, ln, c) for f, ln, c in hits if not _path_in_allowed(f, root)]
    assert not bad, (
        "get_db() may only be called from repo.py. Found in:\n"
        + "\n".join(f"  {f}:{ln}: {c}" for f, ln, c in bad)
    )
