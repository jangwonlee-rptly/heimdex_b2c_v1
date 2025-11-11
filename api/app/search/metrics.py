"""
Search metrics and observability utilities.

FEATURE FLAG: feature_search_sys_eval

This module provides:
- Per-query metrics logging (latency, candidate counts, parameters)
- Search quality evaluation hooks
- Structured logging for analysis

Metrics emitted:
- query_latency_ms: End-to-end query time
- embedding_latency_ms: Embedding generation time
- ef_search: HNSW search breadth parameter
- topk_candidates: Number of candidates fetched
- final_results: Number of results returned
- search_type: keyword/semantic/hybrid
- fusion_weights: BM25 and vector weights (hybrid only)
"""

import time
from typing import Optional, Dict, Any
from contextlib import contextmanager

from app.config import settings
from app.logging_config import logger


class SearchMetrics:
    """
    Per-query metrics collector.

    Usage:
        >>> metrics = SearchMetrics(query="hello", search_type="semantic")
        >>> with metrics.time_embedding():
        ...     embedding = generate_embedding("hello")
        >>> with metrics.time_query():
        ...     results = execute_search()
        >>> metrics.log(result_count=10)
    """

    def __init__(self, query: str, search_type: str, user_id: str):
        """
        Initialize metrics collector.

        Args:
            query: Search query text
            search_type: One of: keyword, semantic, hybrid
            user_id: User ID for tracking
        """
        self.query = query
        self.search_type = search_type
        self.user_id = user_id

        # Timing metrics
        self.embedding_latency_ms: Optional[float] = None
        self.query_latency_ms: Optional[float] = None

        # Search parameters
        self.ef_search: Optional[int] = None
        self.topk_candidates: Optional[int] = None
        self.final_limit: Optional[int] = None

        # Fusion weights (hybrid only)
        self.bm25_weight: Optional[float] = None
        self.vector_weight: Optional[float] = None
        self.rrf_k: Optional[int] = None

        # Results
        self.result_count: Optional[int] = None
        self.total_candidates: Optional[int] = None

        # Start time for total query latency
        self._start_time = time.time()

    @contextmanager
    def time_embedding(self):
        """Context manager for timing embedding generation."""
        start = time.time()
        try:
            yield
        finally:
            self.embedding_latency_ms = (time.time() - start) * 1000

    @contextmanager
    def time_query(self):
        """Context manager for timing database query execution."""
        start = time.time()
        try:
            yield
        finally:
            self.query_latency_ms = (time.time() - start) * 1000

    def set_ann_params(self, ef_search: int, topk: int, final_limit: int):
        """Record ANN tuning parameters."""
        self.ef_search = ef_search
        self.topk_candidates = topk
        self.final_limit = final_limit

    def set_hybrid_params(self, bm25_weight: float, vector_weight: float, rrf_k: int):
        """Record hybrid fusion parameters."""
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight
        self.rrf_k = rrf_k

    def log(self, result_count: int, total_candidates: Optional[int] = None):
        """
        Log structured metrics for this query.

        Args:
            result_count: Number of results returned
            total_candidates: Total matching candidates (before pagination)
        """
        if not settings.feature_search_sys_eval:
            return  # Metrics disabled

        self.result_count = result_count
        self.total_candidates = total_candidates

        # Calculate total latency
        total_latency_ms = (time.time() - self._start_time) * 1000

        # Build metrics dict
        metrics_dict = {
            "event": "search_query",
            "query": self.query[:100],  # Truncate long queries
            "query_length": len(self.query),
            "search_type": self.search_type,
            "user_id": self.user_id,
            "result_count": result_count,
            "total_candidates": total_candidates,
            "total_latency_ms": round(total_latency_ms, 2),
        }

        # Add timing breakdown
        if self.embedding_latency_ms is not None:
            metrics_dict["embedding_latency_ms"] = round(self.embedding_latency_ms, 2)
        if self.query_latency_ms is not None:
            metrics_dict["query_latency_ms"] = round(self.query_latency_ms, 2)

        # Add ANN params if set
        if self.ef_search is not None:
            metrics_dict.update({
                "ef_search": self.ef_search,
                "topk_candidates": self.topk_candidates,
                "final_limit": self.final_limit,
            })

        # Add hybrid params if set
        if self.bm25_weight is not None:
            metrics_dict.update({
                "bm25_weight": self.bm25_weight,
                "vector_weight": self.vector_weight,
                "rrf_k": self.rrf_k,
            })

        # Log structured metrics
        logger.info("[metrics] Search query metrics", extra=metrics_dict)


def log_search_error(
    query: str,
    search_type: str,
    error: str,
    user_id: str,
):
    """
    Log search error for monitoring.

    Args:
        query: Search query that failed
        search_type: Type of search attempted
        error: Error message
        user_id: User ID
    """
    if not settings.feature_search_sys_eval:
        return

    logger.error(
        "[metrics] Search query failed",
        extra={
            "event": "search_error",
            "query": query[:100],
            "search_type": search_type,
            "error": error,
            "user_id": user_id,
        }
    )
