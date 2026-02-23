"""Tests for embeddings service: env support and clear error on load failure."""

import pytest


def test_embeddings_load_failure_raises_clear_error(monkeypatch) -> None:
    """When HF provider's model load fails, error propagates (no silent fail). No network."""
    import apps.api.services.embedding_provider as ep
    import apps.api.services.embeddings as embeddings_module

    def _raise_unavailable():
        raise RuntimeError("Embeddings model unavailable. Set EMBEDDINGS_MODEL_PATH for offline use.")

    monkeypatch.setenv("EMBED_PROVIDER", "huggingface")
    monkeypatch.setattr(embeddings_module, "get_embedding_model", _raise_unavailable)
    ep._provider = None
    embeddings_module._model = None

    with pytest.raises(RuntimeError) as exc_info:
        ep.embed_text("x")

    msg = str(exc_info.value)
    assert "Embeddings model unavailable" in msg
    assert "EMBEDDINGS_MODEL_PATH" in msg


def test_deterministic_provider_no_network() -> None:
    """With ENV=test, embed_text returns fixed-size vectors without loading remote model."""
    from apps.api.services.embedding_provider import EMBEDDING_DIM, embed_text

    v = embed_text("hello")
    assert len(v) == EMBEDDING_DIM
    assert all(isinstance(x, float) for x in v)
    # Same input => same output (deterministic)
    assert embed_text("hello") == v
    # Different input => different output
    assert embed_text("world") != v
