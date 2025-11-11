"""
Text normalization utilities for canonical embedding generation.

FEATURE FLAG: search_sys_canonical_trim

This module provides utilities for normalizing text before embedding generation
to ensure consistent, high-quality search results.

Canonical text construction:
1. Field ordering: transcript → tags → persons (configurable)
2. Token limiting: Trim to max tokens to avoid truncation artifacts
3. Stable serialization: Consistent JSON formatting for tags/persons
"""

from typing import Optional, List, Dict
from app.config import settings
from app.logging_config import logger


def normalize_canonical_text(
    transcript: Optional[str] = None,
    tags: Optional[Dict[str, float]] = None,
    persons: Optional[List[str]] = None,
) -> str:
    """
    Construct canonical text representation from scene fields.

    This ensures:
    - Consistent field ordering (no embedding drift from field reordering)
    - Token budget adherence (prevents model truncation artifacts)
    - Stable serialization (JSON formatting doesn't affect embeddings)

    Args:
        transcript: ASR transcript text
        tags: Vision tags dict (e.g., {"crying": 0.85, "night": 0.72})
        persons: List of person names detected in scene

    Returns:
        Normalized canonical text string

    Example:
        >>> normalize_canonical_text(
        ...     transcript="Hello world",
        ...     tags={"person": 0.9, "indoor": 0.7},
        ...     persons=["Alice", "Bob"]
        ... )
        'Transcript: Hello world. Tags: person, indoor. People: Alice, Bob'
    """
    if not settings.feature_search_sys_canonical_trim:
        # Feature flag disabled - return raw transcript or empty
        return transcript or ""

    # Get field order from config
    field_order = [
        f.strip()
        for f in settings.search_canonical_field_order.split(",")
    ]

    # Build canonical parts in configured order
    parts = []
    for field in field_order:
        if field == "transcript" and transcript:
            # Trim transcript to reasonable length
            trimmed = _trim_text(transcript, max_chars=2000)
            parts.append(f"Transcript: {trimmed}")

        elif field == "tags" and tags:
            # Sort tags by score descending, take top N
            sorted_tags = sorted(
                tags.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]  # Top 10 tags
            tag_names = [tag for tag, score in sorted_tags]
            parts.append(f"Tags: {', '.join(tag_names)}")

        elif field == "persons" and persons:
            # Deduplicate and sort persons alphabetically for stability
            unique_persons = sorted(set(persons))[:5]  # Top 5 persons
            parts.append(f"People: {', '.join(unique_persons)}")

    # Join parts with period separator
    canonical = ". ".join(parts)

    # Apply token limit (approximate - 1 token ≈ 4 chars for English)
    max_tokens = settings.search_canonical_max_tokens
    max_chars = max_tokens * 4
    if len(canonical) > max_chars:
        canonical = canonical[:max_chars].rsplit(". ", 1)[0] + "."
        logger.debug(f"[text_utils] Trimmed canonical text to {max_tokens} tokens")

    return canonical


def _trim_text(text: str, max_chars: int) -> str:
    """
    Trim text to max characters, breaking at sentence boundary.

    Args:
        text: Text to trim
        max_chars: Maximum character length

    Returns:
        Trimmed text ending at sentence boundary
    """
    if len(text) <= max_chars:
        return text

    # Find last sentence boundary before max_chars
    trimmed = text[:max_chars]
    last_period = trimmed.rfind(". ")
    last_question = trimmed.rfind("? ")
    last_exclaim = trimmed.rfind("! ")

    boundary = max(last_period, last_question, last_exclaim)

    if boundary > 0:
        return trimmed[:boundary + 1]
    else:
        # No sentence boundary - hard cut with ellipsis
        return trimmed.rstrip() + "..."


def estimate_token_count(text: str) -> int:
    """
    Estimate token count for text (rough approximation).

    Uses simple heuristic: 1 token ≈ 4 characters for English.
    For precise counts, use tiktoken or model-specific tokenizer.

    Args:
        text: Input text

    Returns:
        Estimated token count
    """
    return len(text) // 4


def validate_canonical_length(text: str) -> bool:
    """
    Check if canonical text is within token budget.

    Args:
        text: Canonical text to validate

    Returns:
        True if within budget, False otherwise
    """
    estimated_tokens = estimate_token_count(text)
    max_tokens = settings.search_canonical_max_tokens
    return estimated_tokens <= max_tokens
