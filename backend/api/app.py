"""
INSIGHT - FastAPI Search API
Main application with endpoints for semantic talent search

Negative Spaces Implementation:
- Lifespan management for connection pool
- Request validation via Pydantic
- Error handling with proper status codes
- CORS configuration
"""

from fastapi import FastAPI, HTTPException, status, Query, Response, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import json
import base64
import io
import csv
from contextlib import asynccontextmanager
import logging
from datetime import datetime
from typing import Optional
import time

from backend.api.models import (
    SearchRequest,
    SearchResponse,
    HealthResponse,
    ErrorResponse
)
from backend.api import database, search
from backend.api.auth import resolve_auth_context, AuthContext
from backend.api.rate_limit import limiter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    NEGATIVE SPACE CONTRACT:
    - Creates pool on startup
    - Closes pool on shutdown
    - Ensures no connection leaks
    """
    logger.info("🚀 Starting INSIGHT API...")

    # Startup: Create connection pool
    try:
        await database.get_pool()
        logger.info("✅ Database connection pool initialized")
    except database.DatabaseError as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        raise

    # Create admin user if not exists
    try:
        from backend.api.user_manager import UserManager
        await UserManager.create_admin_if_not_exists()
    except Exception as e:
        logger.error(f"⚠️  Failed to create admin user: {e}")

    yield

    # Shutdown: Close connection pool
    logger.info("🛑 Shutting down INSIGHT API...")
    await database.close_pool()
    logger.info("✅ Database connection pool closed")


# Create FastAPI app
app = FastAPI(
    title="INSIGHT - Semantic Talent Finder",
    description="Hybrid search API for LinkedIn profiles using vector embeddings and full-text search",
    version="1.0.0",
    lifespan=lifespan
)


# Add CORS middleware
import os
allowed_origins_env = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5500,http://127.0.0.1:5500"
)
dev_relax_cors = os.getenv("DEV_RELAX_CORS", "false").lower() == "true"
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
allow_origin_regex = os.getenv(
    "CORS_ORIGIN_REGEX",
    r"https?://(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\\d+)?$"
)
# For local dev and to match previously working behavior, default to wide-open CORS.
# You can tighten by setting CORS_ORIGINS explicitly in .env.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include authentication router
from backend.api.auth_routes import router as auth_router
app.include_router(auth_router)

# Explicit preflight handlers to satisfy strict browsers and proxies
@app.options("/search")
async def options_search():
    return Response(status_code=204)

@app.options("/export/ndjson")
async def options_export_ndjson():
    return Response(status_code=204)

@app.options("/export/csv")
async def options_export_csv():
    return Response(status_code=204)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "name": "INSIGHT - Semantic Talent Finder",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }

# Page token helpers
def _encode_token(payload: dict) -> str:
    data = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
    return base64.urlsafe_b64encode(data).decode("ascii")


def _decode_token(token: str) -> dict:
    try:
        data = base64.urlsafe_b64decode(token.encode("ascii"))
        return json.loads(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid page_token: {e}")


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["Health"],
    summary="Health check endpoint"
)
async def health_check():
    """
    Check API and database health.

    NEGATIVE SPACE CONTRACT:
    - Returns 200 if healthy
    - Returns 503 if database unavailable
    """
    try:
        pool = await database.get_pool()

        async with pool.acquire() as conn:
            # Test database connectivity
            await conn.fetchval("SELECT 1")

            # Get profile counts
            total_profiles = await conn.fetchval(
                "SELECT count(*) FROM profiles WHERE is_deleted = FALSE"
            )

            profiles_with_embeddings = await conn.fetchval(
                "SELECT count(*) FROM profiles WHERE embedding IS NOT NULL AND is_deleted = FALSE"
            )

        return HealthResponse(
            status="healthy",
            timestamp=datetime.utcnow(),
            database="connected",
            profiles_total=total_profiles,
            profiles_with_embeddings=profiles_with_embeddings
        )

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unavailable: {e}"
        )


@app.get(
    "/countries",
    tags=["Filters"],
    summary="Get list of countries"
)
async def get_countries(response: Response):
    """Get distinct countries from profiles"""
    try:
        # No rate limit on filters to avoid UX issues
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            countries = await conn.fetch("""
                SELECT DISTINCT location_country
                FROM profiles
                WHERE location_country IS NOT NULL
                  AND is_deleted = FALSE
                ORDER BY location_country
            """)
            response.headers["Cache-Control"] = "public, max-age=600"
            return {"countries": [row['location_country'] for row in countries]}
    except Exception as e:
        logger.error(f"Failed to fetch countries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/industries",
    tags=["Filters"],
    summary="Get list of industries"
)
async def get_industries(response: Response):
    """Get distinct industries from profiles"""
    try:
        # No rate limit on filters to avoid UX issues
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            industries = await conn.fetch("""
                SELECT DISTINCT industry
                FROM profiles
                WHERE industry IS NOT NULL
                  AND is_deleted = FALSE
                ORDER BY industry
            """)
            response.headers["Cache-Control"] = "public, max-age=600"
            return {"industries": [row['industry'] for row in industries]}
    except Exception as e:
        logger.error(f"Failed to fetch industries: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/regions",
    tags=["Filters"],
    summary="Get list of regions/states"
)
async def get_regions(response: Response, country: Optional[str] = None):
    """Get distinct regions/states from profiles, optionally filtered by country"""
    try:
        # No rate limit on filters to avoid UX issues
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            if country:
                regions = await conn.fetch("""
                    SELECT DISTINCT region, COUNT(*) as count
                    FROM profiles
                    WHERE region IS NOT NULL
                      AND location_country = $1
                      AND is_deleted = FALSE
                    GROUP BY region
                    ORDER BY count DESC, region
                    LIMIT 100
                """, country)
            else:
                regions = await conn.fetch("""
                    SELECT DISTINCT region, COUNT(*) as count
                    FROM profiles
                    WHERE region IS NOT NULL
                      AND is_deleted = FALSE
                    GROUP BY region
                    ORDER BY count DESC, region
                    LIMIT 100
                """)
            response.headers["Cache-Control"] = "public, max-age=600"
            return {"regions": [{"region": row['region'], "count": row['count']} for row in regions]}
    except Exception as e:
        logger.error(f"Failed to fetch regions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/localities",
    tags=["Filters"],
    summary="Get list of cities"
)
async def get_localities(response: Response, country: Optional[str] = None, region: Optional[str] = None):
    """Get distinct localities/cities from profiles, optionally filtered by country and region"""
    try:
        # No rate limit on filters to avoid UX issues
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            if country and region:
                localities = await conn.fetch("""
                    SELECT DISTINCT locality, COUNT(*) as count
                    FROM profiles
                    WHERE locality IS NOT NULL
                      AND location_country = $1
                      AND region = $2
                      AND is_deleted = FALSE
                    GROUP BY locality
                    ORDER BY count DESC, locality
                    LIMIT 100
                """, country, region)
            elif country:
                localities = await conn.fetch("""
                    SELECT DISTINCT locality, COUNT(*) as count
                    FROM profiles
                    WHERE locality IS NOT NULL
                      AND location_country = $1
                      AND is_deleted = FALSE
                    GROUP BY locality
                    ORDER BY count DESC, locality
                    LIMIT 100
                """, country)
            else:
                localities = await conn.fetch("""
                    SELECT DISTINCT locality, COUNT(*) as count
                    FROM profiles
                    WHERE locality IS NOT NULL
                      AND is_deleted = FALSE
                    GROUP BY locality
                    ORDER BY count DESC, locality
                    LIMIT 100
                """)
            response.headers["Cache-Control"] = "public, max-age=600"
            return {"localities": [{"locality": row['locality'], "count": row['count']} for row in localities]}
    except Exception as e:
        logger.error(f"Failed to fetch localities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/stats",
    tags=["Statistics"],
    summary="Get dataset statistics"
)
async def get_stats(response: Response, request: Request):
    """Get dataset statistics"""
    try:
        # Stats endpoint has light rate limiting but no auth required
        x_api_key = request.headers.get("x-api-key")
        ctx: AuthContext = await resolve_auth_context(x_api_key)
        if not limiter.allow(f"stats:{ctx.api_key or request.client.host}", 30, 60):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            # Total profiles
            total = await conn.fetchval("""
                SELECT COUNT(*) FROM profiles WHERE is_deleted = FALSE
            """)

            # Top countries
            countries = await conn.fetch("""
                SELECT location_country as country, COUNT(*) as count
                FROM profiles
                WHERE location_country IS NOT NULL AND is_deleted = FALSE
                GROUP BY location_country
                ORDER BY count DESC
                LIMIT 20
            """)

            # Top industries
            industries = await conn.fetch("""
                SELECT industry, COUNT(*) as count
                FROM profiles
                WHERE industry IS NOT NULL AND is_deleted = FALSE
                GROUP BY industry
                ORDER BY count DESC
                LIMIT 20
            """)

            response.headers["Cache-Control"] = "public, max-age=60"
            return {
                "total_profiles": total,
                "countries": [{"country": row['country'], "count": row['count']} for row in countries],
                "industries": [{"industry": row['industry'], "count": row['count']} for row in industries]
            }
    except Exception as e:
        logger.error(f"Failed to fetch stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/search",
    response_model=SearchResponse,
    tags=["Search"],
    summary="Semantic search for talent profiles"
)
async def search_profiles(request: SearchRequest, http_request: Request, x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """
    Execute hybrid semantic search on talent profiles.

    Combines:
    - Vector similarity search (HNSW index)
    - Full-text lexical search (ts_rank)
    - Structured filters (location, skills, experience)

    NEGATIVE SPACE CONTRACT:
    - Returns SearchResponse with results
    - Returns 400 for invalid requests
    - Returns 500 for search failures

    Args:
        request: SearchRequest with query and filters

    Returns:
        SearchResponse with results and metadata
    """
    start_time = time.time()

    try:
        ctx: AuthContext = await resolve_auth_context(x_api_key)
        # Effective limits
        if request.limit > ctx.max_limit:
            request.limit = ctx.max_limit
        if request.offset > ctx.max_offset:
            raise HTTPException(status_code=422, detail=f"Offset exceeds maximum {ctx.max_offset}")

        # Rate limit per API key/IP
        rl_key = f"search:{ctx.api_key or http_request.client.host}"
        if not limiter.allow(rl_key, int(os.getenv("RATE_LIMIT_SEARCH_PER_MIN", "60")), int(os.getenv("RATE_LIMIT_SEARCH_BURST", "120"))):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")

        # If a page_token is provided, reconstruct request from token (server-side snapshot)
        if request.page_token:
            snapshot = _decode_token(request.page_token)
            # Rehydrate request fields from snapshot
            for k, v in snapshot.items():
                if hasattr(request, k):
                    setattr(request, k, v)

        pool = await database.get_pool()

        async with pool.acquire() as conn:
            # Execute hybrid search
            results, total_count = await search.hybrid_search(conn, request)

        # Calculate query time
        query_time_ms = (time.time() - start_time) * 1000

        # Build filters dict for response
        filters_applied = {}
        if request.location_country:
            filters_applied['location_country'] = request.location_country
        if request.regions:
            filters_applied['regions'] = request.regions
        elif request.region:
            filters_applied['region'] = request.region
        if request.localities:
            filters_applied['localities'] = request.localities
        elif request.locality:
            filters_applied['locality'] = request.locality
        if request.min_years_experience is not None:
            filters_applied['min_years_experience'] = request.min_years_experience
        if request.max_years_experience is not None:
            filters_applied['max_years_experience'] = request.max_years_experience
        if request.skills:
            filters_applied['skills'] = request.skills
        if request.industry:
            filters_applied['industry'] = request.industry
        if request.min_quality_score is not None:
            filters_applied['min_quality_score'] = request.min_quality_score

        logger.info(
            f"Search completed: query='{request.query}', "
            f"results={len(results)}/{total_count}, "
            f"time={query_time_ms:.1f}ms"
        )

        # Compute next page token if more results remain
        next_token = None
        if request.offset + request.limit < total_count:
            snapshot = request.dict()
            snapshot.pop('page_token', None)
            snapshot['offset'] = request.offset + request.limit
            next_token = _encode_token(snapshot)

        # PII redaction unless authorized
        # TEMPORARY: Disabled for testing - ENABLE IN PRODUCTION!
        # if not ctx.allow_pii:
        #     for r in results:
        #         r.email = None
        #         r.phone = None

        return SearchResponse(
            results=results,
            total_count=total_count,
            returned_count=len(results),
            offset=request.offset,
            limit=request.limit,
            query_time_ms=query_time_ms,
            query=request.query,
            filters_applied=filters_applied,
            next_page_token=next_token
        )

    except search.SearchError as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {e}"
        )

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {e}"
        )


@app.get(
    "/search",
    response_model=SearchResponse,
    tags=["Search"],
    summary="Semantic search (GET with query params)"
)
async def search_profiles_get(
    request: Request,
    q: str = Query("", description="Search query text (empty for browse mode)"),
    limit: int = Query(20, ge=1, le=1000, description="Number of results to return (max 1000)"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    page_token: str | None = Query(None, description="Opaque token to fetch the next page (overrides other params)"),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    location_country: str | None = Query(None, description="Filter by country"),
    region: str | None = Query(None, description="Filter by region/state (deprecated - use regions)"),
    regions: list[str] | None = Query(None, description="Filter by multiple regions/states (OR logic)"),
    locality: str | None = Query(None, description="Filter by city (deprecated - use localities)"),
    localities: list[str] | None = Query(None, description="Filter by multiple cities (OR logic)"),
    min_years_experience: int | None = Query(None, ge=0, le=80, description="Minimum years of experience"),
    max_years_experience: int | None = Query(None, ge=0, le=80, description="Maximum years of experience"),
    skills: list[str] | None = Query(None, description="Required skills (AND logic)"),
    industry: str | None = Query(None, description="Filter by single industry (deprecated - use industries)"),
    industries: list[str] | None = Query(None, description="Filter by multiple industries (OR logic)"),
    job_title: str | None = Query(None, description="Filter by job title (partial match)"),
    company: str | None = Query(None, description="Filter by company name (partial match)"),
    has_linkedin: bool | None = Query(None, description="Filter profiles with LinkedIn URL"),
    has_email: bool | None = Query(None, description="Filter profiles with email"),
    has_phone: bool | None = Query(None, description="Filter profiles with phone"),
    has_website: bool | None = Query(None, description="Filter profiles with website"),
    has_twitter: bool | None = Query(None, description="Filter profiles with Twitter"),
    has_github: bool | None = Query(None, description="Filter profiles with GitHub"),
    min_quality_score: float | None = Query(None, ge=0.0, le=1.0, description="Minimum quality score"),
    min_data_completeness: int | None = Query(None, ge=0, le=100, description="Minimum data completeness percentage"),
    vector_weight: float = Query(0.8, ge=0.0, le=1.0, description="Weight for vector similarity"),
    lexical_weight: float = Query(0.2, ge=0.0, le=1.0, description="Weight for lexical matching"),
    ef_search: int = Query(64, ge=10, le=400, description="HNSW ef_search parameter (quality vs speed)")
):
    """
    GET version of search to support simple HTTP request nodes.

    Use repeated query params for lists, e.g. `regions=CA&regions=NY`.
    """
    req = SearchRequest(
        query=q,
        limit=limit,
        offset=offset,
        page_token=page_token,
        location_country=location_country,
        region=region,
        regions=regions,
        locality=locality,
        localities=localities,
        min_years_experience=min_years_experience,
        max_years_experience=max_years_experience,
        skills=skills,
        industry=industry,
        industries=industries,
        job_title=job_title,
        company=company,
        has_linkedin=has_linkedin,
        has_email=has_email,
        has_phone=has_phone,
        has_website=has_website,
        has_twitter=has_twitter,
        has_github=has_github,
        min_quality_score=min_quality_score,
        min_data_completeness=min_data_completeness,
        vector_weight=vector_weight,
        lexical_weight=lexical_weight,
        ef_search=ef_search,
    )
    return await search_profiles(req, http_request=request, x_api_key=x_api_key)


@app.get(
    "/export/ndjson",
    tags=["Export"],
    summary="Export search results as NDJSON (up to 1000 per call)"
)
async def export_ndjson(
    request: Request,
    q: str = Query("", description="Search query text (empty for browse mode)"),
    limit: int = Query(1000, ge=1, le=1000, description="Number of results to return (max 1000)"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    location_country: str | None = Query(None),
    regions: list[str] | None = Query(None),
    localities: list[str] | None = Query(None),
    min_years_experience: int | None = Query(None, ge=0, le=80),
    max_years_experience: int | None = Query(None, ge=0, le=80),
    skills: list[str] | None = Query(None),
    industries: list[str] | None = Query(None),
    min_quality_score: float | None = Query(None, ge=0.0, le=1.0),
    min_data_completeness: int | None = Query(None, ge=0, le=100),
    vector_weight: float = Query(0.8, ge=0.0, le=1.0),
    lexical_weight: float = Query(0.2, ge=0.0, le=1.0),
    ef_search: int = Query(64, ge=10, le=400),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """Stream results as NDJSON for easy bulk ingestion."""

    req = SearchRequest(
        query=q,
        limit=limit,
        offset=offset,
        location_country=location_country,
        regions=regions,
        localities=localities,
        min_years_experience=min_years_experience,
        max_years_experience=max_years_experience,
        skills=skills,
        industries=industries,
        min_quality_score=min_quality_score,
        min_data_completeness=min_data_completeness,
        vector_weight=vector_weight,
        lexical_weight=lexical_weight,
        ef_search=ef_search,
    )

    async def iter_lines():
        ctx: AuthContext = await resolve_auth_context(x_api_key)
        require_key = os.getenv("EXPORT_REQUIRE_API_KEY", "false").lower() == "true"
        if require_key and not ctx.allow_export:
            raise HTTPException(status_code=403, detail="Export not permitted without 'export:read' scope")
        # Rate limit exports
        if not limiter.allow(f"export:{ctx.api_key or request.client.host}", int(os.getenv("RATE_LIMIT_EXPORT_PER_MIN", "6")), int(os.getenv("RATE_LIMIT_EXPORT_BURST", "10"))):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        # Require filters and query to mitigate bulk dumps
        export_require_filter = os.getenv("EXPORT_REQUIRE_FILTER", "true").lower() == "true"
        has_any_filter = bool(location_country or (regions and len(regions) > 0) or (localities and len(localities) > 0))
        if (q.strip() == "") and (export_require_filter and not has_any_filter):
            raise HTTPException(status_code=422, detail="Export requires query or at least one filter")

        pool = await database.get_pool()
        async with pool.acquire() as conn:
            results, _ = await search.hybrid_search(conn, req)
            for r in results:
                # TEMPORARY: Disabled for testing - ENABLE IN PRODUCTION!
                # if not ctx.allow_pii:
                #     r.email = None
                #     r.phone = None
                yield json.dumps(r.dict(), default=str) + "\n"

    headers = {"Content-Type": "application/x-ndjson"}
    return StreamingResponse(iter_lines(), headers=headers, media_type="application/x-ndjson")


@app.get(
    "/export/csv",
    tags=["Export"],
    summary="Export search results as CSV (up to 1000 per call)"
)
async def export_csv(
    request: Request,
    q: str = Query("", description="Search query text (empty for browse mode)"),
    limit: int = Query(1000, ge=1, le=1000, description="Number of results to return (max 1000)"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    location_country: str | None = Query(None),
    regions: list[str] | None = Query(None),
    localities: list[str] | None = Query(None),
    min_years_experience: int | None = Query(None, ge=0, le=80),
    max_years_experience: int | None = Query(None, ge=0, le=80),
    skills: list[str] | None = Query(None),
    industries: list[str] | None = Query(None),
    min_quality_score: float | None = Query(None, ge=0.0, le=1.0),
    min_data_completeness: int | None = Query(None, ge=0, le=100),
    vector_weight: float = Query(0.8, ge=0.0, le=1.0),
    lexical_weight: float = Query(0.2, ge=0.0, le=1.0),
    ef_search: int = Query(64, ge=10, le=400),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    req = SearchRequest(
        query=q,
        limit=limit,
        offset=offset,
        location_country=location_country,
        regions=regions,
        localities=localities,
        min_years_experience=min_years_experience,
        max_years_experience=max_years_experience,
        skills=skills,
        industries=industries,
        min_quality_score=min_quality_score,
        min_data_completeness=min_data_completeness,
        vector_weight=vector_weight,
        lexical_weight=lexical_weight,
        ef_search=ef_search,
    )

    headers = {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": "attachment; filename=insight_export.csv",
    }

    fieldnames = [
        "id",
        "full_name",
        "first_name",
        "last_name",
        "job_title",
        "company_name",
        "industry",
        "location",
        "location_country",
        "region",
        "locality",
        "years_experience",
        "skills",
        "headline",
        "summary",
        "linkedin_url",
        "linkedin_username",
        "email",
        "phone",
        "website",
        "twitter",
        "github",
        "score",
        "vector_similarity",
        "lexical_rank",
        "content_quality_score",
        "data_completeness_pct",
    ]

    async def iter_csv():
        ctx: AuthContext = await resolve_auth_context(x_api_key)
        require_key = os.getenv("EXPORT_REQUIRE_API_KEY", "false").lower() == "true"
        if require_key and not ctx.allow_export:
            raise HTTPException(status_code=403, detail="Export not permitted without 'export:read' scope")
        if not limiter.allow(f"export:{ctx.api_key or request.client.host}", int(os.getenv("RATE_LIMIT_EXPORT_PER_MIN", "6")), int(os.getenv("RATE_LIMIT_EXPORT_BURST", "10"))):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        export_require_filter = os.getenv("EXPORT_REQUIRE_FILTER", "true").lower() == "true"
        has_any_filter = bool(location_country or (regions and len(regions) > 0) or (localities and len(localities) > 0))
        if (q.strip() == "") and (export_require_filter and not has_any_filter):
            raise HTTPException(status_code=422, detail="Export requires query or at least one filter")
        pool = await database.get_pool()
        async with pool.acquire() as conn:
            results, _ = await search.hybrid_search(conn, req)
            # Header
            sio = io.StringIO()
            writer = csv.DictWriter(sio, fieldnames=fieldnames)
            writer.writeheader()
            yield sio.getvalue()
            sio.seek(0)
            sio.truncate(0)
            for r in results:
                data = r.dict()
                # TEMPORARY: Disabled for testing - ENABLE IN PRODUCTION!
                # if not ctx.allow_pii:
                #     data["email"] = ""
                #     data["phone"] = ""
                if isinstance(data.get("skills"), list):
                    data["skills"] = "; ".join(data["skills"]) if data["skills"] else ""
                writer.writerow({k: data.get(k, "") for k in fieldnames})
                yield sio.getvalue()
                sio.seek(0)
                sio.truncate(0)

    return StreamingResponse(iter_csv(), headers=headers, media_type="text/csv")

# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Handle HTTP exceptions with ErrorResponse format"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "detail": None,
            "timestamp": datetime.utcnow().isoformat()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "timestamp": datetime.utcnow().isoformat()
        }
    )


if __name__ == "__main__":
    import uvicorn

    # Run with: python -m backend.api.app
    uvicorn.run(
        "backend.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
