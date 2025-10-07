"""
INSIGHT - Pydantic Models
Request/response schemas for FastAPI endpoints
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# Search request/response models

class SearchRequest(BaseModel):
    """Search request with query and filters"""

    query: str = Field(..., description="Search query text")
    limit: int = Field(default=20, ge=1, le=100, description="Max results")

    # Filters
    country: Optional[str] = Field(None, description="Filter by country")
    industry: Optional[str] = Field(None, description="Filter by industry")
    seniority: Optional[str] = Field(None, description="Filter by seniority level")
    min_experience: Optional[int] = Field(None, ge=0, description="Min years experience")
    max_experience: Optional[int] = Field(None, ge=0, description="Max years experience")
    skills: Optional[List[str]] = Field(None, description="Required skills (any match)")
    min_quality_score: Optional[float] = Field(None, ge=0, le=1, description="Min quality score")


class ProfileResult(BaseModel):
    """Profile result from search"""

    id: str
    linkedin_username: str
    full_name: str
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    headline: Optional[str] = None
    location_country: Optional[str] = None
    industry: Optional[str] = None
    seniority_level: Optional[str] = None
    years_experience: Optional[int] = None
    top_skills: Optional[List[str]] = None
    quality_score: Optional[float] = None
    hotness_score: Optional[float] = None
    relevance_score: Optional[float] = Field(None, description="Search relevance (0-1)")


class SearchResponse(BaseModel):
    """Search response with results and metadata"""

    results: List[ProfileResult]
    total_results: int
    search_time_ms: int
    query: str


# Profile detail models

class ProfileDetail(BaseModel):
    """Full profile details (hot + detail joined)"""

    id: str
    linkedin_username: str
    full_name: str
    job_title: Optional[str] = None
    company_name: Optional[str] = None
    headline: Optional[str] = None
    summary: Optional[str] = None
    location_country: Optional[str] = None
    industry: Optional[str] = None
    seniority_level: Optional[str] = None
    years_experience: Optional[int] = None
    top_skills: Optional[List[str]] = None
    all_skills: Optional[List[str]] = None
    email: Optional[str] = None
    experience_json: Optional[dict] = None
    education_json: Optional[dict] = None
    quality_score: Optional[float] = None
    hotness_score: Optional[float] = None
    query_count_7d: Optional[int] = None
    click_count_7d: Optional[int] = None


# Analytics models

class IndustryStats(BaseModel):
    """Industry statistics from DuckDB analytics"""

    industry: str
    count: int
    avg_completeness: Optional[float] = None
    countries: Optional[int] = None


class CountryStats(BaseModel):
    """Country statistics from DuckDB analytics"""

    country: str
    count: int
    avg_experience: Optional[float] = None
    industries: Optional[int] = None
