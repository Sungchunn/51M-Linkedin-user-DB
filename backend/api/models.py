"""
INSIGHT - API Models
Pydantic models for request/response validation

Negative Spaces Implementation:
- Strict type validation
- Range constraints on numeric fields
- Required vs optional fields clearly defined
"""

from typing import List, Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime


class SearchRequest(BaseModel):
    """
    Search request with hybrid search parameters.

    NEGATIVE SPACE CONTRACT:
    - query is required and non-empty
    - limit must be [1, 100]
    - offset must be >= 0
    - vector_weight + lexical_weight should = 1.0 (warning if not)
    """
    # Query text (optional - if empty, returns recent profiles with filters)
    query: str = Field("", description="Search query text (empty for browse mode)")

    # Pagination
    limit: int = Field(20, ge=1, le=100, description="Number of results to return")
    offset: int = Field(0, ge=0, description="Offset for pagination")

    # Filters
    location_country: Optional[str] = Field(None, description="Filter by country")
    region: Optional[str] = Field(None, description="Filter by region/state")
    locality: Optional[str] = Field(None, description="Filter by city")

    min_years_experience: Optional[int] = Field(None, ge=0, le=80, description="Minimum years of experience")
    max_years_experience: Optional[int] = Field(None, ge=0, le=80, description="Maximum years of experience")

    skills: Optional[List[str]] = Field(None, description="Required skills (AND logic)")
    industry: Optional[str] = Field(None, description="Filter by industry")

    min_quality_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum quality score")

    # Search weights
    vector_weight: float = Field(0.8, ge=0.0, le=1.0, description="Weight for vector similarity")
    lexical_weight: float = Field(0.2, ge=0.0, le=1.0, description="Weight for lexical matching")

    # HNSW search parameter
    ef_search: int = Field(64, ge=10, le=400, description="HNSW ef_search parameter (quality vs speed)")

    @validator('max_years_experience')
    def validate_experience_range(cls, v, values):
        """Ensure max >= min for experience range"""
        if v is not None and 'min_years_experience' in values:
            min_exp = values['min_years_experience']
            if min_exp is not None and v < min_exp:
                raise ValueError(
                    f"NEGATIVE SPACE: max_years_experience ({v}) must be >= "
                    f"min_years_experience ({min_exp})"
                )
        return v

    class Config:
        schema_extra = {
            "example": {
                "query": "senior software engineer with python experience",
                "limit": 20,
                "offset": 0,
                "location_country": "united states",
                "region": "california",
                "min_years_experience": 5,
                "skills": ["python", "sql"],
                "vector_weight": 0.8,
                "lexical_weight": 0.2
            }
        }


class ProfileResult(BaseModel):
    """
    Single profile search result.

    NEGATIVE SPACE CONTRACT:
    - id is always present (UUID)
    - score is in [0.0, 1.0]
    - All nullable fields explicitly typed as Optional
    """
    id: str
    full_name: str
    job_title: Optional[str]
    company_name: Optional[str]
    industry: Optional[str]
    location: Optional[str]
    location_country: Optional[str]
    region: Optional[str]
    locality: Optional[str]
    years_experience: Optional[int]
    skills: Optional[List[str]]
    headline: Optional[str]
    summary: Optional[str]

    # Search metadata
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    vector_similarity: Optional[float] = Field(None, ge=0.0, le=1.0)
    lexical_rank: Optional[float] = Field(None, ge=0.0)

    # Quality metrics
    content_quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    class Config:
        schema_extra = {
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "full_name": "John Doe",
                "job_title": "Senior Software Engineer",
                "company_name": "Tech Corp",
                "location_country": "united states",
                "skills": ["python", "sql", "docker"],
                "score": 0.92,
                "vector_similarity": 0.95,
                "content_quality_score": 0.85
            }
        }


class SearchResponse(BaseModel):
    """
    Search response with results and metadata.

    NEGATIVE SPACE CONTRACT:
    - results count matches actual list length
    - total_count >= results count
    - query_time_ms >= 0
    """
    results: List[ProfileResult]
    total_count: int = Field(..., ge=0)
    returned_count: int = Field(..., ge=0)
    offset: int = Field(..., ge=0)
    limit: int = Field(..., ge=1, le=100)
    query_time_ms: float = Field(..., ge=0.0)

    query: str
    filters_applied: dict

    @validator('returned_count')
    def validate_returned_count(cls, v, values):
        """Ensure returned_count matches results length"""
        if 'results' in values:
            actual_count = len(values['results'])
            if v != actual_count:
                raise ValueError(
                    f"NEGATIVE SPACE: returned_count ({v}) must match "
                    f"results length ({actual_count})"
                )
        return v

    class Config:
        schema_extra = {
            "example": {
                "results": [],
                "total_count": 1250,
                "returned_count": 20,
                "offset": 0,
                "limit": 20,
                "query_time_ms": 145.3,
                "query": "senior software engineer",
                "filters_applied": {
                    "location_country": "united states",
                    "min_years_experience": 5
                }
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    database: str
    profiles_total: int
    profiles_with_embeddings: int

    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2025-10-07T03:00:00Z",
                "database": "connected",
                "profiles_total": 10000,
                "profiles_with_embeddings": 5000
            }
        }


class ErrorResponse(BaseModel):
    """Error response"""
    error: str
    detail: Optional[str] = None
    timestamp: datetime

    class Config:
        schema_extra = {
            "example": {
                "error": "Invalid query parameter",
                "detail": "Query text cannot be empty",
                "timestamp": "2025-10-07T03:00:00Z"
            }
        }
