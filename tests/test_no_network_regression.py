"""Regression: ensure no network/model downloads occur during tests.

If someone reintroduces HuggingFace provider in tests, CI fails immediately.
"""

import os
import socket
import time

import pytest


def test_embed_provider_must_be_deterministic() -> None:
    """EMBED_PROVIDER must be 'deterministic' during tests to avoid network/model downloads."""
    assert os.getenv("EMBED_PROVIDER") == "deterministic", (
        "Tests must use EMBED_PROVIDER=deterministic to avoid network. "
        "Set in conftest.py: os.environ['EMBED_PROVIDER'] = 'deterministic'"
    )


def test_embed_text_fast_and_deterministic() -> None:
    """embed_text returns quickly and deterministically (no model load, no network)."""
    from apps.api.services.embedding_provider import EMBEDDING_DIM, embed_text, get_embedding_provider

    get_embedding_provider(force_refresh=True)

    t0 = time.perf_counter()
    v1 = embed_text("hello")
    v2 = embed_text("hello")
    v3 = embed_text("world")
    elapsed = time.perf_counter() - t0

    assert len(v1) == EMBEDDING_DIM
    assert all(isinstance(x, float) for x in v1)
    assert v1 == v2, "Same input must yield same output (deterministic)"
    assert v1 != v3, "Different input must yield different output"
    assert elapsed < 0.5, f"embed_text must be fast (<0.5s), took {elapsed:.3f}s (indicates model load/network)"


def test_no_outbound_network_on_embed(monkeypatch) -> None:
    """Block network; embed_text must still succeed (deterministic provider uses no network)."""
    from apps.api.services.embedding_provider import embed_text, get_embedding_provider

    monkeypatch.setenv("EMBED_PROVIDER", "deterministic")
    monkeypatch.setenv("ENV", "test")
    get_embedding_provider(force_refresh=True)

    _original_socket = socket.socket

    def _blocking_socket(family=-1, type=-1, proto=-1, fileno=None):
        s = _original_socket(family, type, proto, fileno)

        _orig_connect = s.connect

        def _blocked_connect(addr):
            raise RuntimeError(
                "Outbound network blocked in tests. EMBED_PROVIDER must be 'deterministic'."
            )

        s.connect = _blocked_connect
        return s

    monkeypatch.setattr("socket.socket", _blocking_socket)

    v = embed_text("no network needed")
    assert len(v) == 384
    assert all(isinstance(x, float) for x in v)
