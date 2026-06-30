"""
Utility functions for Knowtis (Embeddings, cosine similarity, etc.)
"""
import numpy as np
import hashlib
from typing import List

# Try importing sentence-transformers for production
try:
    from sentence_transformers import SentenceTransformer
    _model = SentenceTransformer('all-MiniLM-L6-v2')
except ImportError:
    _model = None


def generate_embedding(text: str) -> List[float]:
    """
    Generate MiniLM vector embedding for a given text (384 dimensions)
    Falls back to a deterministic hash-based mock embedding if libraries are missing.
    """
    if _model is not None:
        try:
            return _model.encode(text).tolist()
        except Exception:
            pass

    # Mock embedding: 384-dimensional deterministic unit vector based on md5 hashing
    vec = []
    for i in range(384):
        h = hashlib.md5(f"{text}-{i}".encode('utf-8')).hexdigest()
        val = int(h[:8], 16) / 4294967295.0
        vec.append(val * 2.0 - 1.0)
    
    # Normalize vector to unit length
    arr = np.array(vec)
    norm = np.linalg.norm(arr)
    if norm > 0:
        arr = arr / norm
    return arr.tolist()


def calculate_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Calculate cosine similarity between two vector embeddings
    """
    arr1 = np.array(vec1)
    arr2 = np.array(vec2)
    norm1 = np.linalg.norm(arr1)
    norm2 = np.linalg.norm(arr2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(arr1, arr2) / (norm1 * norm2))
