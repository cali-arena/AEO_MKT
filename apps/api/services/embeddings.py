"""
Centralized embedding model loading (singleton).

Used by HuggingFaceEmbeddingProvider; not called directly in normal flows.
All embedding generation goes through embedding_provider (which uses deterministic
provider when ENV=test). No import-time loading; model loads on first use.
"""

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
UNAVAILABLE_MSG = "Embeddings model unavailable. Set EMBEDDINGS_MODEL_PATH for offline use."
_model: "SentenceTransformer | None" = None


def get_embedding_model() -> "SentenceTransformer":
    """Load embedding model singleton. Configurable via EMBEDDINGS_MODEL_NAME and EMBEDDINGS_MODEL_PATH env."""
    global _model
    if _model is None:
        model_path = os.getenv("EMBEDDINGS_MODEL_PATH", "").strip()
        model_name = os.getenv("EMBEDDINGS_MODEL_NAME", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        load_from = model_path if model_path else model_name
        logger.info("Loading embedding model: %s", load_from)
        try:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer(load_from)
        except Exception as e:
            raise RuntimeError(UNAVAILABLE_MSG) from e
    return _model
