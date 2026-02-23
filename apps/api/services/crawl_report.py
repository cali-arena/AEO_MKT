"""Crawl report: append JSONL records for every URL evaluated by the pipeline."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Default report path: eval/reports/crawl_report.jsonl (relative to project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_REPORT_PATH = _PROJECT_ROOT / "eval" / "reports" / "crawl_report.jsonl"


def append_jsonl(path: str | Path, record: dict[str, Any]) -> None:
    """
    Append a single JSON record as one line to a JSONL file.
    Creates parent directories if they do not exist.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with open(p, "a", encoding="utf-8") as f:
        f.write(line)


def write_crawl_record(
    *,
    tenant_id: str,
    url: str,
    canonical_url: str,
    domain: str,
    page_type: str,
    decision: str,
    reason: str,
    path: str | Path | None = None,
) -> None:
    """
    Write one crawl evaluation record to the report.
    decision: "allowed" | "excluded"
    """
    report_path = path or DEFAULT_REPORT_PATH
    record = {
        "tenant_id": tenant_id,
        "url": url,
        "canonical_url": canonical_url,
        "domain": domain,
        "page_type": page_type,
        "decision": decision,
        "reason": reason,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    append_jsonl(report_path, record)
