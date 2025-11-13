#!/usr/bin/env python3
"""
Normalize existing embeddings in the database.

This script updates all scene embeddings (text_vec and image_vec) to be unit vectors
(L2 norm = 1.0) as required by pgvector's cosine distance operator.

Run this after fixing the embedding generation code to normalize vectors.
"""

import os
import sys
import asyncio
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker


async def normalize_embeddings():
    """Normalize all existing embeddings in the database."""

    # Get database URL from environment
    db_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not db_url:
        print("ERROR: DATABASE_URL or POSTGRES_URL environment variable not set")
        sys.exit(1)

    # Convert to async URL if needed
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    print(f"Connecting to database...")
    engine = create_async_engine(db_url, echo=False)

    async with engine.begin() as conn:
        # Get all scenes with embeddings
        result = await conn.execute(text("""
            SELECT scene_id, image_vec, text_vec
            FROM scenes
            WHERE image_vec IS NOT NULL OR text_vec IS NOT NULL
        """))

        scenes = result.fetchall()
        print(f"Found {len(scenes)} scenes with embeddings to normalize")

        if len(scenes) == 0:
            print("No scenes to normalize!")
            return

        normalized_count = 0

        for row in scenes:
            scene_id = row[0]
            image_vec = row[1]
            text_vec = row[2]

            updates = []
            params = {"scene_id": scene_id}

            # Normalize image_vec if present
            if image_vec is not None:
                # Convert pgvector to numpy array
                # pgvector returns as string "[1.0, 2.0, ...]", need to parse
                if isinstance(image_vec, str):
                    image_vec = image_vec.strip('[]').split(',')
                    image_array = np.array([float(x) for x in image_vec], dtype=np.float32)
                else:
                    image_array = np.array(image_vec, dtype=np.float32)
                norm = np.linalg.norm(image_array)

                if norm > 0 and abs(norm - 1.0) > 0.01:  # Only update if not already normalized
                    normalized = image_array / norm
                    updates.append("image_vec = CAST(:image_vec AS vector(1152))")
                    # Convert to pgvector string format: "[1.0,2.0,3.0,...]"
                    params["image_vec"] = '[' + ','.join(str(x) for x in normalized.tolist()) + ']'
                    print(f"  Scene {scene_id}: Normalizing image_vec (L2 norm {norm:.2f} -> 1.0)")

            # Normalize text_vec if present
            if text_vec is not None:
                # Convert pgvector to numpy array
                # pgvector returns as string "[1.0, 2.0, ...]", need to parse
                if isinstance(text_vec, str):
                    text_vec = text_vec.strip('[]').split(',')
                    text_array = np.array([float(x) for x in text_vec], dtype=np.float32)
                else:
                    text_array = np.array(text_vec, dtype=np.float32)
                norm = np.linalg.norm(text_array)

                if norm > 0 and abs(norm - 1.0) > 0.01:  # Only update if not already normalized
                    normalized = text_array / norm
                    updates.append("text_vec = CAST(:text_vec AS vector(1152))")
                    # Convert to pgvector string format: "[1.0,2.0,3.0,...]"
                    params["text_vec"] = '[' + ','.join(str(x) for x in normalized.tolist()) + ']'
                    print(f"  Scene {scene_id}: Normalizing text_vec (L2 norm {norm:.2f} -> 1.0)")

            # Update scene if needed
            if updates:
                update_sql = f"""
                    UPDATE scenes
                    SET {', '.join(updates)}
                    WHERE scene_id = :scene_id
                """
                await conn.execute(text(update_sql), params)
                normalized_count += 1

        print(f"\nNormalized {normalized_count} scenes")
        print("Done!")


if __name__ == "__main__":
    asyncio.run(normalize_embeddings())
