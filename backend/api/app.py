"""
INSIGHT - FastAPI Search API
Main application with endpoints for semantic talent search

Negative Spaces Implementation:
- Lifespan management for connection pool
- Request validation via Pydantic
- Error handling with proper status codes
- CORS configuration
"""

from fastapi import FastAPI, HTTPException, status, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "name": "INSIGHT - Semantic Talent Finder",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


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
async def get_stats(response: Response):
    """Get dataset statistics"""
    try:
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
async def search_profiles(request: SearchRequest):
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

        return SearchResponse(
            results=results,
            total_count=total_count,
            returned_count=len(results),
            offset=request.offset,
            limit=request.limit,
            query_time_ms=query_time_ms,
            query=request.query,
            filters_applied=filters_applied
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
    q: str = Query("", description="Search query text (empty for browse mode)"),
    limit: int = Query(20, ge=1, le=100, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
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
        min_quality_score=min_quality_score,
        min_data_completeness=min_data_completeness,
        vector_weight=vector_weight,
        lexical_weight=lexical_weight,
        ef_search=ef_search,
    )
    return await search_profiles(req)


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
