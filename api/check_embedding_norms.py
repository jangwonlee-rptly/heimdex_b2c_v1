#!/usr/bin/env python3
"""Quick script to check if embeddings are normalized."""

import os
import sys
import asyncio
import numpy as np
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def check_norms():
    """Check L2 norms of stored embeddings."""

    db_url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not db_url:
        print("ERROR: DATABASE_URL or POSTGRES_URL not set")
        sys.exit(1)

    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

    print("Connecting to database...")
    engine = create_async_engine(db_url, echo=False)

    async with engine.begin() as conn:
        result = await conn.execute(text("""
            SELECT scene_id, image_vec, text_vec
            FROM scenes
            WHERE image_vec IS NOT NULL OR text_vec IS NOT NULL
            LIMIT 5
        """))

        scenes = result.fetchall()
        print(f"Found {len(scenes)} scenes\n")

        for row in scenes:
            scene_id = row[0]
            image_vec = row[1]
            text_vec = row[2]

            print(f"Scene: {scene_id}")

            if image_vec is not None:
                # Parse pgvector string
                if isinstance(image_vec, str):
                    vec_list = image_vec.strip('[]').split(',')
                    arr = np.array([float(x) for x in vec_list], dtype=np.float32)
                else:
                    arr = np.array(image_vec, dtype=np.float32)

                norm = np.linalg.norm(arr)
                print(f"  image_vec norm: {norm:.6f}")

            if text_vec is not None:
                # Parse pgvector string
                if isinstance(text_vec, str):
                    vec_list = text_vec.strip('[]').split(',')
                    arr = np.array([float(x) for x in vec_list], dtype=np.float32)
                else:
                    arr = np.array(text_vec, dtype=np.float32)

                norm = np.linalg.norm(arr)
                print(f"  text_vec norm: {norm:.6f}")

            print()


if __name__ == "__main__":
    asyncio.run(check_norms())
