"""
INSIGHT - DuckDB-Only API
Browse and search 51M profiles directly from S3 without local storage
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging
import time

from backend.duck import get_duckdb_conn, get_parquet_path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="INSIGHT - DuckDB Talent Browser",
    description="Browse 51M+ LinkedIn profiles directly from S3 using DuckDB",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Models ===

class ProfileResult(BaseModel):
    """Single profile result"""
    full_name: str
    linkedin_username: Optional[str] = None
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    industry: Optional[str] = None
    location_country: Optional[str] = None
    region: Optional[str] = None
    locality: Optional[str] = None
    years_experience: Optional[int] = None
    skills: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None


class SearchResponse(BaseModel):
    """Search response with results and metadata"""
    results: List[ProfileResult]
    total_count: int
    returned_count: int
    offset: int
    limit: int
    query_time_ms: float
    filters_applied: Dict[str, Any]


class StatsResponse(BaseModel):
    """Dataset statistics"""
    total_profiles: int
    countries: List[Dict[str, Any]]
    industries: List[Dict[str, Any]]
    top_skills: List[Dict[str, Any]]


# === Helper Functions ===

def execute_query(query: str) -> List[Dict[str, Any]]:
    """Execute DuckDB query and return results as list of dicts"""
    try:
        conn = get_duckdb_conn()
        result = conn.execute(query).fetchall()

        if not result:
            return []

        # Get column names
        columns = [desc[0] for desc in conn.description]

        # Convert to list of dicts
        return [dict(zip(columns, row)) for row in result]

    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


def build_where_clause(
    keyword: Optional[str] = None,
    country: Optional[str] = None,
    industry: Optional[str] = None,
    min_experience: Optional[int] = None,
    max_experience: Optional[int] = None,
    skills: Optional[str] = None
) -> str:
    """Build WHERE clause from filters"""
    conditions = []

    if keyword:
        # Search in multiple fields
        keyword_escaped = keyword.replace("'", "''")
        conditions.append(f"""(
            "Full Name" ILIKE '%{keyword_escaped}%' OR
            "Job Title" ILIKE '%{keyword_escaped}%' OR
            "Company Name" ILIKE '%{keyword_escaped}%' OR
            "Industry" ILIKE '%{keyword_escaped}%' OR
            "Headline" ILIKE '%{keyword_escaped}%' OR
            "Summary" ILIKE '%{keyword_escaped}%' OR
            "Skills" ILIKE '%{keyword_escaped}%'
        )""")

    if country:
        country_escaped = country.replace("'", "''")
        conditions.append(f"\"Location Country\" = '{country_escaped}'")

    if industry:
        industry_escaped = industry.replace("'", "''")
        conditions.append(f"\"Industry\" = '{industry_escaped}'")

    if min_experience is not None:
        conditions.append(f"\"Years Experience\" >= {min_experience}")

    if max_experience is not None:
        conditions.append(f"\"Years Experience\" <= {max_experience}")

    if skills:
        skills_escaped = skills.replace("'", "''")
        conditions.append(f"\"Skills\" ILIKE '%{skills_escaped}%'")

    return " AND ".join(conditions) if conditions else "1=1"


# === Endpoints ===

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "name": "INSIGHT - DuckDB Talent Browser",
        "version": "1.0.0",
        "status": "running",
        "dataset": "51M+ LinkedIn profiles",
        "storage": "S3 (zero local disk usage)",
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check - verify S3 connectivity"""
    try:
        parquet_path = get_parquet_path()
        conn = get_duckdb_conn()

        # Quick count query
        result = conn.execute(f"SELECT COUNT(*) as total FROM read_parquet('{parquet_path}')").fetchone()
        total = result[0]

        return {
            "status": "healthy",
            "timestamp": datetime.utcnow(),
            "s3_path": parquet_path,
            "total_profiles": total,
            "storage": "S3 (zero local disk)"
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"S3 connectivity failed: {str(e)}")


@app.get("/search", response_model=SearchResponse, tags=["Search"])
async def search_profiles(
    keyword: Optional[str] = Query(None, description="Search keyword (searches across all text fields)"),
    country: Optional[str] = Query(None, description="Filter by country (exact match)"),
    industry: Optional[str] = Query(None, description="Filter by industry (exact match)"),
    min_experience: Optional[int] = Query(None, ge=0, le=80, description="Minimum years of experience"),
    max_experience: Optional[int] = Query(None, ge=0, le=80, description="Maximum years of experience"),
    skills: Optional[str] = Query(None, description="Filter by skills (partial match)"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum results to return")
):
    """
    Search profiles with filters.

    Queries S3 Parquet directly - no local storage needed.
    """
    start_time = time.time()
    parquet_path = get_parquet_path()

    # Build WHERE clause
    where_clause = build_where_clause(
        keyword=keyword,
        country=country,
        industry=industry,
        min_experience=min_experience,
        max_experience=max_experience,
        skills=skills
    )

    try:
        # Count query
        count_query = f"""
            SELECT COUNT(*) as total
            FROM read_parquet('{parquet_path}')
            WHERE {where_clause}
        """
        count_result = execute_query(count_query)
        total_count = count_result[0]['total'] if count_result else 0

        # Data query
        data_query = f"""
            SELECT
                "Full Name" as full_name,
                "LinkedIn Username" as linkedin_username,
                "Job Title" as job_title,
                "Company Name" as company_name,
                "Industry" as industry,
                "Location Country" as location_country,
                "Region" as region,
                "Locality" as locality,
                "Years Experience" as years_experience,
                "Skills" as skills,
                "Headline" as headline,
                "Summary" as summary
            FROM read_parquet('{parquet_path}')
            WHERE {where_clause}
            ORDER BY "Full Name"
            LIMIT {limit}
            OFFSET {offset}
        """

        results = execute_query(data_query)

        # Convert to ProfileResult models
        profiles = [ProfileResult(**row) for row in results]

        query_time_ms = (time.time() - start_time) * 1000

        # Build filters dict
        filters_applied = {}
        if keyword:
            filters_applied['keyword'] = keyword
        if country:
            filters_applied['country'] = country
        if industry:
            filters_applied['industry'] = industry
        if min_experience is not None:
            filters_applied['min_experience'] = min_experience
        if max_experience is not None:
            filters_applied['max_experience'] = max_experience
        if skills:
            filters_applied['skills'] = skills

        logger.info(
            f"Search completed: filters={filters_applied}, "
            f"results={len(profiles)}/{total_count}, "
            f"time={query_time_ms:.1f}ms"
        )

        return SearchResponse(
            results=profiles,
            total_count=total_count,
            returned_count=len(profiles),
            offset=offset,
            limit=limit,
            query_time_ms=query_time_ms,
            filters_applied=filters_applied
        )

    except Exception as e:
        logger.error(f"Search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@app.get("/stats", response_model=StatsResponse, tags=["Analytics"])
async def get_stats():
    """
    Get dataset statistics.

    Returns top countries, industries, and skills.
    """
    parquet_path = get_parquet_path()

    try:
        # Total count
        total_query = f"SELECT COUNT(*) as total FROM read_parquet('{parquet_path}')"
        total_result = execute_query(total_query)
        total = total_result[0]['total']

        # Top countries
        countries_query = f"""
            SELECT
                "Location Country" as country,
                COUNT(*) as count
            FROM read_parquet('{parquet_path}')
            WHERE "Location Country" IS NOT NULL
            GROUP BY "Location Country"
            ORDER BY count DESC
            LIMIT 20
        """
        countries = execute_query(countries_query)

        # Top industries
        industries_query = f"""
            SELECT
                "Industry" as industry,
                COUNT(*) as count
            FROM read_parquet('{parquet_path}')
            WHERE "Industry" IS NOT NULL
            GROUP BY "Industry"
            ORDER BY count DESC
            LIMIT 20
        """
        industries = execute_query(industries_query)

        # Note: Skills are complex to parse, returning empty for now
        top_skills = []

        return StatsResponse(
            total_profiles=total,
            countries=countries,
            industries=industries,
            top_skills=top_skills
        )

    except Exception as e:
        logger.error(f"Stats query failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Stats failed: {str(e)}")


@app.get("/countries", tags=["Filters"])
async def get_countries():
    """Get list of all countries for filter dropdown"""
    parquet_path = get_parquet_path()

    query = f"""
        SELECT DISTINCT "Location Country" as country
        FROM read_parquet('{parquet_path}')
        WHERE "Location Country" IS NOT NULL
        ORDER BY country
    """

    results = execute_query(query)
    return {"countries": [r['country'] for r in results]}


@app.get("/industries", tags=["Filters"])
async def get_industries():
    """Get list of all industries for filter dropdown"""
    parquet_path = get_parquet_path()

    query = f"""
        SELECT DISTINCT "Industry" as industry
        FROM read_parquet('{parquet_path}')
        WHERE "Industry" IS NOT NULL
        ORDER BY industry
    """

    results = execute_query(query)
    return {"industries": [r['industry'] for r in results]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.api.duckdb_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
