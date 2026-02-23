"""
Embedding provider abstraction for dependency injection.

EMBED_PROVIDER=deterministic or ENV=test or PYTEST_CURRENT_TEST => no network, hash-based vectors.
Otherwise HuggingFace SentenceTransformer (lazy-loaded on first embed).

No import-time model loading; everything is lazy.
"""

import hashlib
import logging
import os
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 384  # Must match ac_embedding.EMBEDDING_DIM


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding generation. Can be swapped for testing."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed texts into vectors. Returns list of 384-dim lists."""
        ...


class DeterministicEmbeddingProvider:
    """
    Deterministic provider: fixed 384-dim vectors from stable hash of text.
    Pure: no network, no randomness. Same input => same output.
    """

    def __init__(self, dim: int = EMBEDDING_DIM) -> None:
        self._dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_hash_to_vector(t, self._dim) for t in texts]


def _hash_to_vector(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Produce deterministic dim-dim vector from text hash. Pure, no randomness."""
    out: list[float] = []
    for i in range(dim):
        h = hashlib.sha256((text + "|" + str(i)).encode()).hexdigest()
        x = int(h[:8], 16) / (2**32) * 2 - 1
        out.append(x)
    return out


class HuggingFaceEmbeddingProvider:
    """
    HuggingFace SentenceTransformer provider. Loads model on first embed() call (lazy).
    No import-time loading.
    """

    def __init__(self) -> None:
        self._model = None

    def _get_model(self):
        if self._model is None:
            from apps.api.services.embeddings import get_embedding_model

            self._model = get_embedding_model()
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._get_model()
        embs = model.encode(texts)
        return [e.tolist() for e in embs]


_provider: EmbeddingProvider | None = None


def _use_deterministic_provider() -> bool:
    """
    True if we should use deterministic provider (no network).
    EMBED_PROVIDER=deterministic => always deterministic.
    EMBED_PROVIDER=huggingface (or hf) => always HuggingFace (for testing load failure).
    Otherwise: ENV=test or PYTEST_CURRENT_TEST => deterministic.
    """
    explicit = (os.getenv("EMBED_PROVIDER") or "").lower().strip()
    if explicit == "deterministic":
        return True
    if explicit in ("huggingface", "hf"):
        return False
    env = (os.getenv("ENV") or os.getenv("ENVIRONMENT") or "").lower()
    if env == "test":
        return True
    if os.getenv("PYTEST_CURRENT_TEST"):
        return True
    return False


def get_embedder(*, force_refresh: bool = False) -> EmbeddingProvider:
    """
    Return the active embedding provider. Lazy-initialized.
    Alias: get_embedding_provider.
    """
    return get_embedding_provider(force_refresh=force_refresh)


def get_embedding_provider(*, force_refresh: bool = False) -> EmbeddingProvider:
    """
    Return the active embedding provider. Lazy-initialized.

    Deterministic when:
    - EMBED_PROVIDER=deterministic
    - ENV=test
    - PYTEST_CURRENT_TEST is set (pytest run)

    Otherwise HuggingFace (loads model on first embed(), not at import).

    force_refresh: if True, re-resolve provider (for tests).
    """
    global _provider
    if force_refresh:
        _provider = None
    use_deterministic = _use_deterministic_provider()
    needs_reinit = _provider is None
    if not needs_reinit and use_deterministic and not isinstance(_provider, DeterministicEmbeddingProvider):
        needs_reinit = True
    if not needs_reinit and (not use_deterministic) and not isinstance(_provider, HuggingFaceEmbeddingProvider):
        needs_reinit = True

    if needs_reinit:
        if use_deterministic:
            _provider = DeterministicEmbeddingProvider()
            logger.info("Using deterministic embedding provider (no network)")
        else:
            _provider = HuggingFaceEmbeddingProvider()
            logger.info("Using HuggingFace embedding provider")
    return _provider


def embed_text(text: str) -> list[float]:
    """Convenience: embed single text. Uses active provider."""
    return get_embedding_provider().embed([text])[0]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Convenience: embed batch. Uses active provider."""
    if not texts:
        return []
    return get_embedding_provider().embed(texts)
