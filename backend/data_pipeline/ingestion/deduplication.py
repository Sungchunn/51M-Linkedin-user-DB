"""
INSIGHT - Data Deduplication Module
Prevents duplicate profile imports across multiple data loads

Negative Spaces Implementation:
- Unique constraint on linkedin_username (enforced at DB level)
- Hash-based deduplication for full_name + company + job_title
- Skip existing profiles, log conflicts
- Idempotent operations (safe to re-run)
"""

import hashlib
from typing import Dict, Any, Optional, Set
import psycopg
from psycopg.rows import dict_row
import logging

logger = logging.getLogger(__name__)


class DeduplicationError(Exception):
    """Raised when deduplication operations fail"""
    pass


def generate_profile_hash(row: Dict[str, Any]) -> str:
    """
    Generate deterministic hash for a profile using MD5 (matches database-side hashing).

    Used for detecting duplicate imports even when linkedin_username is missing.

    NEGATIVE SPACE CONTRACT:
    - Always returns 32-character hex string (MD5)
    - Same profile data → same hash
    - Uses: full_name + job_title + company_name
    - Matches PostgreSQL MD5() function output

    Args:
        row: Profile dict with full_name, job_title, company_name

    Returns:
        MD5 hex string
    """
    # Normalize and combine key fields (must match database query)
    full_name = str(row.get('full_name', '')).lower().strip()
    job_title = str(row.get('job_title', '')).lower().strip()
    company_name = str(row.get('company_name', '')).lower().strip()

    # Create deterministic hash (MD5 for speed, matches database)
    content = f"{full_name}|{job_title}|{company_name}"
    hash_obj = hashlib.md5(content.encode('utf-8'))
    return hash_obj.hexdigest()


def get_existing_linkedin_usernames(conn: psycopg.Connection) -> Set[str]:
    """
    Fetch all existing LinkedIn usernames from database.

    NEGATIVE SPACE CONTRACT:
    - Returns set (O(1) lookup)
    - Excludes NULL usernames
    - Excludes soft-deleted profiles

    Args:
        conn: Database connection

    Returns:
        Set of lowercase linkedin usernames
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT LOWER(linkedin_username)
            FROM profiles
            WHERE linkedin_username IS NOT NULL
              AND is_deleted = FALSE
        """)

        results = cur.fetchall()
        usernames = {row[0] for row in results}

    logger.info(f"Found {len(usernames):,} existing LinkedIn usernames")
    return usernames


def get_existing_profile_hashes(conn: psycopg.Connection) -> Set[str]:
    """
    Fetch all existing profile hashes from database using database-side hash generation.

    Used as secondary deduplication when linkedin_username is missing.

    NEGATIVE SPACE CONTRACT:
    - Returns set (O(1) lookup)
    - Only includes non-deleted profiles
    - Uses PostgreSQL MD5 for faster hashing

    Args:
        conn: Database connection

    Returns:
        Set of profile hashes
    """
    with conn.cursor() as cur:
        # Use database-side hash generation (much faster than Python loop)
        cur.execute("""
            SELECT MD5(
                LOWER(COALESCE(full_name, '')) || '|' ||
                LOWER(COALESCE(job_title, '')) || '|' ||
                LOWER(COALESCE(company_name, ''))
            ) as profile_hash
            FROM profiles
            WHERE is_deleted = FALSE
              AND linkedin_username IS NULL
        """)

        results = cur.fetchall()

    # Extract hashes from results (already computed in database)
    hashes = {row[0] for row in results}

    logger.info(f"Loaded {len(hashes):,} profile hashes for deduplication")
    return hashes


def is_duplicate_profile(
    row: Dict[str, Any],
    existing_usernames: Set[str],
    existing_hashes: Set[str]
) -> tuple[bool, Optional[str]]:
    """
    Check if profile is duplicate based on linkedin_username or content hash.

    NEGATIVE SPACE CONTRACT:
    - Returns (is_duplicate: bool, reason: str)
    - Primary check: linkedin_username
    - Fallback check: profile content hash

    Args:
        row: Profile dict to check
        existing_usernames: Set of existing LinkedIn usernames
        existing_hashes: Set of existing profile hashes

    Returns:
        Tuple of (is_duplicate, reason_string)
    """
    # Primary: Check LinkedIn username
    linkedin_username = row.get('linkedin_username')
    if linkedin_username:
        username_lower = linkedin_username.lower()
        if username_lower in existing_usernames:
            return True, f"linkedin_username: {linkedin_username}"

    # Secondary: Check content hash (for profiles without LinkedIn username)
    profile_hash = generate_profile_hash(row)
    if profile_hash in existing_hashes:
        name = row.get('full_name', 'Unknown')
        company = row.get('company_name', 'Unknown')
        return True, f"content_hash: {name} @ {company}"

    return False, None


def filter_duplicate_profiles(
    profiles: list[Dict[str, Any]],
    conn: psycopg.Connection
) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]]]:
    """
    Filter out duplicate profiles from import batch.

    NEGATIVE SPACE CONTRACT:
    - Returns (unique_profiles, duplicate_profiles)
    - len(unique) + len(duplicates) = len(profiles)
    - Logs all duplicates with reason

    Args:
        profiles: List of profile dicts to filter
        conn: Database connection

    Returns:
        Tuple of (unique_profiles, duplicate_profiles)
    """
    # Get existing data
    existing_usernames = get_existing_linkedin_usernames(conn)
    existing_hashes = get_existing_profile_hashes(conn)

    unique_profiles = []
    duplicate_profiles = []

    for profile in profiles:
        is_dup, reason = is_duplicate_profile(profile, existing_usernames, existing_hashes)

        if is_dup:
            duplicate_profiles.append(profile)
            logger.debug(f"Skipping duplicate: {reason}")
        else:
            unique_profiles.append(profile)

            # Add to tracking sets (for within-batch deduplication)
            linkedin_username = profile.get('linkedin_username')
            if linkedin_username:
                existing_usernames.add(linkedin_username.lower())
            existing_hashes.add(generate_profile_hash(profile))

    logger.info(
        f"Deduplication: {len(unique_profiles):,} unique, "
        f"{len(duplicate_profiles):,} duplicates"
    )

    return unique_profiles, duplicate_profiles


def get_import_statistics(conn: psycopg.Connection) -> Dict[str, int]:
    """
    Get database statistics for import reporting.

    Args:
        conn: Database connection

    Returns:
        Dict with total_profiles, with_embeddings, avg_quality
    """
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT
                COUNT(*) as total_profiles,
                COUNT(embedding) as with_embeddings,
                ROUND(AVG(content_quality_score)::numeric, 2) as avg_quality,
                COUNT(*) FILTER (WHERE content_quality_score >= 0.7) as high_quality
            FROM profiles
            WHERE is_deleted = FALSE
        """)

        return cur.fetchone()
