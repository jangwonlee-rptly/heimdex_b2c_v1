"""Search API routes for Heimdex B2C - keyword and semantic search."""

from typing import List, Optional
from uuid import UUID
from datetime import timedelta

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.db import get_db
from app.auth.middleware import AuthUser, get_current_user
from app.models.scene import Scene
from app.models.video import Video
from app.models.face import ScenePerson, FaceProfile
from app.config import settings
from app.logging_config import logger
from app.storage import StorageClient


router = APIRouter()


# Response models
class SceneResponse(BaseModel):
    """Scene response model matching frontend expectations."""
    id: str
    video_id: str
    start_time: float
    end_time: float
    transcript: Optional[str] = None
    thumbnail_url: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class VideoResponse(BaseModel):
    """Video response model."""
    video_id: str
    user_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    duration_s: Optional[float] = None
    size_bytes: int
    mime_type: str
    state: str
    created_at: str
    indexed_at: Optional[str] = None

    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    """Search result with scene, video, and relevance score."""
    scene: SceneResponse
    video: VideoResponse
    score: float
    highlights: Optional[List[str]] = None


class SearchResponse(BaseModel):
    """Search response with results and metadata."""
    results: List[SearchResult]
    total: int
    query: str
    search_type: str = "keyword"


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query(..., description="Search query text", min_length=1),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    person_id: Optional[str] = Query(None, description="Filter by person ID"),
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Search videos using keyword matching on transcripts.

    NOTE: Semantic search with embeddings is planned but requires ML model infrastructure.
    For now, this endpoint uses case-insensitive keyword matching on transcripts.

    This endpoint:
    1. Searches scenes using case-insensitive keyword matching on transcripts
    2. Returns matching scenes with their parent videos
    3. Supports pagination and filtering
    """
    logger.info(f"[search] Query: '{q}', user: {current_user.user_id}, type: keyword")

    try:
        user_uuid = UUID(current_user.user_id)
        search_pattern = f"%{q}%"

        # Main query joining scenes with videos
        query = (
            select(Scene, Video)
            .join(Video, Scene.video_id == Video.video_id)
            .where(Video.user_id == user_uuid)  # Filter by user
            .where(Video.state == 'indexed')  # Only search indexed videos
            .where(Scene.transcript.ilike(search_pattern))  # Keyword match on transcript
            .order_by(Scene.created_at.desc())  # Most recent first
        )

        # Optional: Filter by person_id
        if person_id:
            person_uuid = UUID(person_id)
            query = query.join(
                ScenePerson,
                ScenePerson.scene_id == Scene.scene_id
            ).where(ScenePerson.person_id == person_uuid)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        # Apply pagination
        query = query.limit(limit).offset(offset)

        # Execute query
        result = await db.execute(query)
        results = result.all()

        # Build response
        search_results = []
        for scene, video in results:
            # Generate thumbnail URL if thumbnail exists
            thumbnail_url = None
            if scene.thumbnail_key:
                try:
                    thumbnail_url = StorageClient.generate_presigned_download_url(
                        bucket=settings.storage_bucket_thumbnails,
                        object_key=scene.thumbnail_key,
                        expires=timedelta(hours=1)  # Cache for 1 hour
                    )
                except Exception as e:
                    logger.warning(f"Failed to generate thumbnail URL for scene {scene.scene_id}: {e}")

            # Convert scene
            scene_dict = {
                "id": str(scene.scene_id),
                "video_id": str(scene.video_id),
                "start_time": float(scene.start_s),
                "end_time": float(scene.end_s),
                "transcript": scene.transcript,
                "thumbnail_url": thumbnail_url,
                "created_at": scene.created_at.isoformat() if scene.created_at else None,
            }

            # Convert video
            video_dict = {
                "video_id": str(video.video_id),
                "user_id": str(video.user_id),
                "title": video.title,
                "description": video.description,
                "duration_s": float(video.duration_s) if video.duration_s else None,
                "size_bytes": video.size_bytes,
                "mime_type": video.mime_type,
                "state": video.state,
                "created_at": video.created_at.isoformat() if video.created_at else None,
                "indexed_at": video.indexed_at.isoformat() if video.indexed_at else None,
            }

            # Create highlights from transcript (optional)
            highlights = []
            if scene.transcript and q.lower() in scene.transcript.lower():
                highlights.append(scene.transcript)

            # Simple scoring: 1.0 for all matches (can be improved later with semantic search)
            score = 1.0

            search_results.append(
                SearchResult(
                    scene=SceneResponse(**scene_dict),
                    video=VideoResponse(**video_dict),
                    score=score,
                    highlights=highlights if highlights else None,
                )
            )

        logger.info(f"[search] Found {len(search_results)} results (total: {total})")

        return SearchResponse(
            results=search_results,
            total=total,
            query=q,
            search_type="keyword",
        )

    except Exception as e:
        logger.error(f"[search] Error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/hybrid", response_model=SearchResponse)
async def hybrid_search(
    q: str = Query(..., description="Search query text", min_length=1),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    person_id: Optional[str] = Query(None, description="Filter by person ID"),
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Hybrid search using RRF (Reciprocal Rank Fusion) of BM25 + vector similarity.

    This endpoint:
    1. Performs BM25 full-text search on transcripts (sparse retrieval)
    2. Performs vector similarity search on embeddings (dense retrieval)
    3. Fuses results using Reciprocal Rank Fusion
    4. Returns re-ranked results by combined score

    Feature flag: FEATURE_SEARCH_SYS_HYBRID_RRF must be enabled

    RRF Formula: score(d) = Σ 1 / (k + rank(d))
    where k is a constant (typically 20-100) and rank is position in each retriever
    """
    # Check if hybrid search is enabled
    if not settings.feature_search_sys_hybrid_rrf:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Hybrid search is not enabled. Set FEATURE_SEARCH_SYS_HYBRID_RRF=true to enable."
        )

    if not settings.feature_semantic_search:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Semantic search must be enabled for hybrid search. Set FEATURE_SEMANTIC_SEARCH=true."
        )

    logger.info(f"[search] Hybrid query: '{q}', user: {current_user.user_id}")

    try:
        # Generate query embedding for dense retrieval
        from app.search.embeddings import generate_text_embedding

        query_embedding = generate_text_embedding(q)
        if query_embedding is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate query embedding"
            )

        embedding_list = query_embedding.tolist()
        embedding_str = str(embedding_list)

        user_uuid = UUID(current_user.user_id)
        rrf_k = settings.search_hybrid_rrf_k
        bm25_weight = settings.search_hybrid_bm25_weight
        vector_weight = settings.search_hybrid_vector_weight

        # Apply ANN tuning if enabled
        if settings.feature_search_sys_ann_tuning:
            await db.execute(text(f"SET LOCAL hnsw.ef_search = {settings.search_ann_ef_search}"))
            topk = settings.search_ann_client_topk
        else:
            topk = limit * 5  # Fetch 5x candidates for fusion

        # RRF Hybrid Query: BM25 + Vector with Reciprocal Rank Fusion
        query_sql = text("""
            WITH bm25_results AS (
                -- Sparse retrieval: BM25-style text search using ts_rank
                SELECT
                    s.scene_id,
                    ROW_NUMBER() OVER (ORDER BY ts_rank(s.tsv, plainto_tsquery('english', :query)) DESC) as bm25_rank
                FROM scenes s
                JOIN videos v ON s.video_id = v.video_id
                WHERE v.user_id = CAST(:user_id AS uuid)
                  AND v.state = 'indexed'
                  AND s.tsv @@ plainto_tsquery('english', :query)
                  AND (CAST(:person_id AS uuid) IS NULL OR EXISTS (
                      SELECT 1 FROM scene_people sp
                      WHERE sp.scene_id = s.scene_id AND sp.person_id = CAST(:person_id AS uuid)
                  ))
                LIMIT :topk
            ),
            vector_results AS (
                -- Dense retrieval: Vector similarity search
                SELECT
                    s.scene_id,
                    ROW_NUMBER() OVER (ORDER BY (1 - (s.image_vec <-> CAST(:embedding AS vector))) DESC) as vector_rank
                FROM scenes s
                JOIN videos v ON s.video_id = v.video_id
                WHERE v.user_id = CAST(:user_id AS uuid)
                  AND v.state = 'indexed'
                  AND s.image_vec IS NOT NULL
                  AND (CAST(:person_id AS uuid) IS NULL OR EXISTS (
                      SELECT 1 FROM scene_people sp
                      WHERE sp.scene_id = s.scene_id AND sp.person_id = CAST(:person_id AS uuid)
                  ))
                ORDER BY s.image_vec <-> CAST(:embedding AS vector)
                LIMIT :topk
            ),
            fused_scores AS (
                -- RRF: Reciprocal Rank Fusion
                SELECT
                    COALESCE(b.scene_id, v.scene_id) as scene_id,
                    COALESCE(1.0 / (:rrf_k + b.bm25_rank), 0) * :bm25_weight as bm25_score,
                    COALESCE(1.0 / (:rrf_k + v.vector_rank), 0) * :vector_weight as vector_score,
                    (COALESCE(1.0 / (:rrf_k + b.bm25_rank), 0) * :bm25_weight +
                     COALESCE(1.0 / (:rrf_k + v.vector_rank), 0) * :vector_weight) as rrf_score
                FROM bm25_results b
                FULL OUTER JOIN vector_results v ON b.scene_id = v.scene_id
            )
            SELECT
                s.scene_id,
                s.video_id,
                s.start_s,
                s.end_s,
                s.transcript,
                s.thumbnail_key,
                s.created_at,
                f.bm25_score,
                f.vector_score,
                f.rrf_score
            FROM fused_scores f
            JOIN scenes s ON f.scene_id = s.scene_id
            ORDER BY f.rrf_score DESC
            LIMIT :limit OFFSET :offset
        """)

        # Execute query
        result = await db.execute(
            query_sql,
            {
                "query": q,
                "embedding": embedding_str,
                "user_id": str(user_uuid),
                "person_id": person_id,
                "rrf_k": rrf_k,
                "bm25_weight": bm25_weight,
                "vector_weight": vector_weight,
                "topk": topk,
                "limit": limit,
                "offset": offset,
            }
        )

        rows = result.fetchall()

        # Get total count
        count_sql = text("""
            SELECT COUNT(DISTINCT s.scene_id) FROM scenes s
            JOIN videos v ON s.video_id = v.video_id
            WHERE v.user_id = CAST(:user_id AS uuid)
              AND v.state = 'indexed'
              AND (s.tsv @@ plainto_tsquery('english', :query) OR s.image_vec IS NOT NULL)
              AND (CAST(:person_id AS uuid) IS NULL OR EXISTS (
                  SELECT 1 FROM scene_people sp
                  WHERE sp.scene_id = s.scene_id AND sp.person_id = CAST(:person_id AS uuid)
              ))
        """)

        count_result = await db.execute(
            count_sql,
            {
                "user_id": str(user_uuid),
                "person_id": person_id,
                "query": q,
            }
        )
        total = count_result.scalar() or 0

        # Build response
        search_results = []
        for row in rows:
            # Get video for this scene
            video_query = select(Video).where(Video.video_id == row.video_id)
            video_result = await db.execute(video_query)
            video = video_result.scalar_one()

            # Generate thumbnail URL
            thumbnail_url = None
            if row.thumbnail_key:
                try:
                    thumbnail_url = StorageClient.generate_presigned_download_url(
                        bucket=settings.storage_bucket_thumbnails,
                        object_key=row.thumbnail_key,
                        expires=timedelta(hours=1)
                    )
                except Exception as e:
                    logger.warning(f"Failed to generate thumbnail URL for scene {row.scene_id}: {e}")

            # Convert scene
            scene_dict = {
                "id": str(row.scene_id),
                "video_id": str(row.video_id),
                "start_time": float(row.start_s),
                "end_time": float(row.end_s),
                "transcript": row.transcript,
                "thumbnail_url": thumbnail_url,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }

            # Convert video
            video_dict = {
                "video_id": str(video.video_id),
                "user_id": str(video.user_id),
                "title": video.title,
                "description": video.description,
                "duration_s": float(video.duration_s) if video.duration_s else None,
                "size_bytes": video.size_bytes,
                "mime_type": video.mime_type,
                "state": video.state,
                "created_at": video.created_at.isoformat() if video.created_at else None,
                "indexed_at": video.indexed_at.isoformat() if video.indexed_at else None,
            }

            # Create highlights with scores
            highlights = [
                f"BM25: {row.bm25_score:.4f}",
                f"Vector: {row.vector_score:.4f}",
                f"RRF: {row.rrf_score:.4f}",
            ]

            search_results.append(
                SearchResult(
                    scene=SceneResponse(**scene_dict),
                    video=VideoResponse(**video_dict),
                    score=float(row.rrf_score),
                    highlights=highlights,
                )
            )

        logger.info(f"[search] Hybrid search found {len(search_results)} results (total: {total})")

        return SearchResponse(
            results=search_results,
            total=total,
            query=q,
            search_type="hybrid",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[search] Hybrid search error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hybrid search failed: {str(e)}"
        )


@router.get("/semantic", response_model=SearchResponse)
async def semantic_search(
    q: str = Query(..., description="Search query text", min_length=1),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    person_id: Optional[str] = Query(None, description="Filter by person ID"),
    text_weight: Optional[float] = Query(None, ge=0.0, le=1.0, description="Text similarity weight"),
    vision_weight: Optional[float] = Query(None, ge=0.0, le=1.0, description="Vision similarity weight"),
    current_user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Semantic search using vector similarity with pgvector.

    This endpoint:
    1. Generates text embedding for the query using BGE-M3
    2. Computes cosine similarity against scene text_vec and image_vec
    3. Applies hybrid scoring (text + vision + person boost)
    4. Returns ranked results by relevance score

    Feature flag: FEATURE_SEMANTIC_SEARCH must be enabled
    """
    # Check if semantic search is enabled
    if not settings.feature_semantic_search:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Semantic search is not enabled. Set FEATURE_SEMANTIC_SEARCH=true to enable."
        )

    logger.info(f"[search] Semantic query: '{q}', user: {current_user.user_id}")

    try:
        # Generate query embedding
        from app.search.embeddings import generate_text_embedding

        query_embedding = generate_text_embedding(q)
        if query_embedding is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate query embedding"
            )

        # Convert embedding to list for SQL
        embedding_list = query_embedding.tolist()
        embedding_str = str(embedding_list)

        # Get search weights (use config defaults if not provided)
        text_w = text_weight if text_weight is not None else settings.search_text_weight
        vision_w = vision_weight if vision_weight is not None else settings.search_vision_weight
        person_boost = settings.search_person_boost

        user_uuid = UUID(current_user.user_id)

        # Apply ANN tuning if enabled (FEATURE_SEARCH_SYS_ANN_TUNING)
        if settings.feature_search_sys_ann_tuning:
            # Set HNSW ef_search for this query (query-time accuracy/speed tradeoff)
            await db.execute(text(f"SET LOCAL hnsw.ef_search = {settings.search_ann_ef_search}"))
            # Use higher topK for re-ranking
            query_limit = settings.search_ann_client_topk
            logger.info(f"[search] ANN tuning enabled: ef_search={settings.search_ann_ef_search}, topK={query_limit}")
        else:
            query_limit = limit

        # Build SQL query using pgvector cosine distance operator
        # Uses SigLIP embeddings (1152-dim) for true multimodal search
        # Text queries are encoded with SigLIP's text encoder and compared against image_vec
        # This enables semantic visual search (e.g., "red car" finds scenes with red cars)
        query_sql = text("""
            WITH scene_scores AS (
                SELECT
                    s.scene_id,
                    s.video_id,
                    s.start_s,
                    s.end_s,
                    s.transcript,
                    s.thumbnail_key,
                    s.created_at,
                    -- Compute vision similarity using SigLIP embeddings (1152-dim)
                    -- Both query text and scene images are in the same embedding space
                    CASE
                        WHEN s.image_vec IS NOT NULL THEN (1 - (s.image_vec <-> CAST(:embedding AS vector)))
                        ELSE 0
                    END AS vision_similarity,
                    -- Check if person is in scene
                    CASE
                        WHEN CAST(:person_id AS uuid) IS NOT NULL AND EXISTS (
                            SELECT 1 FROM scene_people sp
                            WHERE sp.scene_id = s.scene_id AND sp.person_id = CAST(:person_id AS uuid)
                        ) THEN :person_boost
                        ELSE 0
                    END AS person_boost_score
                FROM scenes s
                JOIN videos v ON s.video_id = v.video_id
                WHERE v.user_id = CAST(:user_id AS uuid)
                  AND v.state = 'indexed'
                  AND s.image_vec IS NOT NULL
                  AND (CAST(:person_id AS uuid) IS NULL OR EXISTS (
                      SELECT 1 FROM scene_people sp
                      WHERE sp.scene_id = s.scene_id AND sp.person_id = CAST(:person_id AS uuid)
                  ))
            )
            SELECT
                scene_id,
                video_id,
                start_s,
                end_s,
                transcript,
                thumbnail_key,
                created_at,
                vision_similarity,
                person_boost_score,
                (vision_similarity * :vision_weight + person_boost_score) AS final_score
            FROM scene_scores
            -- Temporarily removed threshold to debug: WHERE (vision_similarity * :vision_weight + person_boost_score) > 0
            ORDER BY final_score DESC
            LIMIT :limit OFFSET :offset
        """)

        # Execute query
        result = await db.execute(
            query_sql,
            {
                "embedding": embedding_str,
                "user_id": str(user_uuid),
                "person_id": person_id,
                "person_boost": person_boost,
                "vision_weight": vision_w,
                "limit": query_limit,  # Use ANN-tuned limit if enabled
                "offset": offset,
            }
        )

        rows = result.fetchall()

        # Re-rank and trim to final limit if ANN tuning is enabled
        if settings.feature_search_sys_ann_tuning and len(rows) > settings.search_ann_final_limit:
            # Take top N after fetching broader candidates
            rows = rows[:settings.search_ann_final_limit]
            logger.info(f"[search] Re-ranked from {query_limit} to {settings.search_ann_final_limit} results")

        # Get total count (without pagination)
        # NOTE: Threshold removed for debugging - count all scenes with embeddings
        count_sql = text("""
            SELECT COUNT(*) FROM (
                SELECT s.scene_id
                FROM scenes s
                JOIN videos v ON s.video_id = v.video_id
                WHERE v.user_id = CAST(:user_id AS uuid)
                  AND v.state = 'indexed'
                  AND s.image_vec IS NOT NULL
                  AND (CAST(:person_id AS uuid) IS NULL OR EXISTS (
                      SELECT 1 FROM scene_people sp
                      WHERE sp.scene_id = s.scene_id AND sp.person_id = CAST(:person_id AS uuid)
                  ))
            ) subq
        """)

        count_result = await db.execute(
            count_sql,
            {
                # Only pass parameters actually used in the query
                "user_id": str(user_uuid),
                "person_id": person_id,
                # Commented out since threshold is disabled for debugging:
                # "embedding": embedding_str,
                # "vision_weight": vision_w,
            }
        )
        total = count_result.scalar() or 0

        # Build response
        search_results = []
        for row in rows:
            # Get video for this scene
            video_query = select(Video).where(Video.video_id == row.video_id)
            video_result = await db.execute(video_query)
            video = video_result.scalar_one()

            # Generate thumbnail URL if thumbnail exists
            thumbnail_url = None
            if row.thumbnail_key:
                try:
                    thumbnail_url = StorageClient.generate_presigned_download_url(
                        bucket=settings.storage_bucket_thumbnails,
                        object_key=row.thumbnail_key,
                        expires=timedelta(hours=1)  # Cache for 1 hour
                    )
                except Exception as e:
                    logger.warning(f"Failed to generate thumbnail URL for scene {row.scene_id}: {e}")

            # Convert scene
            scene_dict = {
                "id": str(row.scene_id),
                "video_id": str(row.video_id),
                "start_time": float(row.start_s),
                "end_time": float(row.end_s),
                "transcript": row.transcript,
                "thumbnail_url": thumbnail_url,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }

            # Convert video
            video_dict = {
                "video_id": str(video.video_id),
                "user_id": str(video.user_id),
                "title": video.title,
                "description": video.description,
                "duration_s": float(video.duration_s) if video.duration_s else None,
                "size_bytes": video.size_bytes,
                "mime_type": video.mime_type,
                "state": video.state,
                "created_at": video.created_at.isoformat() if video.created_at else None,
                "indexed_at": video.indexed_at.isoformat() if video.indexed_at else None,
            }

            # Create highlights with similarity scores
            highlights = [
                f"Vision similarity: {row.vision_similarity:.3f}",
            ]
            if row.person_boost_score > 0:
                highlights.append(f"Person boost: {row.person_boost_score:.3f}")

            search_results.append(
                SearchResult(
                    scene=SceneResponse(**scene_dict),
                    video=VideoResponse(**video_dict),
                    score=float(row.final_score),
                    highlights=highlights,
                )
            )

        logger.info(f"[search] Semantic search found {len(search_results)} results (total: {total})")

        return SearchResponse(
            results=search_results,
            total=total,
            query=q,
            search_type="semantic",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[search] Semantic search error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Semantic search failed: {str(e)}"
        )
