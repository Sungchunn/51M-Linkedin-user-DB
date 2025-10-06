"""
INSIGHT - Field Validators
Validates row data before insertion to core schema

Negative Spaces Implementation:
- Explicit validation failures with context
- Returns (is_valid, error_message) tuples
- Fails fast on required field violations
"""

from typing import Tuple, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


def validate_required_fields(row: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate that required fields are present and non-empty.

    NEGATIVE SPACE CONTRACT:
    - full_name must exist and be non-empty
    - linkedin_username must exist and be non-empty

    Args:
        row: Transformed row dict

    Returns:
        (is_valid, error_message) tuple
    """
    # Check full_name
    full_name = row.get('full_name')
    if not full_name or (isinstance(full_name, str) and not full_name.strip()):
        return False, "NEGATIVE SPACE: Missing or empty full_name"

    # Check linkedin_username
    username = row.get('linkedin_username')
    if not username or (isinstance(username, str) and not username.strip()):
        return False, "NEGATIVE SPACE: Missing or empty linkedin_username"

    return True, None


def validate_numeric_ranges(row: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Validate numeric fields are within acceptable ranges.

    NEGATIVE SPACE CONTRACT:
    - years_experience: [0, 80] or None
    - content_quality_score: [0.0, 1.0] or None
    - profile_completeness: [0, 100] or None

    Args:
        row: Transformed row dict

    Returns:
        (is_valid, error_message) tuple
    """
    # Validate years_experience
    years = row.get('years_experience')
    if years is not None:
        if not isinstance(years, (int, float)):
            return False, f"NEGATIVE SPACE: years_experience must be numeric, got {type(years)}"

        if years < 0 or years > 80:
            return False, f"NEGATIVE SPACE: years_experience={years} outside [0, 80]"

    # Validate quality score
    quality = row.get('content_quality_score')
    if quality is not None:
        if not isinstance(quality, (int, float)):
            return False, f"NEGATIVE SPACE: content_quality_score must be numeric, got {type(quality)}"

        if quality < 0.0 or quality > 1.0:
            return False, f"NEGATIVE SPACE: content_quality_score={quality} outside [0.0, 1.0]"

    # Validate profile completeness
    completeness = row.get('profile_completeness')
    if completeness is not None:
        if not isinstance(completeness, (int, float)):
            return False, f"NEGATIVE SPACE: profile_completeness must be numeric, got {type(completeness)}"

        if completeness < 0 or completeness > 100:
            return False, f"NEGATIVE SPACE: profile_completeness={completeness} outside [0, 100]"

    return True, None


def validate_embedding_dimension(embedding: Optional[list]) -> Tuple[bool, Optional[str]]:
    """
    Validate embedding vector dimension.

    NEGATIVE SPACE CONTRACT:
    - Must be None or exactly 1536 dimensions
    - All values must be numeric

    Args:
        embedding: Embedding vector or None

    Returns:
        (is_valid, error_message) tuple
    """
    if embedding is None:
        return True, None

    if not isinstance(embedding, list):
        return False, f"NEGATIVE SPACE: embedding must be list, got {type(embedding)}"

    if len(embedding) != 1536:
        return False, f"NEGATIVE SPACE: embedding dimension={len(embedding)}, expected 1536"

    # Validate all values are numeric
    for i, val in enumerate(embedding):
        if not isinstance(val, (int, float)):
            return False, f"NEGATIVE SPACE: embedding[{i}] is {type(val)}, expected numeric"

    return True, None


def validate_row(row: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Run all validation checks on a row.

    NEGATIVE SPACE CONTRACT:
    - Fails fast on first validation failure
    - Returns detailed error context

    Args:
        row: Transformed row dict

    Returns:
        (is_valid, error_message) tuple
    """
    # Check required fields
    is_valid, error = validate_required_fields(row)
    if not is_valid:
        return is_valid, error

    # Check numeric ranges
    is_valid, error = validate_numeric_ranges(row)
    if not is_valid:
        return is_valid, error

    # Check embedding dimension
    embedding = row.get('embedding')
    is_valid, error = validate_embedding_dimension(embedding)
    if not is_valid:
        return is_valid, error

    return True, None


def calculate_quality_score(row: Dict[str, Any]) -> float:
    """
    Calculate content quality score for a profile.

    NEGATIVE SPACE CONTRACT:
    - Result must be in [0.0, 1.0]
    - Uses weighted scoring:
      * full_name: 0.15
      * linkedin_username: 0.15
      * job_title: 0.20
      * company_name: 0.15
      * industry: 0.10
      * location: 0.10
      * skills: 0.15

    Args:
        row: Transformed row dict

    Returns:
        Quality score in [0.0, 1.0]
    """
    score = 0.0

    # Core identity (30%)
    if row.get('full_name'):
        score += 0.15
    if row.get('linkedin_username'):
        score += 0.15

    # Professional info (50%)
    if row.get('job_title'):
        score += 0.20
    if row.get('company_name'):
        score += 0.15
    if row.get('industry'):
        score += 0.10

    # Location (10%)
    if row.get('location_country') or row.get('location'):
        score += 0.10

    # Skills (15%)
    skills = row.get('skills') or []
    if skills and len(skills) > 0:
        score += 0.15

    # NEGATIVE SPACE: Enforce invariant
    if not (0.0 <= score <= 1.0):
        logger.error(
            f"NEGATIVE SPACE VIOLATION: quality_score={score} outside [0.0, 1.0] "
            f"for username={row.get('linkedin_username')}"
        )
        raise ValueError(f"Quality score {score} violates [0.0, 1.0] invariant")

    return round(score, 2)


def should_skip_row(row: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """
    Determine if a row should be skipped during ingestion.

    NEGATIVE SPACE CONTRACT:
    - Skip if validation fails
    - Skip if duplicate linkedin_username (handled by DB UPSERT)
    - Log reason for skip

    Args:
        row: Transformed row dict

    Returns:
        (should_skip, reason) tuple
    """
    # Run validation
    is_valid, error = validate_row(row)

    if not is_valid:
        logger.warning(f"Skipping row: {error}")
        return True, error

    return False, None
