"""
Utility functions for Knowtis (Embeddings, cosine similarity, etc.)
"""
import hashlib
import threading
from typing import List, Optional

import numpy as np


def resolve_user_tier(user) -> str:
    """Return the effective tier for a User-like object.

    Centralised here so the rate limiter and the auth dependencies can share
    one definition (and avoid the circular import between ``dependencies``
    and ``rate_limit``).
    """
    if (getattr(user, "tier", None) or "free").lower() == "premium":
        return "premium"
    if getattr(user, "is_premium", False):
        return "premium"
    return "free"


# Lazily import sentence-transformers so module import doesn't pay the
# model-load cost (a few seconds) on every process boot — including CLI
# tasks, tests, and the small Celery beat scheduler.
_model = None
_model_lock = threading.Lock()
_SENTENCE_TRANSFORMERS_ERROR: Optional[BaseException] = None


def _get_model():
    global _model, _SENTENCE_TRANSFORMERS_ERROR
    if _model is not None:
        return _model
    with _model_lock:
        if _model is not None:
            return _model
        try:
            from sentence_transformers import SentenceTransformer

            _model = SentenceTransformer("all-MiniLM-L6-v2")
            return _model
        except (ImportError, OSError) as exc:
            _SENTENCE_TRANSFORMERS_ERROR = exc
            return None


def generate_embedding(text: str) -> List[float]:
    """
    Generate MiniLM vector embedding for a given text (384 dimensions)
    Falls back to a deterministic hash-based mock embedding if libraries are missing.
    """
    model = _get_model()
    if model is not None:
        try:
            return model.encode(text).tolist()
        except Exception:
            pass

    # Mock embedding: 384-dimensional deterministic unit vector based on md5 hashing.
    # Vectorized over the 384 indices to avoid 384 Python MD5 calls per text.
    idx = np.arange(384, dtype=np.int64)
    digest_hex = np.array(
        [hashlib.md5(f"{text}-{i}".encode("utf-8")).hexdigest()[:8] for i in range(384)]
    )
    raw = np.array([int(h, 16) for h in digest_hex], dtype=np.float64) / 4294967295.0
    vec = raw * 2.0 - 1.0
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


def calculate_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vector embeddings.
    """
    arr1 = np.asarray(vec1, dtype=np.float64)
    arr2 = np.asarray(vec2, dtype=np.float64)
    norm1 = np.linalg.norm(arr1)
    norm2 = np.linalg.norm(arr2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(arr1, arr2) / (norm1 * norm2))
