"""
INSIGHT - FastAPI Application (Rebuilt Architecture)
Hybrid search with Postgres hot serving, Redis caching, DuckDB analytics
"""

import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from backend.db import get_db_pool, close_db_pool
from backend.cache import cache
from backend.search import hybrid_search, get_profile_by_id, record_profile_view
from backend.duck import get_industry_stats, get_country_stats
from backend.models import (
    SearchRequest,
    SearchResponse,
    ProfileDetail,
    IndustryStats,
    CountryStats
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown"""
    # Startup
    logger.info("🚀 Starting INSIGHT API...")
    await get_db_pool()  # Initialize connection pool
    logger.info("✅ Database pool initialized")

    yield

    # Shutdown
    logger.info("🛑 Shutting down INSIGHT API...")
    await close_db_pool()
    logger.info("✅ Database pool closed")


app = FastAPI(
    title="INSIGHT - LinkedIn Profile Search API",
    description="Hybrid architecture: Postgres (hot) + Redis (cache) + DuckDB (analytics)",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "INSIGHT API v2",
        "architecture": "Postgres (hot) + Redis (cache) + DuckDB (analytics)"
    }


@app.post("/search", response_model=SearchResponse)
async def search_profiles(request: SearchRequest):
    """
    Hybrid semantic + keyword search on hot profiles.

    Uses Redis caching for repeated queries.
    Increments query_count_7d for matched profiles.
    """
    try:
        # Build cache key from request
        cache_key = f"search:{hash(request.model_dump_json())}"

        # Try cache first
        cached = await cache.get_search_results(cache_key)
        if cached:
            logger.info(f"Cache HIT for query: {request.query[:50]}...")
            return SearchResponse(**cached)

        # Execute search
        results = await hybrid_search(request)

        # Cache for 5 minutes
        await cache.set_search_results(cache_key, results.model_dump(), ttl=300)

        logger.info(
            f"Search complete: query='{request.query[:50]}', "
            f"results={len(results.results)}, took={results.search_time_ms}ms"
        )

        return results

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/profile/{profile_id}", response_model=ProfileDetail)
async def get_profile(profile_id: str):
    """
    Get full profile details (hot + detail tables joined).

    Uses Redis caching for repeated profile views.
    Increments click_count_7d for the profile.
    """
    try:
        # Try cache first
        cached = await cache.get_profile(profile_id)
        if cached:
            logger.info(f"Cache HIT for profile: {profile_id}")
            return ProfileDetail(**cached)

        # Fetch from database
        profile = await get_profile_by_id(profile_id)

        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")

        # Record view (increments click_count_7d)
        await record_profile_view(profile_id)

        # Cache for 10 minutes
        await cache.set_profile(profile_id, profile.model_dump(), ttl=600)

        logger.info(f"Profile fetched: {profile_id}")

        return profile

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile fetch failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch profile: {str(e)}")


@app.get("/stats/industry", response_model=List[IndustryStats])
async def get_industry_statistics(
    limit: int = Query(default=20, ge=1, le=100)
):
    """
    Get industry statistics using DuckDB analytics on S3 Parquet.

    Queries full 51M dataset without local copy.
    """
    try:
        stats = await get_industry_stats(limit=limit)
        return stats

    except Exception as e:
        logger.error(f"Industry stats failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")


@app.get("/stats/country", response_model=List[CountryStats])
async def get_country_statistics(
    limit: int = Query(default=20, ge=1, le=100)
):
    """
    Get country statistics using DuckDB analytics on S3 Parquet.
    """
    try:
        stats = await get_country_stats(limit=limit)
        return stats

    except Exception as e:
        logger.error(f"Country stats failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")


@app.get("/health")
async def health_check():
    """
    Detailed health check for all components.
    """
    health = {
        "status": "ok",
        "database": "unknown",
        "cache": "unknown",
        "duckdb": "unknown"
    }

    # Check database
    try:
        pool = await get_db_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                health["database"] = "ok"
    except Exception as e:
        health["database"] = f"error: {str(e)}"
        health["status"] = "degraded"

    # Check Redis
    try:
        await cache.ping()
        health["cache"] = "ok"
    except Exception as e:
        health["cache"] = f"error: {str(e)}"
        health["status"] = "degraded"

    # Check DuckDB (basic connectivity)
    try:
        from backend.duck import test_connection
        await test_connection()
        health["duckdb"] = "ok"
    except Exception as e:
        health["duckdb"] = f"error: {str(e)}"
        health["status"] = "degraded"

    return health


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("API_PORT", "8000"))

    uvicorn.run(
        "backend.app:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
