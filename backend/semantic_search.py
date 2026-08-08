"""
semantic_search.py — Part 3: local semantic search using sentence-transformers.

Model  : sentence-transformers/all-MiniLM-L6-v2  (EXACT — do not substitute)
Version: sentence-transformers==3.0.0             (pinned in requirements.txt)

First run requires an internet connection to download model weights (~90 MB).
They are cached at ~/.cache/huggingface by default.
Every subsequent run is fully offline — no API key, no paid service.
"""

import logging
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load model once at module import time (cached after first download)
# ---------------------------------------------------------------------------
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

logger.info(f"[SemanticSearch] Loading model '{MODEL_NAME}' …")
_model = SentenceTransformer(MODEL_NAME)
logger.info("[SemanticSearch] Model ready.")


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def get_embedding(text: str) -> np.ndarray:
    """Return a 1-D numpy embedding vector for the given text."""
    return _model.encode(text, convert_to_numpy=True)


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """
    Compute cosine similarity between two vectors.
    Returns a float in [-1, 1]; higher means more similar.
    """
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


def rank_notes_by_query(query: str, notes: list[dict], top_k: int = 3) -> list[dict]:
    """
    Given a query string and a list of note dicts (each with a 'content' key),
    compute the embedding for the query and for every note's content,
    then return the top_k notes ranked by cosine similarity (highest first).

    Each returned dict has an added 'score' key with the similarity value.
    """
    query_vec = get_embedding(query)

    scored = []
    for note in notes:
        note_vec = get_embedding(note["content"])
        score = cosine_similarity(query_vec, note_vec)
        scored.append({**note, "score": round(score, 6)})

    # Sort descending by score — standard Python sort is fine here
    # (the no-built-in-sort restriction applies only to algorithms.py)
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
