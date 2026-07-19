"""
INSIGHT - Hybrid Search Implementation
Vector similarity + keyword search on hot profiles with HNSW optimization

NOTE: this module runs through the psycopg_pool cursors in backend/db.py, so
all SQL uses psycopg named placeholders (%(name)s) — NOT asyncpg $N style.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from psycopg.rows import dict_row

from backend.db import get_db_pool
from backend.models import ProfileResult, SearchRequest, SearchResponse

logger = logging.getLogger(__name__)


async def hybrid_search(request: SearchRequest) -> SearchResponse:
    """
    Execute hybrid semantic + keyword search.

    Query strategy:
    1. Generate embedding for query text (if semantic search enabled)
    2. Execute vector similarity search with HNSW index (ef_search=100)
    3. Apply filters (country, industry, seniority, experience, skills)
    4. Boost results with keyword matches in job_title/company
    5. Increment query_count_7d for matched profiles
    6. Return top N results with relevance scores

    Args:
        request: SearchRequest with query, filters, limit

    Returns:
        SearchResponse with results and metadata
    """
    start_time = time.time()

    pool = await get_db_pool()

    async with pool.connection() as conn:
        # Set HNSW search parameter for higher recall
        await conn.execute("SET hnsw.ef_search = 100")

        # Generate embedding for query (placeholder - implement with OpenAI)
        query_embedding = await _generate_query_embedding(request.query)

        if not query_embedding:
            # Fallback to keyword-only search
            results = await _keyword_search(conn, request)
        else:
            # Hybrid vector + keyword search
            results = await _vector_search(conn, request, query_embedding)

        # Increment query counters for matched profiles
        if results:
            profile_ids = [r["id"] for r in results]
            await _increment_query_counts(conn, profile_ids)
            await conn.commit()

    elapsed_ms = int((time.time() - start_time) * 1000)

    return SearchResponse(
        results=[ProfileResult(**r) for r in results],
        total_results=len(results),
        search_time_ms=elapsed_ms,
        query=request.query,
    )


async def _generate_query_embedding(query: str) -> Optional[List[float]]:
    """
    Generate embedding for search query.

    TODO: Implement with OpenAI API (384-d text-embedding-3-small)
    For now, returns None to trigger keyword search fallback.
    """
    # Placeholder - implement with OpenAI
    # from openai import AsyncOpenAI
    # client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    # response = await client.embeddings.create(
    #     input=query,
    #     model="text-embedding-3-small",
    #     dimensions=384
    # )
    # return response.data[0].embedding

    return None  # Fallback to keyword search


def _apply_filters(request: SearchRequest, filters: List[str], params: Dict[str, Any]) -> None:
    """Append the shared filter conditions and their named params in place —
    single source of truth for both search paths."""
    if request.country:
        filters.append("location_country = %(country)s")
        params["country"] = request.country

    if request.industry:
        filters.append("industry = %(industry)s")
        params["industry"] = request.industry

    if request.seniority:
        filters.append("seniority_level = %(seniority)s")
        params["seniority"] = request.seniority

    if request.min_experience is not None:
        filters.append("years_experience >= %(min_experience)s")
        params["min_experience"] = request.min_experience

    if request.max_experience is not None:
        filters.append("years_experience <= %(max_experience)s")
        params["max_experience"] = request.max_experience

    if request.skills:
        filters.append("top_skills && %(skills)s")
        params["skills"] = request.skills

    if request.min_quality_score is not None:
        filters.append("quality_score >= %(min_quality_score)s")
        params["min_quality_score"] = request.min_quality_score


async def _vector_search(conn, request: SearchRequest, query_embedding: List[float]) -> List[dict]:
    """
    Execute vector similarity search with filters.

    Uses HNSW index for fast approximate nearest neighbor search.
    """
    filters = ["is_deleted = FALSE", "embedding IS NOT NULL"]
    params: Dict[str, Any] = {
        # pgvector accepts the text form '[x,y,...]' cast to ::vector — no
        # adapter registration needed
        "embedding": "[" + ",".join(str(x) for x in query_embedding) + "]",
        "limit": request.limit,
    }
    _apply_filters(request, filters, params)

    where_clause = " AND ".join(filters)

    # Query with vector similarity (cosine distance)
    query = f"""
        SELECT
            id::text,
            linkedin_username,
            full_name,
            job_title,
            company_name,
            headline,
            location_country,
            industry,
            seniority_level,
            years_experience,
            top_skills,
            quality_score,
            hotness_score,
            (1 - (embedding <=> %(embedding)s::vector)) as relevance_score
        FROM profiles_hot
        WHERE {where_clause}
        ORDER BY embedding <=> %(embedding)s::vector
        LIMIT %(limit)s
    """

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, params)
        results: List[dict] = await cur.fetchall()

    return results


async def _keyword_search(conn, request: SearchRequest) -> List[dict]:
    """
    Fallback keyword search when embedding generation fails.

    Uses trigram similarity on full_name + job_title + company_name.
    """
    filters = ["is_deleted = FALSE"]
    params: Dict[str, Any] = {
        "pattern": f"%{request.query}%",
        "limit": request.limit,
    }
    _apply_filters(request, filters, params)

    where_clause = " AND ".join(filters)

    query = f"""
        SELECT
            id::text,
            linkedin_username,
            full_name,
            job_title,
            company_name,
            headline,
            location_country,
            industry,
            seniority_level,
            years_experience,
            top_skills,
            quality_score,
            hotness_score,
            similarity(full_name || ' ' || COALESCE(job_title, '') || ' ' || COALESCE(company_name, ''), %(pattern)s) as relevance_score
        FROM profiles_hot
        WHERE {where_clause}
          AND (
            full_name ILIKE %(pattern)s
            OR job_title ILIKE %(pattern)s
            OR company_name ILIKE %(pattern)s
            OR headline ILIKE %(pattern)s
          )
        ORDER BY relevance_score DESC, hotness_score DESC
        LIMIT %(limit)s
    """

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(query, params)
        results: List[dict] = await cur.fetchall()

    return results


async def _increment_query_counts(conn, profile_ids: List[str]):
    """Increment query_count_7d for matched profiles"""
    if not profile_ids:
        return

    query = """
        UPDATE profiles_hot
        SET query_count_7d = query_count_7d + 1
        WHERE id = ANY(%s::uuid[])
    """

    async with conn.cursor() as cur:
        await cur.execute(query, (profile_ids,))


async def get_profile_by_id(profile_id: str) -> Optional[dict]:
    """
    Get full profile details (hot + detail joined).

    Returns:
        Profile dict or None if not found
    """
    pool = await get_db_pool()

    query = """
        SELECT
            h.id::text,
            h.linkedin_username,
            h.full_name,
            h.job_title,
            h.company_name,
            h.headline,
            h.location_country,
            h.industry,
            h.seniority_level,
            h.years_experience,
            h.top_skills,
            h.quality_score,
            h.hotness_score,
            h.query_count_7d,
            h.click_count_7d,
            d.summary,
            d.experience_json,
            d.education_json,
            d.email,
            d.all_skills
        FROM profiles_hot h
        LEFT JOIN profiles_detail d ON h.id = d.id
        WHERE h.id = %s::uuid AND h.is_deleted = FALSE
    """

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, (profile_id,))
            result = await cur.fetchone()

    return result


async def record_profile_view(profile_id: str):
    """Increment click_count_7d for profile"""
    pool = await get_db_pool()

    query = """
        UPDATE profiles_hot
        SET click_count_7d = click_count_7d + 1
        WHERE id = %s::uuid
    """

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, (profile_id,))
        await conn.commit()
