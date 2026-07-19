"""
INSIGHT - Hybrid Search Implementation
Combines vector similarity + full-text search + structured filters

Negative Spaces Implementation:
- Query must produce embedding
- Score bounds [0.0, 1.0] enforced
- NULL handling in filters
- Timeout enforcement
"""

import asyncio
import logging
from typing import Any, List

import asyncpg

from backend.api.models import ProfileResult, SearchRequest
from backend.data_pipeline.embeddings import providers

logger = logging.getLogger(__name__)


class SearchError(Exception):
    """Raised when search operations fail"""

    pass


async def hybrid_search(
    conn: asyncpg.Connection, request: SearchRequest
) -> tuple[List[ProfileResult], int]:
    """
    Execute hybrid search combining vector + lexical + filters.

    NEGATIVE SPACE CONTRACT:
    - query text is a HARD filter: only profiles whose search_vector matches
      plainto_tsquery are candidates; the hybrid score only ranks them
    - total_count == count of rows matching filters + query text (never the
      whole corpus)
    - if the lexical gate matches ZERO rows (residual intents like "candidate"
      have no lexical anchor), falls back to _vector_browse: the filtered set
      ranked by vector similarity, total_count == filtered-set size
    - empty/whitespace query -> keyword_search browse mode (no embedding call)
    - Returns (results, total_count)
    - Results list length <= request.limit
    - All scores in [0.0, 1.0]

    Args:
        conn: Database connection
        request: Search request parameters

    Returns:
        Tuple of (results list, total count)

    Raises:
        SearchError: If search fails
    """
    try:
        # Browse mode: without query text there is nothing to match or rank
        # semantically — the filter-only path orders by recency and counts correctly
        if not request.query or not request.query.strip():
            return await keyword_search(conn, request)

        # Check if we have any embeddings in the database
        has_embeddings = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM profiles WHERE embedding IS NOT NULL LIMIT 1)"
        )

        # If no embeddings, use keyword-only search
        if not has_embeddings:
            logger.info("No embeddings found, using keyword-only search")
            return await keyword_search(conn, request)

        # Generate query embedding with graceful fallback to keyword search.
        # embed_single is a blocking HTTP call — run it in a worker thread so
        # it can't stall the event loop for other requests.
        try:
            provider = providers.get_provider()
            query_embedding = await asyncio.to_thread(provider.embed_single, request.query)
        except Exception as e:
            logger.warning(f"Embedding provider error, falling back to keyword search: {e}")
            return await keyword_search(conn, request)

        if query_embedding is None:
            logger.warning("Query embedding is None, falling back to keyword search")
            return await keyword_search(conn, request)

        # Build WHERE clause for filters
        where_conditions = ["embedding IS NOT NULL", "is_deleted = FALSE"]
        # Convert embedding list to string format for asyncpg
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Filter params come first ($1..$N) so the count query can reuse the
        # same WHERE clause text and a prefix of the same params list
        params: List[Any] = []
        param_idx = 1

        # Location filters
        if request.location_country:
            where_conditions.append(f"location_country = ${param_idx}")
            params.append(request.location_country)
            param_idx += 1

        # Region filter (support both single and multiple)
        regions_to_filter = []
        if request.regions:
            regions_to_filter = request.regions
        elif request.region:
            regions_to_filter = [request.region]

        if regions_to_filter:
            where_conditions.append(f"region = ANY(${param_idx})")
            params.append(regions_to_filter)
            param_idx += 1

        # Locality filter (support both single and multiple)
        localities_to_filter = []
        if request.localities:
            localities_to_filter = request.localities
        elif request.locality:
            localities_to_filter = [request.locality]

        if localities_to_filter:
            where_conditions.append(f"locality = ANY(${param_idx})")
            params.append(localities_to_filter)
            param_idx += 1

        # Experience filters
        if request.min_years_experience is not None:
            where_conditions.append(f"years_experience >= ${param_idx}")
            params.append(request.min_years_experience)
            param_idx += 1

        if request.max_years_experience is not None:
            where_conditions.append(f"years_experience <= ${param_idx}")
            params.append(request.max_years_experience)
            param_idx += 1

        # Skills filter (array containment)
        if request.skills:
            where_conditions.append(f"skills @> ${param_idx}")
            params.append(request.skills)
            param_idx += 1

        # Industry filter (support both single and multiple)
        industries_to_filter = []
        if request.industries:
            industries_to_filter = request.industries
        elif request.industry:
            industries_to_filter = [request.industry]

        if industries_to_filter:
            where_conditions.append(f"industry = ANY(${param_idx})")
            params.append(industries_to_filter)
            param_idx += 1

        # Job title filter (partial match, case-insensitive)
        if request.job_title:
            where_conditions.append(f"job_title ILIKE ${param_idx}")
            params.append(f"%{request.job_title}%")
            param_idx += 1

        # Company filter (partial match, case-insensitive)
        if request.company:
            where_conditions.append(f"company_name ILIKE ${param_idx}")
            params.append(f"%{request.company}%")
            param_idx += 1

        # Contact information filters (exclude NULL, empty string, and "-")
        if request.has_linkedin:
            where_conditions.append(
                "linkedin_url IS NOT NULL AND linkedin_url != '' AND linkedin_url != '-'"
            )
        if request.has_email:
            where_conditions.append("email IS NOT NULL AND email != '' AND email != '-'")
        if request.has_phone:
            where_conditions.append("phone IS NOT NULL AND phone != '' AND phone != '-'")
        if request.has_website:
            where_conditions.append("website IS NOT NULL AND website != '' AND website != '-'")
        if request.has_twitter:
            where_conditions.append("twitter IS NOT NULL AND twitter != '' AND twitter != '-'")
        if request.has_github:
            where_conditions.append("github IS NOT NULL AND github != '' AND github != '-'")

        # Quality score filter
        if request.min_quality_score is not None:
            where_conditions.append(f"content_quality_score >= ${param_idx}")
            params.append(request.min_quality_score)
            param_idx += 1

        # Data completeness filter
        if request.min_data_completeness is not None:
            where_conditions.append(f"data_completeness_pct >= ${param_idx}")
            params.append(request.min_data_completeness)
            param_idx += 1

        where_clause = " AND ".join(where_conditions)

        # Note: the query is gated by the GIN full-text index, not an ANN scan,
        # so hnsw.ef_search does not apply (request.ef_search is kept in the API
        # for compatibility).

        # Build hybrid search query
        # Append parameters for remaining placeholders
        params.append(request.query)  # $param_idx
        tsquery_idx = param_idx
        param_idx += 1

        params.append(embedding_str)  # $param_idx
        embedding_idx = param_idx
        param_idx += 1

        params.append(request.vector_weight)  # $param_idx
        vector_weight_idx = param_idx
        param_idx += 1

        params.append(request.lexical_weight)  # $param_idx
        lexical_weight_idx = param_idx
        param_idx += 1

        params.append(request.limit)  # $param_idx
        limit_idx = param_idx
        param_idx += 1

        params.append(request.offset)  # $param_idx
        offset_idx = param_idx

        # The query text is a hard filter: candidates must match the full-text
        # query; the hybrid score only ranks them. Vector distance is computed
        # for the top lexical matches by ts_rank; the rank window always covers
        # the requested page (deep pages cost proportionally more, bounded by
        # the tier's MAX_OFFSET) so pages are never silently empty while
        # total_count reports more. Ties break on id so pagination is
        # deterministic.
        query = f"""
        WITH lexical_matches AS (
            SELECT
                id,
                full_name,
                first_name,
                last_name,
                job_title,
                company_name,
                industry,
                location,
                location_country,
                region,
                locality,
                years_experience,
                skills,
                headline,
                summary,
                linkedin_url,
                linkedin_username,
                email,
                phone,
                website,
                twitter,
                github,
                content_quality_score,
                data_completeness_pct,
                embedding,
                ts_rank(search_vector, plainto_tsquery('english', ${tsquery_idx})) AS lexical_rank
            FROM profiles
            WHERE {where_clause}
              AND search_vector @@ plainto_tsquery('english', ${tsquery_idx})
            ORDER BY lexical_rank DESC, id
            LIMIT GREATEST(5000, ${limit_idx}::int + ${offset_idx}::int)
        )
        SELECT
            id,
            full_name,
            first_name,
            last_name,
            job_title,
            company_name,
            industry,
            location,
            location_country,
            region,
            locality,
            years_experience,
            skills,
            headline,
            summary,
            linkedin_url,
            linkedin_username,
            email,
            phone,
            website,
            twitter,
            github,
            content_quality_score,
            data_completeness_pct,
            1 - (embedding <=> ${embedding_idx}::vector) AS vector_similarity,
            lexical_rank,
            ((1 - (embedding <=> ${embedding_idx}::vector)) * ${vector_weight_idx}) + (lexical_rank * ${lexical_weight_idx}) AS score
        FROM lexical_matches
        ORDER BY score DESC, id
        LIMIT ${limit_idx} OFFSET ${offset_idx}
        """

        # Count first — a cheap GIN probe, and the gate may match nothing: a
        # natural-language residual like "candidate" has no lexical anchor.
        # The count reuses the search's WHERE clause + a prefix of its params,
        # so it always reflects the same match set.
        count_query = f"""
            SELECT count(*) FROM profiles
            WHERE {where_clause}
              AND search_vector @@ plainto_tsquery('english', ${tsquery_idx})
        """
        total_count = await conn.fetchval(count_query, *params[:tsquery_idx])
        assert total_count is not None, "count(*) always returns a row"

        if total_count == 0:
            logger.info(
                f"Lexical gate matched 0 rows for {request.query!r} — "
                "vector-browse fallback over the filtered set"
            )
            return await _vector_browse(
                conn, request, where_clause, params[: tsquery_idx - 1], embedding_str
            )

        # Execute search
        logger.debug(
            f"Executing hybrid search: query='{request.query}', filters={len(where_conditions)}"
        )

        rows = await conn.fetch(query, *params)

        # Convert to ProfileResult objects
        results = []
        for row in rows:
            result = ProfileResult(
                id=str(row["id"]),
                full_name=row["full_name"],
                first_name=row["first_name"],
                last_name=row["last_name"],
                job_title=row["job_title"],
                company_name=row["company_name"],
                industry=row["industry"],
                location=row["location"],
                location_country=row["location_country"],
                region=row["region"],
                locality=row["locality"],
                years_experience=row["years_experience"],
                skills=row["skills"],
                headline=row["headline"],
                summary=row["summary"],
                linkedin_url=row["linkedin_url"],
                linkedin_username=row["linkedin_username"],
                email=row["email"],
                phone=row["phone"],
                website=row["website"],
                twitter=row["twitter"],
                github=row["github"],
                score=float(row["score"]),
                vector_similarity=float(row["vector_similarity"]),
                lexical_rank=float(row["lexical_rank"]),
                content_quality_score=(
                    float(row["content_quality_score"]) if row["content_quality_score"] else None
                ),
                data_completeness_pct=row["data_completeness_pct"],
            )

            # Validate score bounds
            if not (0.0 <= result.score <= 1.0):
                logger.warning(
                    f"NEGATIVE SPACE: Score {result.score} outside [0, 1] for profile {result.id}"
                )

            results.append(result)

        logger.info(f"Search completed: {len(results)} results, {total_count} total matches")

        return results, total_count

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise SearchError(f"Search failed: {e}") from e


async def _vector_browse(
    conn: asyncpg.Connection,
    request: SearchRequest,
    where_clause: str,
    filter_params: List[Any],
    embedding_str: str,
) -> tuple[List[ProfileResult], int]:
    """
    Rank the filtered set by vector similarity when the query text has no
    lexical matches (e.g. a residual intent like "candidate" that describes
    every profile and none).

    NEGATIVE SPACE CONTRACT:
    - total_count == size of the filtered set (filters only, no query gate)
    - ordering is ANN (HNSW) — pages beyond hnsw.ef_search degrade by design
    - where_clause references exactly $1..$len(filter_params)
    """
    emb_idx = len(filter_params) + 1
    limit_idx = emb_idx + 1
    offset_idx = emb_idx + 2

    # An HNSW scan returns at most ef_search rows — raise it to cover the
    # requested window, clamped to pgvector's hard maximum of 1000.
    effective_ef_search = min(max(request.ef_search, request.limit + request.offset), 1000)
    await conn.execute(f"SET hnsw.ef_search = {effective_ef_search}")

    query = f"""
        SELECT
            id,
            full_name,
            first_name,
            last_name,
            job_title,
            company_name,
            industry,
            location,
            location_country,
            region,
            locality,
            years_experience,
            skills,
            headline,
            summary,
            linkedin_url,
            linkedin_username,
            email,
            phone,
            website,
            twitter,
            github,
            content_quality_score,
            data_completeness_pct,
            1 - (embedding <=> ${emb_idx}::vector) AS vector_similarity
        FROM profiles
        WHERE {where_clause}
        ORDER BY embedding <=> ${emb_idx}::vector
        LIMIT ${limit_idx} OFFSET ${offset_idx}
    """
    rows = await conn.fetch(query, *filter_params, embedding_str, request.limit, request.offset)

    results = []
    for row in rows:
        # Clamp: cosine similarity can be slightly negative, but ProfileResult
        # enforces scores in [0, 1]
        vector_similarity = max(0.0, min(1.0, float(row["vector_similarity"])))
        results.append(
            ProfileResult(
                id=str(row["id"]),
                full_name=row["full_name"],
                first_name=row["first_name"],
                last_name=row["last_name"],
                job_title=row["job_title"],
                company_name=row["company_name"],
                industry=row["industry"],
                location=row["location"],
                location_country=row["location_country"],
                region=row["region"],
                locality=row["locality"],
                years_experience=row["years_experience"],
                skills=row["skills"],
                headline=row["headline"],
                summary=row["summary"],
                linkedin_url=row["linkedin_url"],
                linkedin_username=row["linkedin_username"],
                email=row["email"],
                phone=row["phone"],
                website=row["website"],
                twitter=row["twitter"],
                github=row["github"],
                score=vector_similarity * request.vector_weight,
                vector_similarity=vector_similarity,
                lexical_rank=0.0,
                content_quality_score=(
                    float(row["content_quality_score"]) if row["content_quality_score"] else None
                ),
                data_completeness_pct=row["data_completeness_pct"],
            )
        )

    count_query = f"SELECT count(*) FROM profiles WHERE {where_clause}"
    total_count = await conn.fetchval(count_query, *filter_params)
    assert total_count is not None, "count(*) always returns a row"

    logger.info(f"Vector browse: {len(results)} results, {total_count} in filtered set")
    return results, total_count


async def keyword_search(
    conn: asyncpg.Connection, request: SearchRequest
) -> tuple[List[ProfileResult], int]:
    """
    Simple keyword search without embeddings (fallback when no embeddings exist).
    Uses full-text search only.
    """
    try:
        # DEBUG: Log all incoming filter parameters
        logger.info(
            f"DEBUG FILTERS: job_title={request.job_title}, company={request.company}, "
            f"has_linkedin={request.has_linkedin}, has_email={request.has_email}, "
            f"has_phone={request.has_phone}, has_website={request.has_website}, "
            f"has_twitter={request.has_twitter}, has_github={request.has_github}"
        )

        # Build WHERE clause for filters
        where_conditions = ["is_deleted = FALSE"]
        params: List[Any] = []
        param_idx = 1

        # Location filters
        if request.location_country:
            where_conditions.append(f"location_country = ${param_idx}")
            params.append(request.location_country)
            param_idx += 1

        # Region filter (support both single and multiple)
        regions_to_filter = []
        if request.regions:
            regions_to_filter = request.regions
        elif request.region:
            regions_to_filter = [request.region]

        if regions_to_filter:
            where_conditions.append(f"region = ANY(${param_idx})")
            params.append(regions_to_filter)
            param_idx += 1

        # Locality filter (support both single and multiple)
        localities_to_filter = []
        if request.localities:
            localities_to_filter = request.localities
        elif request.locality:
            localities_to_filter = [request.locality]

        if localities_to_filter:
            where_conditions.append(f"locality = ANY(${param_idx})")
            params.append(localities_to_filter)
            param_idx += 1

        # Experience filters
        if request.min_years_experience is not None:
            where_conditions.append(f"years_experience >= ${param_idx}")
            params.append(request.min_years_experience)
            param_idx += 1

        if request.max_years_experience is not None:
            where_conditions.append(f"years_experience <= ${param_idx}")
            params.append(request.max_years_experience)
            param_idx += 1

        # Skills filter
        if request.skills:
            where_conditions.append(f"skills @> ${param_idx}")
            params.append(request.skills)
            param_idx += 1

        # Industry filter (support both single and multiple)
        industries_to_filter = []
        if request.industries:
            industries_to_filter = request.industries
        elif request.industry:
            industries_to_filter = [request.industry]

        if industries_to_filter:
            where_conditions.append(f"industry = ANY(${param_idx})")
            params.append(industries_to_filter)
            param_idx += 1

        # Job title filter (partial match, case-insensitive)
        if request.job_title:
            where_conditions.append(f"job_title ILIKE ${param_idx}")
            params.append(f"%{request.job_title}%")
            param_idx += 1

        # Company filter (partial match, case-insensitive)
        if request.company:
            where_conditions.append(f"company_name ILIKE ${param_idx}")
            params.append(f"%{request.company}%")
            param_idx += 1

        # Contact information filters (exclude NULL, empty string, and "-")
        if request.has_linkedin:
            where_conditions.append(
                "linkedin_url IS NOT NULL AND linkedin_url != '' AND linkedin_url != '-'"
            )
        if request.has_email:
            where_conditions.append("email IS NOT NULL AND email != '' AND email != '-'")
        if request.has_phone:
            where_conditions.append("phone IS NOT NULL AND phone != '' AND phone != '-'")
        if request.has_website:
            where_conditions.append("website IS NOT NULL AND website != '' AND website != '-'")
        if request.has_twitter:
            where_conditions.append("twitter IS NOT NULL AND twitter != '' AND twitter != '-'")
        if request.has_github:
            where_conditions.append("github IS NOT NULL AND github != '' AND github != '-'")

        # Quality score filter
        if request.min_quality_score is not None:
            where_conditions.append(f"content_quality_score >= ${param_idx}")
            params.append(request.min_quality_score)
            param_idx += 1

        # Data completeness filter (must mirror hybrid_search — this is its
        # fallback path, and a silently dropped filter over-returns rows)
        if request.min_data_completeness is not None:
            where_conditions.append(f"data_completeness_pct >= ${param_idx}")
            params.append(request.min_data_completeness)
            param_idx += 1

        # Add keyword filter if query provided (use pre-computed search_vector)
        if request.query and request.query.strip():
            where_conditions.append(f"search_vector @@ plainto_tsquery('english', ${param_idx})")
            params.append(request.query)
            param_idx += 1

        where_clause = " AND ".join(where_conditions)

        # DEBUG: Log the WHERE clause
        logger.info(f"DEBUG WHERE CLAUSE: {where_clause}")
        logger.info(f"DEBUG PARAMS: {params}")

        # If query provided, add parameter for ORDER BY ts_rank
        if request.query and request.query.strip():
            tsrank_idx = param_idx
            params.append(request.query)
            param_idx += 1
            order_clause = f"ts_rank(search_vector, plainto_tsquery('english', ${tsrank_idx})) DESC"
        else:
            order_clause = "created_at DESC"

        # Build search query - add limit and offset params
        params.append(request.limit)
        limit_idx = param_idx
        param_idx += 1

        params.append(request.offset)
        offset_idx = param_idx

        query = f"""
            SELECT
                id,
                full_name,
                first_name,
                last_name,
                job_title,
                company_name,
                industry,
                location,
                location_country,
                region,
                locality,
                years_experience,
                skills,
                headline,
                summary,
                linkedin_url,
                linkedin_username,
                email,
                phone,
                website,
                twitter,
                github,
                content_quality_score,
                data_completeness_pct
            FROM profiles
            WHERE {where_clause}
            ORDER BY {order_clause}
            LIMIT ${limit_idx} OFFSET ${offset_idx}
        """

        rows = await conn.fetch(query, *params)

        # Convert to ProfileResult objects
        results = []
        for row in rows:
            result = ProfileResult(
                id=str(row["id"]),
                full_name=row["full_name"],
                first_name=row["first_name"],
                last_name=row["last_name"],
                job_title=row["job_title"],
                company_name=row["company_name"],
                industry=row["industry"],
                location=row["location"],
                location_country=row["location_country"],
                region=row["region"],
                locality=row["locality"],
                years_experience=row["years_experience"],
                skills=row["skills"],
                headline=row["headline"],
                summary=row["summary"],
                linkedin_url=row["linkedin_url"],
                linkedin_username=row["linkedin_username"],
                email=row["email"],
                phone=row["phone"],
                website=row["website"],
                twitter=row["twitter"],
                github=row["github"],
                score=0.5,  # Placeholder score for keyword search
                vector_similarity=0.0,
                lexical_rank=0.5,
                content_quality_score=(
                    float(row["content_quality_score"]) if row["content_quality_score"] else None
                ),
                data_completeness_pct=row.get("data_completeness_pct", None),
            )
            results.append(result)

        # Get total count
        count_query = f"""
            SELECT count(*) FROM profiles
            WHERE {where_clause}
        """
        # Remove limit, offset, and potentially ts_rank params for count
        # Count params are all params except the last 2 (limit, offset) and potentially one more (ts_rank)
        if request.query and request.query.strip():
            count_params = params[:-3]  # Remove ts_rank, limit, offset
        else:
            count_params = params[:-2]  # Remove limit, offset only
        total_count = await conn.fetchval(count_query, *count_params)
        assert total_count is not None, "count(*) always returns a row"

        logger.info(
            f"Keyword search completed: {len(results)} results, {total_count} total matches"
        )

        return results, total_count

    except Exception as e:
        logger.error(f"Keyword search error: {e}", exc_info=True)
        raise SearchError(f"Keyword search failed: {e}") from e
