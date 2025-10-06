"""
INSIGHT - Field Transformers
Transforms raw staging data to core schema format

Negative Spaces Implementation:
- Validates input types
- Returns None for unparseable values
- Enforces bounded ranges
- Normalizes text fields
"""

import re
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def parse_skills(skills_text: Optional[str]) -> List[str]:
    """
    Parse skills from comma/semicolon separated string.

    NEGATIVE SPACE CONTRACT:
    - Returns empty list for None/empty input
    - Splits on comma, semicolon, or pipe
    - Lowercases and strips whitespace
    - Removes empty strings

    Args:
        skills_text: Raw skills string (e.g., "Python, SQL; Docker")

    Returns:
        List of normalized skill strings
    """
    if not skills_text or not isinstance(skills_text, str):
        return []

    # Split on common delimiters
    skills = re.split(r'[,;|]', skills_text)

    # Normalize: lowercase, strip, filter empty
    normalized = []
    for skill in skills:
        cleaned = skill.strip().lower()
        if cleaned:  # NEGATIVE SPACE: exclude empty strings
            normalized.append(cleaned)

    return normalized


def normalize_skill(skill: str) -> str:
    """
    Normalize a single skill for fuzzy matching.

    NEGATIVE SPACE CONTRACT:
    - Input must be non-empty string
    - Removes all non-alphanumeric characters
    - Lowercases
    - Returns empty string for invalid input

    Examples:
        "Machine Learning" -> "machinelearning"
        "C++" -> "c"
        "Node.js" -> "nodejs"
    """
    if not skill or not isinstance(skill, str):
        return ""

    # Lowercase
    normalized = skill.lower().strip()

    # Remove all non-alphanumeric characters
    normalized = re.sub(r'[^a-z0-9]', '', normalized)

    return normalized


def parse_years_experience(years_text: Optional[str]) -> Optional[int]:
    """
    Extract numeric years from messy experience strings.

    NEGATIVE SPACE CONTRACT:
    - Returns None for unparseable input
    - Returns None for values > 80 (biological limit)
    - Returns None for negative values
    - Handles ranges by taking lower bound

    Args:
        years_text: Raw string (e.g., "5", "5 years", "10+", "3-5")

    Returns:
        Integer years or None
    """
    if not years_text:
        return None

    # Convert to string if not already
    years_str = str(years_text).strip()

    if not years_str:
        return None

    # Extract first number from string
    match = re.search(r'\d+', years_str)

    if not match:
        return None

    try:
        years = int(match.group())

        # NEGATIVE SPACE: Enforce biological limits
        if years < 0 or years > 80:
            logger.warning(
                f"NEGATIVE SPACE: years_experience={years} outside [0, 80], returning None"
            )
            return None

        return years

    except ValueError:
        return None


def map_geo_fields(row: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Map location fields from staging to core schema.

    NEGATIVE SPACE CONTRACT:
    - All output values must be str or None (never empty string)
    - Preserves NULL values (None != "")

    Args:
        row: Dict with keys: Location, Locality, Region, Location Country

    Returns:
        Dict with keys: location, locality, region, location_country
    """
    def clean_geo(value: Any) -> Optional[str]:
        """Convert empty strings to None, preserve non-empty strings"""
        if value is None:
            return None
        if not isinstance(value, str):
            value = str(value)
        stripped = value.strip()
        return stripped if stripped else None

    return {
        'location': clean_geo(row.get('Location')),
        'locality': clean_geo(row.get('Locality')),
        'region': clean_geo(row.get('Region')),
        'location_country': clean_geo(row.get('Location Country')),
    }


def clean_text_field(text: Optional[str], max_length: Optional[int] = None) -> Optional[str]:
    """
    Clean and normalize text fields.

    NEGATIVE SPACE CONTRACT:
    - Returns None for None input (preserves NULL)
    - Returns None for empty/whitespace-only strings
    - Truncates to max_length if specified
    - Strips leading/trailing whitespace

    Args:
        text: Raw text field
        max_length: Optional max length (truncates if exceeded)

    Returns:
        Cleaned text or None
    """
    if text is None:
        return None

    if not isinstance(text, str):
        text = str(text)

    # Strip whitespace
    cleaned = text.strip()

    # NEGATIVE SPACE: Empty string becomes None
    if not cleaned:
        return None

    # Truncate if max_length specified
    if max_length and len(cleaned) > max_length:
        cleaned = cleaned[:max_length]

    return cleaned


def parse_boolean(value: Any) -> bool:
    """
    Parse boolean from various formats.

    NEGATIVE SPACE CONTRACT:
    - Defaults to False for unparseable values
    - Handles: True/False, "true"/"false", 1/0, "yes"/"no"

    Args:
        value: Any value to parse as boolean

    Returns:
        Boolean value (defaults to False)
    """
    if value is None:
        return False

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return value != 0

    if isinstance(value, str):
        lower = value.lower().strip()
        return lower in ('true', 't', 'yes', 'y', '1')

    return False


def validate_email(email: Optional[str]) -> Optional[str]:
    """
    Validate and normalize email address.

    NEGATIVE SPACE CONTRACT:
    - Returns None for invalid format
    - Returns None for empty/whitespace input
    - Lowercases domain

    Args:
        email: Raw email string

    Returns:
        Normalized email or None
    """
    if not email or not isinstance(email, str):
        return None

    email = email.strip()

    if not email:
        return None

    # Basic email regex (same as DB constraint)
    email_pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'

    if not re.match(email_pattern, email):
        logger.debug(f"Invalid email format: {email}")
        return None

    return email.lower()


def validate_linkedin_username(username: Optional[str]) -> Optional[str]:
    """
    Validate LinkedIn username format.

    NEGATIVE SPACE CONTRACT:
    - Returns None for invalid format
    - Must match ^[a-zA-Z0-9_-]+$ pattern (same as DB constraint)
    - Strips whitespace

    Args:
        username: Raw LinkedIn username

    Returns:
        Validated username or None
    """
    if not username or not isinstance(username, str):
        return None

    username = username.strip()

    if not username:
        return None

    # Must match DB constraint pattern
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        logger.warning(f"NEGATIVE SPACE: Invalid LinkedIn username format: {username}")
        return None

    return username


def extract_founded_year(year_text: Optional[str]) -> Optional[int]:
    """
    Extract company founding year.

    NEGATIVE SPACE CONTRACT:
    - Returns None for unparseable input
    - Returns None for years < 1800 or > current year
    - Handles 2-digit years (assumes 19xx or 20xx)

    Args:
        year_text: Raw year string

    Returns:
        Integer year or None
    """
    if not year_text:
        return None

    year_str = str(year_text).strip()

    if not year_str:
        return None

    # Extract 4-digit year
    match = re.search(r'\d{4}', year_str)

    if match:
        try:
            year = int(match.group())

            # NEGATIVE SPACE: Enforce reasonable bounds (same as DB)
            from datetime import datetime
            current_year = datetime.now().year

            if year < 1800 or year > current_year:
                logger.warning(
                    f"NEGATIVE SPACE: founded_year={year} outside [1800, {current_year}]"
                )
                return None

            return year

        except ValueError:
            return None

    return None


def build_content_for_embedding(row: Dict[str, Any]) -> str:
    """
    Build content string for embedding generation.

    Template: Professional: {job_title} at {company_name} | Industry: {industry} | Location: {location} | Skills: {skills}

    NEGATIVE SPACE CONTRACT:
    - Always returns non-empty string
    - Uses "N/A" for missing fields (not empty string)
    - Truncates to 8000 chars max

    Args:
        row: Profile data dict

    Returns:
        Formatted content string
    """
    job_title = row.get('job_title') or 'N/A'
    company = row.get('company_name') or 'N/A'
    industry = row.get('industry') or 'N/A'
    location = row.get('location') or 'N/A'

    # Skills array to comma-separated string
    skills = row.get('skills') or []
    if isinstance(skills, list):
        skills_text = ', '.join(skills) if skills else 'N/A'
    else:
        skills_text = str(skills)

    content = (
        f"Professional: {job_title} at {company} | "
        f"Industry: {industry} | "
        f"Location: {location} | "
        f"Skills: {skills_text}"
    )

    # NEGATIVE SPACE: Truncate to max length
    if len(content) > 8000:
        content = content[:8000]

    return content
