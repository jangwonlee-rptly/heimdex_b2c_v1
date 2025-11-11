"""
Golden query evaluation for search quality measurement.

FEATURE FLAG: feature_search_sys_eval

This module provides tools to:
- Run golden queries and measure metrics (recall, MRR, latency)
- Compare results before/after config changes
- Generate evaluation reports

Usage:
    # CLI
    python -m app.search.eval --user-id <uuid>

    # Programmatic
    from app.search.eval import run_golden_queries
    results = await run_golden_queries(user_id="...")
"""

import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.logging_config import logger
from app.db import get_db


@dataclass
class EvalResult:
    """Evaluation result for a single query."""
    query_id: str
    query: str
    query_type: str
    latency_ms: float
    result_count: int
    recall_at_10: float
    mrr: float
    error: Optional[str] = None


@dataclass
class EvalReport:
    """Aggregate evaluation report."""
    total_queries: int
    successful_queries: int
    failed_queries: int
    avg_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    avg_recall_at_10: float
    avg_mrr: float
    results: List[EvalResult]


def load_golden_queries() -> List[Dict[str, Any]]:
    """
    Load golden queries from JSON file.

    Returns:
        List of query dicts

    Raises:
        FileNotFoundError: If golden_queries.json doesn't exist
    """
    golden_path = Path(__file__).parent.parent.parent / "golden_queries.json"

    if not golden_path.exists():
        raise FileNotFoundError(
            f"Golden queries file not found: {golden_path}\n"
            "Create this file with test queries for evaluation."
        )

    with open(golden_path) as f:
        data = json.load(f)

    return data.get("queries", [])


async def run_golden_queries(
    user_id: str,
    db: AsyncSession,
    search_type: Optional[str] = None,
) -> EvalReport:
    """
    Run golden queries and compute evaluation metrics.

    Args:
        user_id: User ID to run queries for
        db: Database session
        search_type: Filter to specific type (keyword/semantic/hybrid) or None for all

    Returns:
        EvalReport with aggregate metrics
    """
    if not settings.feature_search_sys_eval:
        raise RuntimeError(
            "Evaluation is disabled. Set FEATURE_SEARCH_SYS_EVAL=true to enable."
        )

    logger.info(f"[eval] Loading golden queries for user {user_id}")

    queries = load_golden_queries()

    # Filter by type if specified
    if search_type:
        queries = [q for q in queries if q.get("type") == search_type]

    logger.info(f"[eval] Running {len(queries)} golden queries")

    results = []
    for query_def in queries:
        result = await _eval_single_query(query_def, user_id, db)
        results.append(result)

        # Log result
        if result.error:
            logger.warning(f"[eval] Query {result.query_id} failed: {result.error}")
        else:
            logger.info(
                f"[eval] Query {result.query_id}: "
                f"latency={result.latency_ms:.0f}ms, "
                f"recall@10={result.recall_at_10:.2f}, "
                f"mrr={result.mrr:.2f}"
            )

    # Compute aggregate metrics
    report = _compute_report(results)

    logger.info(
        f"[eval] Evaluation complete: "
        f"{report.successful_queries}/{report.total_queries} successful, "
        f"avg_latency={report.avg_latency_ms:.0f}ms, "
        f"avg_recall@10={report.avg_recall_at_10:.2f}, "
        f"avg_mrr={report.avg_mrr:.2f}"
    )

    return report


async def _eval_single_query(
    query_def: Dict[str, Any],
    user_id: str,
    db: AsyncSession,
) -> EvalResult:
    """
    Evaluate a single golden query.

    Args:
        query_def: Query definition from golden_queries.json
        user_id: User ID
        db: Database session

    Returns:
        EvalResult with metrics
    """
    import time
    from app.search.routes import search, semantic_search, hybrid_search
    from app.auth.middleware import AuthUser

    query_id = query_def.get("id", "unknown")
    query = query_def.get("query", "")
    query_type = query_def.get("type", "keyword")

    # Create mock auth user
    auth_user = AuthUser(user_id=user_id, email="eval@test.com")

    try:
        # Time the query
        start = time.time()

        # Route to appropriate search endpoint
        if query_type == "semantic":
            response = await semantic_search(
                q=query,
                limit=10,
                offset=0,
                person_id=None,
                current_user=auth_user,
                db=db,
            )
        elif query_type == "hybrid":
            response = await hybrid_search(
                q=query,
                limit=10,
                offset=0,
                person_id=None,
                current_user=auth_user,
                db=db,
            )
        else:  # keyword
            response = await search(
                q=query,
                limit=10,
                offset=0,
                person_id=None,
                current_user=auth_user,
                db=db,
            )

        latency_ms = (time.time() - start) * 1000

        # Compute metrics
        recall_at_10 = _compute_recall(response.results, query_def)
        mrr = _compute_mrr(response.results, query_def)

        return EvalResult(
            query_id=query_id,
            query=query,
            query_type=query_type,
            latency_ms=latency_ms,
            result_count=len(response.results),
            recall_at_10=recall_at_10,
            mrr=mrr,
        )

    except Exception as e:
        logger.error(f"[eval] Query {query_id} failed: {e}", exc_info=True)
        return EvalResult(
            query_id=query_id,
            query=query,
            query_type=query_type,
            latency_ms=0,
            result_count=0,
            recall_at_10=0.0,
            mrr=0.0,
            error=str(e),
        )


def _compute_recall(results: List[Any], query_def: Dict[str, Any]) -> float:
    """
    Compute recall@10 based on expected tags/transcript.

    Simplified version - checks if any expected tag appears in results.
    For production, use labeled ground truth with known relevant scene IDs.

    Args:
        results: Search results
        query_def: Query definition with expected tags

    Returns:
        Recall score (0.0 to 1.0)
    """
    if not results:
        return 0.0

    expected_tags = set(query_def.get("expected_tags", []))
    expected_transcript = set(query_def.get("expected_transcript", []))

    if not expected_tags and not expected_transcript:
        # No ground truth - assume any result is relevant
        return 1.0 if results else 0.0

    # Check if results contain expected tags/transcript
    # This is a simplified proxy - replace with actual relevance judgments
    relevant_count = 0

    for result in results[:10]:
        # Check transcript
        transcript = result.scene.transcript or ""
        if any(term in transcript.lower() for term in expected_transcript):
            relevant_count += 1
            continue

        # Check highlights (contains tag info)
        if result.highlights:
            highlights_text = " ".join(result.highlights).lower()
            if any(tag in highlights_text for tag in expected_tags):
                relevant_count += 1

    # Recall = relevant_retrieved / total_relevant
    # For simplicity, assume all expected terms should appear at least once
    return min(relevant_count / max(len(expected_tags) + len(expected_transcript), 1), 1.0)


def _compute_mrr(results: List[Any], query_def: Dict[str, Any]) -> float:
    """
    Compute Mean Reciprocal Rank.

    MRR = 1 / rank_of_first_relevant_result

    Args:
        results: Search results
        query_def: Query definition

    Returns:
        MRR score (0.0 to 1.0)
    """
    if not results:
        return 0.0

    expected_tags = set(query_def.get("expected_tags", []))
    expected_transcript = set(query_def.get("expected_transcript", []))

    if not expected_tags and not expected_transcript:
        return 1.0  # First result is relevant by default

    # Find rank of first relevant result
    for rank, result in enumerate(results, start=1):
        transcript = result.scene.transcript or ""

        # Check if relevant
        if any(term in transcript.lower() for term in expected_transcript):
            return 1.0 / rank

        if result.highlights:
            highlights_text = " ".join(result.highlights).lower()
            if any(tag in highlights_text for tag in expected_tags):
                return 1.0 / rank

    return 0.0  # No relevant results found


def _compute_report(results: List[EvalResult]) -> EvalReport:
    """
    Compute aggregate evaluation report.

    Args:
        results: List of individual eval results

    Returns:
        EvalReport with aggregate metrics
    """
    successful = [r for r in results if r.error is None]
    failed = [r for r in results if r.error is not None]

    if not successful:
        return EvalReport(
            total_queries=len(results),
            successful_queries=0,
            failed_queries=len(failed),
            avg_latency_ms=0.0,
            p50_latency_ms=0.0,
            p95_latency_ms=0.0,
            avg_recall_at_10=0.0,
            avg_mrr=0.0,
            results=results,
        )

    latencies = sorted([r.latency_ms for r in successful])
    recalls = [r.recall_at_10 for r in successful]
    mrrs = [r.mrr for r in successful]

    return EvalReport(
        total_queries=len(results),
        successful_queries=len(successful),
        failed_queries=len(failed),
        avg_latency_ms=sum(latencies) / len(latencies),
        p50_latency_ms=latencies[len(latencies) // 2],
        p95_latency_ms=latencies[int(len(latencies) * 0.95)],
        avg_recall_at_10=sum(recalls) / len(recalls),
        avg_mrr=sum(mrrs) / len(mrrs),
        results=results,
    )


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Run golden query evaluation")
    parser.add_argument("--user-id", required=True, help="User ID to run queries for")
    parser.add_argument("--type", choices=["keyword", "semantic", "hybrid"], help="Filter by search type")
    args = parser.parse_args()

    async def main():
        async for db in get_db():
            report = await run_golden_queries(args.user_id, db, args.type)

            # Print report
            print("\n=== Evaluation Report ===")
            print(f"Total queries: {report.total_queries}")
            print(f"Successful: {report.successful_queries}")
            print(f"Failed: {report.failed_queries}")
            print(f"\nLatency:")
            print(f"  Avg: {report.avg_latency_ms:.0f}ms")
            print(f"  P50: {report.p50_latency_ms:.0f}ms")
            print(f"  P95: {report.p95_latency_ms:.0f}ms")
            print(f"\nQuality:")
            print(f"  Avg Recall@10: {report.avg_recall_at_10:.2%}")
            print(f"  Avg MRR: {report.avg_mrr:.2%}")

            break  # Only use first db session

    asyncio.run(main())
