"""
Embedding generation utilities for semantic search.

This module uses the centralized model service for generating query embeddings.
No models are loaded in the API process - all inference is delegated to the model service.

Uses SigLIP for multimodal embeddings (text and vision in same 1152-dim space).

Warmup & Caching (FEATURE_SEARCH_SYS_ANN_TUNING):
- Connection pooling with warmup requests at boot
- Simple LRU cache for frequent queries (person lookups, etc.)
- Configurable timeouts and retries
"""

import os
from typing import Optional
from functools import lru_cache
import numpy as np
import httpx

from app.logging_config import logger


# Model service client (lightweight HTTP client)
_http_client: Optional[httpx.Client] = None
_warmup_done: bool = False


def get_model_service_client() -> httpx.Client:
    """
    Get HTTP client for model service with connection pooling.

    Returns:
        httpx.Client instance with pooling enabled
    """
    global _http_client, _warmup_done

    if _http_client is None:
        base_url = os.getenv("MODEL_SERVICE_URL", "http://localhost:8001")

        # Create client with connection pooling and reasonable limits
        limits = httpx.Limits(
            max_keepalive_connections=10,  # Keep 10 connections alive
            max_connections=20,  # Max 20 concurrent connections
            keepalive_expiry=30.0,  # Keep connections alive for 30s
        )

        _http_client = httpx.Client(
            base_url=base_url,
            timeout=60.0,
            limits=limits,
            transport=httpx.HTTPTransport(retries=2),  # Retry failed requests
        )
        logger.info(f"[embeddings] Initialized model service client: {base_url} (pooling enabled)")

        # Warmup on first init
        if not _warmup_done:
            warmup_model_service()
            _warmup_done = True

    return _http_client


def warmup_model_service():
    """
    Perform warmup requests to model service to establish connections.

    This:
    - Establishes HTTP connection pool
    - Loads models into memory (if not already loaded)
    - Validates service is reachable

    Called automatically on first client init.
    """
    global _http_client

    if _http_client is None:
        return  # Client not initialized yet, skip warmup

    try:
        # Warmup request: Generate embedding for dummy text
        logger.info("[embeddings] Warming up model service...")

        warmup_payload = {
            "text": "warmup query",
            "model": "siglip"
        }

        response = _http_client.post("/embed/text", json=warmup_payload)
        response.raise_for_status()

        logger.info("[embeddings] Model service warmup completed successfully")

    except Exception as e:
        logger.warning(f"[embeddings] Model service warmup failed (non-fatal): {e}")
        # Don't fail startup - service might not be ready yet


@lru_cache(maxsize=128)
def _cached_text_embedding(text: str) -> Optional[tuple]:
    """
    Cached version of embedding generation (returns tuple for hashability).

    LRU cache with 128 entries - useful for:
    - Repeated person name lookups
    - Common search queries
    - Profile embedding generation

    Returns tuple instead of np.ndarray since numpy arrays aren't hashable.
    """
    embedding = _generate_text_embedding_uncached(text)
    if embedding is None:
        return None
    return tuple(embedding.tolist())


def generate_text_embedding(text: str, use_cache: bool = True) -> Optional[np.ndarray]:
    """
    Generate text embedding for search query (with optional caching).

    Args:
        text: Query text to embed
        use_cache: If True, check LRU cache first (default: True)

    Returns:
        1152-dim embedding vector or None if generation fails
    """
    if use_cache:
        cached = _cached_text_embedding(text)
        if cached is not None:
            return np.array(cached, dtype=np.float32)
        return None
    else:
        return _generate_text_embedding_uncached(text)


def _generate_text_embedding_uncached(text: str) -> Optional[np.ndarray]:
    """
    Generate text embedding for search query using model service.

    This produces 1152-dim embeddings that are compatible with vision embeddings,
    enabling true multimodal search (text queries can find similar images).

    Args:
        text: Query text to embed

    Returns:
        1152-dim embedding vector or None if generation fails
    """
    if not text or not text.strip():
        return None

    try:
        client = get_model_service_client()

        # Call model service
        payload = {
            "text": text,
            "model": "siglip"
        }

        logger.info(f"[embeddings] Generating text embedding via model service: '{text[:50]}'")

        response = client.post("/embed/text", json=payload)
        response.raise_for_status()

        result = response.json()
        embedding = np.array(result["embedding"], dtype=np.float32)

        logger.info(f"[embeddings] Generated {result['dimension']}-dim embedding in {result['latency_ms']:.0f}ms")

        return embedding

    except httpx.HTTPError as e:
        logger.error(f"[embeddings] Model service request failed: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"[embeddings] Failed to generate text embedding: {e}", exc_info=True)
        return None


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Compute cosine similarity between two vectors.

    Args:
        vec1: First vector
        vec2: Second vector

    Returns:
        Cosine similarity score (0-1)
    """
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(dot_product / (norm1 * norm2))
