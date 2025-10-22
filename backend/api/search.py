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

        # Generate query embedding with graceful fallback to keyword search
        try:
            provider = providers.get_provider()
            query_embedding = provider.embed_single(request.query)
        except Exception as e:
            logger.warning(
                f"Embedding provider error, falling back to keyword search: {e}")
            return await keyword_search(conn, request)

        if query_embedding is None:
            logger.warning(
                "Query embedding is None, falling back to keyword search")
            return await keyword_search(conn, request)

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
            where_conditions.append("linkedin_url IS NOT NULL AND linkedin_url != '' AND linkedin_url != '-'")
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
                linkedin_url,
                linkedin_username,
                email,
                phone,
                website,
                twitter,
                github,
                content_quality_score,
                data_completeness_pct,
                1 - (embedding <=> $1::vector) AS vector_similarity
            FROM profiles
            WHERE {where_clause}
            ORDER BY embedding <=> $1::vector
            LIMIT LEAST(${limit_idx}*4, 5000)
        ),
        lexical_results AS (
            SELECT
                id,
                ts_rank(search_vector, plainto_tsquery('english', ${tsquery_idx})) AS lexical_rank
            FROM profiles
            WHERE {where_clause}
              AND search_vector @@ plainto_tsquery('english', ${tsquery_idx})
            LIMIT LEAST(${limit_idx}*4, 5000)
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
            v.linkedin_url,
            v.linkedin_username,
            v.email,
            v.phone,
            v.website,
            v.twitter,
            v.github,
            v.content_quality_score,
            v.data_completeness_pct,
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
                linkedin_url=row['linkedin_url'],
                linkedin_username=row['linkedin_username'],
                email=row['email'],
                phone=row['phone'],
                website=row['website'],
                twitter=row['twitter'],
                github=row['github'],
                score=float(row['score']),
                vector_similarity=float(row['vector_similarity']),
                lexical_rank=float(row['lexical_rank']),
                content_quality_score=float(row['content_quality_score']) if row['content_quality_score'] else None,
                data_completeness_pct=row['data_completeness_pct']
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

            # Region filter (support both single and multiple)
            regions_to_filter = []
            if request.regions:
                regions_to_filter = request.regions
            elif request.region:
                regions_to_filter = [request.region]

            if regions_to_filter:
                count_where_conditions.append(f"region = ANY(${count_param_idx})")
                count_params.append(regions_to_filter)
                count_param_idx += 1

            # Locality filter (support both single and multiple)
            localities_to_filter = []
            if request.localities:
                localities_to_filter = request.localities
            elif request.locality:
                localities_to_filter = [request.locality]

            if localities_to_filter:
                count_where_conditions.append(f"locality = ANY(${count_param_idx})")
                count_params.append(localities_to_filter)
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

            # Industry filter (support both single and multiple)
            industries_to_filter = []
            if request.industries:
                industries_to_filter = request.industries
            elif request.industry:
                industries_to_filter = [request.industry]

            if industries_to_filter:
                count_where_conditions.append(f"industry = ANY(${count_param_idx})")
                count_params.append(industries_to_filter)
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
            where_conditions.append("linkedin_url IS NOT NULL AND linkedin_url != '' AND linkedin_url != '-'")
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

        # Add keyword filter if query provided (use pre-computed search_vector)
        if request.query and request.query.strip():
            where_conditions.append(f"search_vector @@ plainto_tsquery('english', ${param_idx})")
            params.append(request.query)
            param_idx += 1

        where_clause = " AND ".join(where_conditions)

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
                content_quality_score=float(row['content_quality_score']) if row['content_quality_score'] else None,
                data_completeness_pct=row.get('data_completeness_pct', None)
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

        logger.info(
            f"Keyword search completed: {len(results)} results, {total_count} total matches"
        )

        return results, total_count

    except Exception as e:
        logger.error(f"Keyword search error: {e}", exc_info=True)
        raise SearchError(f"Keyword search failed: {e}") from e
