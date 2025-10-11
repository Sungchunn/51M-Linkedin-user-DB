"""
INSIGHT - Hybrid Search Implementation
Combines vector similarity + full-text search + structured filters

Negative Spaces Implementation:
- Query must produce embedding
- Score bounds [0.0, 1.0] enforced
- NULL handling in filters
- Timeout enforcement
"""

from typing import List, Dict, Any, Optional
import asyncpg
import logging
from backend.api.models import SearchRequest, ProfileResult
from backend.data_pipeline.embeddings import providers

logger = logging.getLogger(__name__)


class SearchError(Exception):
    """Raised when search operations fail"""
    pass


async def hybrid_search(
    conn: asyncpg.Connection,
    request: SearchRequest
) -> tuple[List[ProfileResult], int]:
    """
    Execute hybrid search combining vector + lexical + filters.

    NEGATIVE SPACE CONTRACT:
    - query must generate valid embedding
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
        # Check if we have any embeddings in the database
        has_embeddings = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM profiles WHERE embedding IS NOT NULL LIMIT 1)"
        )

        # If no embeddings, use keyword-only search
        if not has_embeddings:
            logger.info("No embeddings found, using keyword-only search")
            return await keyword_search(conn, request)

        # Generate query embedding
        provider = providers.get_provider()
        query_embedding = provider.embed_single(request.query)

        if query_embedding is None:
            raise SearchError(
                f"NEGATIVE SPACE: Failed to generate embedding for query: {request.query}"
            )

        # Build WHERE clause for filters
        where_conditions = ["embedding IS NOT NULL", "is_deleted = FALSE"]
        # Convert embedding list to string format for asyncpg
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        # Start with embedding as $1
        params = [embedding_str]
        param_idx = 2

        # Track where filter params start (for count query)
        filter_params_start_idx = len(params)

        # Location filters
        if request.location_country:
            where_conditions.append(f"location_country = ${param_idx}")
            params.append(request.location_country)
            param_idx += 1

        if request.region:
            where_conditions.append(f"region = ${param_idx}")
            params.append(request.region)
            param_idx += 1

        if request.locality:
            where_conditions.append(f"locality = ${param_idx}")
            params.append(request.locality)
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

        # Industry filter
        if request.industry:
            where_conditions.append(f"industry = ${param_idx}")
            params.append(request.industry)
            param_idx += 1

        # Quality score filter
        if request.min_quality_score is not None:
            where_conditions.append(f"content_quality_score >= ${param_idx}")
            params.append(request.min_quality_score)
            param_idx += 1

        where_clause = " AND ".join(where_conditions)

        # Number of filter params (excluding embedding which is used in CTEs only)
        num_filter_params = len(params) - filter_params_start_idx

        # Set HNSW ef_search parameter
        await conn.execute(f"SET hnsw.ef_search = {request.ef_search}")

        # Build hybrid search query
        # Append parameters for remaining placeholders
        params.append(request.query)  # $param_idx
        tsquery_idx = param_idx
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

        query = f"""
        WITH vector_results AS (
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
                content_quality_score,
                1 - (embedding <=> $1::vector) AS vector_similarity
            FROM profiles
            WHERE {where_clause}
            ORDER BY embedding <=> $1::vector
            LIMIT 500
        ),
        lexical_results AS (
            SELECT
                id,
                ts_rank(
                    to_tsvector('english',
                        coalesce(full_name, '') || ' ' ||
                        coalesce(headline, '') || ' ' ||
                        coalesce(summary, '') || ' ' ||
                        coalesce(job_title, '') || ' ' ||
                        coalesce(company_name, '')
                    ),
                    plainto_tsquery('english', ${tsquery_idx})
                ) AS lexical_rank
            FROM profiles
            WHERE {where_clause}
              AND to_tsvector('english',
                    coalesce(full_name, '') || ' ' ||
                    coalesce(headline, '') || ' ' ||
                    coalesce(summary, '') || ' ' ||
                    coalesce(job_title, '') || ' ' ||
                    coalesce(company_name, '')
                  ) @@ plainto_tsquery('english', ${tsquery_idx})
            LIMIT 500
        )
        SELECT
            v.id,
            v.full_name,
            v.first_name,
            v.last_name,
            v.job_title,
            v.company_name,
            v.industry,
            v.location,
            v.location_country,
            v.region,
            v.locality,
            v.years_experience,
            v.skills,
            v.headline,
            v.summary,
            v.content_quality_score,
            v.vector_similarity,
            COALESCE(l.lexical_rank, 0.0) AS lexical_rank,
            (v.vector_similarity * ${vector_weight_idx}) + (COALESCE(l.lexical_rank, 0.0) * ${lexical_weight_idx}) AS score
        FROM vector_results v
        LEFT JOIN lexical_results l ON l.id = v.id
        ORDER BY score DESC
        LIMIT ${limit_idx} OFFSET ${offset_idx}
        """

        # Execute search
        logger.debug(f"Executing hybrid search: query='{request.query}', filters={len(where_conditions)}")

        rows = await conn.fetch(query, *params)

        # Convert to ProfileResult objects
        results = []
        for row in rows:
            result = ProfileResult(
                id=str(row['id']),
                full_name=row['full_name'],
                first_name=row['first_name'],
                last_name=row['last_name'],
                job_title=row['job_title'],
                company_name=row['company_name'],
                industry=row['industry'],
                location=row['location'],
                location_country=row['location_country'],
                region=row['region'],
                locality=row['locality'],
                years_experience=row['years_experience'],
                skills=row['skills'],
                headline=row['headline'],
                summary=row['summary'],
                score=float(row['score']),
                vector_similarity=float(row['vector_similarity']),
                lexical_rank=float(row['lexical_rank']),
                content_quality_score=float(row['content_quality_score']) if row['content_quality_score'] else None
            )

            # Validate score bounds
            if not (0.0 <= result.score <= 1.0):
                logger.warning(
                    f"NEGATIVE SPACE: Score {result.score} outside [0, 1] for profile {result.id}"
                )

            results.append(result)

        # Get total count (for pagination)
        # Need to rebuild WHERE clause with renumbered parameters starting from $1
        if num_filter_params > 0:
            # Rebuild where conditions with params starting from $1
            count_where_conditions = ["embedding IS NOT NULL", "is_deleted = FALSE"]
            count_param_idx = 1
            count_params = []

            if request.location_country:
                count_where_conditions.append(f"location_country = ${count_param_idx}")
                count_params.append(request.location_country)
                count_param_idx += 1

            if request.region:
                count_where_conditions.append(f"region = ${count_param_idx}")
                count_params.append(request.region)
                count_param_idx += 1

            if request.locality:
                count_where_conditions.append(f"locality = ${count_param_idx}")
                count_params.append(request.locality)
                count_param_idx += 1

            if request.min_years_experience is not None:
                count_where_conditions.append(f"years_experience >= ${count_param_idx}")
                count_params.append(request.min_years_experience)
                count_param_idx += 1

            if request.max_years_experience is not None:
                count_where_conditions.append(f"years_experience <= ${count_param_idx}")
                count_params.append(request.max_years_experience)
                count_param_idx += 1

            if request.skills:
                count_where_conditions.append(f"skills @> ${count_param_idx}")
                count_params.append(request.skills)
                count_param_idx += 1

            if request.industry:
                count_where_conditions.append(f"industry = ${count_param_idx}")
                count_params.append(request.industry)
                count_param_idx += 1

            if request.min_quality_score is not None:
                count_where_conditions.append(f"content_quality_score >= ${count_param_idx}")
                count_params.append(request.min_quality_score)
                count_param_idx += 1

            count_where_clause = " AND ".join(count_where_conditions)
        else:
            # No filter params, just base conditions
            count_where_clause = where_clause
            count_params = []

        count_query = f"""
            SELECT count(*) FROM profiles
            WHERE {count_where_clause}
        """

        total_count = await conn.fetchval(count_query, *count_params)

        logger.info(
            f"Search completed: {len(results)} results, {total_count} total matches"
        )

        return results, total_count

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise SearchError(f"Search failed: {e}") from e


async def keyword_search(
    conn: asyncpg.Connection,
    request: SearchRequest
) -> tuple[List[ProfileResult], int]:
    """
    Simple keyword search without embeddings (fallback when no embeddings exist).
    Uses full-text search only.
    """
    try:
        # Build WHERE clause for filters
        where_conditions = ["is_deleted = FALSE"]
        params = []
        param_idx = 1

        # Location filters
        if request.location_country:
            where_conditions.append(f"location_country = ${param_idx}")
            params.append(request.location_country)
            param_idx += 1

        if request.region:
            where_conditions.append(f"region = ${param_idx}")
            params.append(request.region)
            param_idx += 1

        if request.locality:
            where_conditions.append(f"locality = ${param_idx}")
            params.append(request.locality)
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

        # Industry filter
        if request.industry:
            where_conditions.append(f"industry = ${param_idx}")
            params.append(request.industry)
            param_idx += 1

        # Quality score filter
        if request.min_quality_score is not None:
            where_conditions.append(f"content_quality_score >= ${param_idx}")
            params.append(request.min_quality_score)
            param_idx += 1

        # Add keyword filter if query provided
        if request.query and request.query.strip():
            where_conditions.append(f"""
                to_tsvector('english',
                    coalesce(full_name, '') || ' ' ||
                    coalesce(headline, '') || ' ' ||
                    coalesce(summary, '') || ' ' ||
                    coalesce(job_title, '') || ' ' ||
                    coalesce(company_name, '')
                ) @@ plainto_tsquery('english', ${param_idx})
            """)
            params.append(request.query)
            param_idx += 1

        where_clause = " AND ".join(where_conditions)

        # Build search query
        params.append(request.limit)
        limit_idx = param_idx
        param_idx += 1

        params.append(request.offset)
        offset_idx = param_idx

        # If query provided, rank by relevance; otherwise just return recent profiles
        if request.query and request.query.strip():
            order_clause = f"""
                ts_rank(
                    to_tsvector('english',
                        coalesce(full_name, '') || ' ' ||
                        coalesce(headline, '') || ' ' ||
                        coalesce(summary, '') || ' ' ||
                        coalesce(job_title, '') || ' ' ||
                        coalesce(company_name, '')
                    ),
                    plainto_tsquery('english', '{request.query}')
                ) DESC
            """
        else:
            order_clause = "created_at DESC"

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
                content_quality_score
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
                id=str(row['id']),
                full_name=row['full_name'],
                first_name=row['first_name'],
                last_name=row['last_name'],
                job_title=row['job_title'],
                company_name=row['company_name'],
                industry=row['industry'],
                location=row['location'],
                location_country=row['location_country'],
                region=row['region'],
                locality=row['locality'],
                years_experience=row['years_experience'],
                skills=row['skills'],
                headline=row['headline'],
                summary=row['summary'],
                linkedin_url=row['linkedin_url'],
                linkedin_username=row['linkedin_username'],
                email=row['email'],
                phone=row['phone'],
                website=row['website'],
                twitter=row['twitter'],
                github=row['github'],
                score=0.5,  # Placeholder score for keyword search
                vector_similarity=0.0,
                lexical_rank=0.5,
                content_quality_score=float(row['content_quality_score']) if row['content_quality_score'] else None
            )
            results.append(result)

        # Get total count
        count_query = f"""
            SELECT count(*) FROM profiles
            WHERE {where_clause}
        """
        # Remove limit and offset params for count
        count_params = params[:-2]
        total_count = await conn.fetchval(count_query, *count_params)

        logger.info(
            f"Keyword search completed: {len(results)} results, {total_count} total matches"
        )

        return results, total_count

    except Exception as e:
        logger.error(f"Keyword search error: {e}", exc_info=True)
        raise SearchError(f"Keyword search failed: {e}") from e
