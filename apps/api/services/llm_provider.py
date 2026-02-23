"""
LLM provider for /answer. Returns JSON with answer + claims (Claim schema).

When ENV=test, uses DeterministicAnswerProvider (no network).
Otherwise uses configurable provider (lazy).
"""

import json
import logging
import os
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol for answer generation. Returns raw JSON string only."""

    def generate(self, prompt: str, evidence_items: list[dict[str, Any]]) -> str:
        """Generate answer draft as JSON string. No prose outside JSON."""
        ...


class DeterministicAnswerProvider:
    """
    Deterministic provider for tests. Returns valid AnswerDraft JSON.
    No network. Uses evidence_ids from evidence_items.
    """

    def generate(self, prompt: str, evidence_items: list[dict[str, Any]]) -> str:
        valid_ids = [e["evidence_id"] for e in evidence_items if e.get("evidence_id")]
        claims = [
            {
                "text": (e.get("quote_span") or "")[:80].rstrip() or "Evidence.",
                "evidence_ids": [e["evidence_id"]],
                "confidence": 0.85,
            }
            for e in evidence_items[:3]
        ]
        draft = {
            "answer": " ".join(c["text"] for c in claims),
            "claims": claims,
        }
        return json.dumps(draft, ensure_ascii=False)


_provider: LLMProvider | None = None


def get_llm_provider(*, force_refresh: bool = False) -> LLMProvider:
    """
    Return the active LLM provider. Lazy-initialized.

    When ENV=test, returns DeterministicAnswerProvider (no network).
    Otherwise returns a real provider if configured.
    """
    global _provider
    if force_refresh:
        _provider = None
    if _provider is None:
        env = (os.getenv("ENV") or os.getenv("ENVIRONMENT") or "").lower()
        if env == "test":
            _provider = DeterministicAnswerProvider()
            logger.info("Using deterministic LLM provider (ENV=test)")
        else:
            _provider = _create_production_provider()
    return _provider


def _create_production_provider() -> LLMProvider:
    """Create production LLM provider. Use DeterministicAnswerProvider by default; extend for real API."""
    return DeterministicAnswerProvider()
