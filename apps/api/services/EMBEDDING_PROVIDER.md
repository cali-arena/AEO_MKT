# Embedding Provider

## Overview

Embedding generation uses a pluggable `EmbeddingProvider` interface. This enables tests to run without network access by swapping in a deterministic provider.

## How tests avoid network

- **ENV=test**: When `ENV=test` (or `ENVIRONMENT=test`), the deterministic provider is used automatically. It returns 384-dim vectors derived from a stable SHA256 hash of the text. No randomness, no network, no HuggingFace download.
- **conftest.py** sets `ENV=test` by default for all API tests, so the deterministic provider is used throughout the test suite.
- **Lazy loading**: The HuggingFace SentenceTransformer is never imported or initialized at import time. It loads only on first `embed()` call when using the real provider (non-test env).

## Usage

```python
from apps.api.services.embedding_provider import embed_text, embed_texts

# Single text
vec = embed_text("query string")

# Batch
vecs = embed_texts(["text1", "text2"])
```

## Provider selection

| Condition | Provider |
|-----------|----------|
| `EMBED_PROVIDER=deterministic` | DeterministicEmbeddingProvider |
| `EMBED_PROVIDER=huggingface` or `hf` | HuggingFaceEmbeddingProvider |
| `ENV=test` or `PYTEST_CURRENT_TEST` set | DeterministicEmbeddingProvider |
| Otherwise | HuggingFaceEmbeddingProvider |

## Forcing HuggingFace in tests

To test the real provider's error handling (no network; mock the model loader):

```python
def _raise(): raise RuntimeError("Embeddings model unavailable...")
monkeypatch.setenv("EMBED_PROVIDER", "huggingface")
monkeypatch.setattr(embeddings_module, "get_embedding_model", _raise)
ep._provider = None
# Now embed_text() uses HuggingFace and propagates the error
```
