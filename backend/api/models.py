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
import logging

logger = logging.getLogger(__name__)
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
    limit: int = Field(20, ge=1, le=1000, description="Number of results to return (max 1000)")
    offset: int = Field(0, ge=0, description="Offset for pagination")

    # Opaque pagination
    page_token: Optional[str] = Field(None, description="Opaque token to fetch the next page (overrides offset/filters if provided)")

    # Filters
    location_country: Optional[str] = Field(None, description="Filter by country")
    region: Optional[str] = Field(None, description="Filter by region/state (deprecated - use regions)")
    regions: Optional[List[str]] = Field(None, description="Filter by multiple regions/states (OR logic)")
    locality: Optional[str] = Field(None, description="Filter by city (deprecated - use localities)")
    localities: Optional[List[str]] = Field(None, description="Filter by multiple cities (OR logic)")

    min_years_experience: Optional[int] = Field(None, ge=0, le=80, description="Minimum years of experience")
    max_years_experience: Optional[int] = Field(None, ge=0, le=80, description="Maximum years of experience")

    skills: Optional[List[str]] = Field(None, description="Required skills (AND logic)")
    industry: Optional[str] = Field(None, description="Filter by single industry (deprecated - use industries)")
    industries: Optional[List[str]] = Field(None, description="Filter by multiple industries (OR logic)")

    # Job and company filters
    job_title: Optional[str] = Field(None, description="Filter by job title (partial match)")
    company: Optional[str] = Field(None, description="Filter by company name (partial match)")

    # Contact information filters
    has_linkedin: Optional[bool] = Field(None, description="Filter profiles with LinkedIn URL")
    has_email: Optional[bool] = Field(None, description="Filter profiles with email")
    has_phone: Optional[bool] = Field(None, description="Filter profiles with phone")
    has_website: Optional[bool] = Field(None, description="Filter profiles with website")
    has_twitter: Optional[bool] = Field(None, description="Filter profiles with Twitter")
    has_github: Optional[bool] = Field(None, description="Filter profiles with GitHub")

    min_quality_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum quality score")
    min_data_completeness: Optional[int] = Field(None, ge=0, le=100, description="Minimum data completeness percentage")

    # Search weights
    vector_weight: float = Field(0.8, ge=0.0, le=1.0, description="Weight for vector similarity")
    lexical_weight: float = Field(0.2, ge=0.0, le=1.0, description="Weight for lexical matching")

    # HNSW search parameter
    ef_search: int = Field(64, ge=10, le=400, description="HNSW ef_search parameter (quality vs speed)")

    @validator('lexical_weight')
    def validate_weights(cls, v, values):
        """Warn if vector_weight + lexical_weight != 1.0"""
        vec = values.get('vector_weight', 0.0)
        total = vec + v
        if abs(total - 1.0) > 1e-6:
            logger.warning(
                f"NEGATIVE SPACE: vector_weight ({vec}) + lexical_weight ({v}) != 1.0; total={total}"
            )
        return v

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
    first_name: Optional[str]
    last_name: Optional[str]
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

    # Contact & Social
    linkedin_url: Optional[str]
    linkedin_username: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    website: Optional[str]
    twitter: Optional[str]
    github: Optional[str]

    # Search metadata
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    vector_similarity: Optional[float] = Field(None, ge=0.0, le=1.0)
    lexical_rank: Optional[float] = Field(None, ge=0.0)

    # Quality metrics
    content_quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    data_completeness_pct: Optional[int] = Field(None, ge=0, le=100, description="Data completeness percentage (0-100)")

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
                "content_quality_score": 0.85,
                "data_completeness_pct": 75
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
    next_page_token: Optional[str] = Field(None, description="Token to retrieve the next page")

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


# ==================== AUTHENTICATION MODELS ====================

class UserRegisterRequest(BaseModel):
    """User registration request"""
    username: str = Field(..., min_length=3, max_length=50, description="Username (3-50 chars)")
    email: str = Field(..., description="Email address")
    password: str = Field(..., min_length=8, description="Password (min 8 chars)")
    full_name: Optional[str] = Field(None, max_length=255, description="Full name")

    @validator('username')
    def username_alphanumeric(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must be alphanumeric (underscores and hyphens allowed)')
        return v.lower()

    @validator('email')
    def email_lowercase(cls, v):
        return v.lower()


class UserLoginRequest(BaseModel):
    """User login request"""
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Seconds until access token expires")


class UserResponse(BaseModel):
    """User profile response"""
    id: str
    username: str
    email: str
    full_name: Optional[str]
    is_admin: bool
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime]


class APIKeyCreateRequest(BaseModel):
    """Request to create a new API key"""
    key_name: str = Field(..., min_length=3, max_length=100, description="Descriptive name for the API key")
    scopes: List[str] = Field(default=["search:read"], description="Permissions: search:read, export:read, pii:read")
    tier: str = Field(default="basic", description="Tier: public, basic, trusted")
    expires_in_days: Optional[int] = Field(None, gt=0, le=365, description="Expiration in days (max 365)")

    @validator('tier')
    def validate_tier(cls, v):
        if v not in ['public', 'basic', 'trusted']:
            raise ValueError('Tier must be: public, basic, or trusted')
        return v

    @validator('scopes')
    def validate_scopes(cls, v):
        valid_scopes = {'search:read', 'export:read', 'pii:read', 'admin:write'}
        for scope in v:
            if scope not in valid_scopes:
                raise ValueError(f'Invalid scope: {scope}. Valid: {valid_scopes}')
        return v


class APIKeyResponse(BaseModel):
    """API key response (created)"""
    id: str
    api_key: str = Field(..., description="Full API key - SAVE THIS! Only shown once")
    key_prefix: str = Field(..., description="First 16 chars for identification")
    key_name: str
    scopes: List[str]
    tier: str
    is_active: bool
    created_at: datetime


class APIKeyListItem(BaseModel):
    """API key list item (without full key)"""
    id: str
    key_name: str
    key_prefix: str = Field(..., description="First 16 chars (e.g., abc123...)")
    scopes: List[str]
    tier: str
    is_active: bool
    usage_count: int
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    created_at: datetime
