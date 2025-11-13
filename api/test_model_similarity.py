#!/usr/bin/env python3
"""Test model service embedding quality."""

import os
import sys
import asyncio
import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import httpx


async def test_similarity():
    """Test similarity between query and stored embeddings."""

    # Get stored embedding
    db_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not db_url:
        print("ERROR: DATABASE_URL or POSTGRES_URL not set")
        sys.exit(1)

    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    print("Fetching stored embeddings from database...")
    engine = create_async_engine(db_url, echo=False)

    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT scene_id, image_vec, text_vec
            FROM scenes
            WHERE scene_id = '0fb4b7fa-ee91-4e9b-8328-170061d0d7fd'
        """))

        row = result.fetchone()
        if not row:
            print("Scene not found!")
            return

        scene_id = row[0]
        image_vec_str = row[1]
        text_vec_str = row[2]

        # Parse stored vectors
        image_vec = np.array([float(x) for x in image_vec_str.strip('[]').split(',')], dtype=np.float32)
        text_vec = np.array([float(x) for x in text_vec_str.strip('[]').split(',')], dtype=np.float32)

    print(f"Scene: {scene_id}")
    print(f"Stored image_vec norm: {np.linalg.norm(image_vec):.6f}")
    print(f"Stored text_vec norm: {np.linalg.norm(text_vec):.6f}")
    print()

    # Test various queries
    queries = [
        "two asian girls",
        "two people",
        "two women",
        "girls",
        "people",
        "woman",
        "IMG_8927",  # The actual title
    ]

    model_service_url = os.getenv("MODEL_SERVICE_URL", "http://localhost:8001")
    print(f"Connecting to model service: {model_service_url}\n")

    client = httpx.Client(base_url=model_service_url, timeout=60.0)

    for query_text in queries:
        try:
            # Generate query embedding
            response = client.post("/embed/text", json={"text": query_text, "model": "siglip"})
            response.raise_for_status()

            result = response.json()
            query_embedding = np.array(result["embedding"], dtype=np.float32)

            # Normalize
            norm = np.linalg.norm(query_embedding)
            if norm > 0:
                query_embedding = query_embedding / norm

            # Compute cosine distance
            vision_distance = float(np.linalg.norm(query_embedding - image_vec))
            text_distance = float(np.linalg.norm(query_embedding - text_vec))

            # Convert to similarity (1 - distance)
            vision_similarity = 1.0 - vision_distance
            text_similarity = 1.0 - text_distance

            print(f"Query: '{query_text}'")
            print(f"  Query embedding norm: {norm:.2f} -> {np.linalg.norm(query_embedding):.6f} (after norm)")
            print(f"  Vision distance: {vision_distance:.4f} → similarity: {vision_similarity:+.4f}")
            print(f"  Text distance: {text_distance:.4f} → similarity: {text_similarity:+.4f}")
            print()

        except Exception as e:
            print(f"Query '{query_text}' failed: {e}\n")

    client.close()


if __name__ == "__main__":
    asyncio.run(test_similarity())
