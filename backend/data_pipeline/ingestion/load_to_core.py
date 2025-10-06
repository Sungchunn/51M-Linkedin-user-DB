"""
INSIGHT - Staging to Core Loader
Transforms and loads data from staging_profiles_raw to core tables

Negative Spaces Implementation:
- Validates all transformations
- Skips invalid rows with logging
- Uses UPSERT for duplicate handling
- Tracks quality scores
- Enforces database constraints
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
import logging
from tqdm import tqdm

# Import transformation and validation modules
from backend.data_pipeline.ingestion import transformers as tf
from backend.data_pipeline.ingestion import validators as val

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CoreLoadError(Exception):
    """Raised when core table loading fails"""
    pass


def transform_staging_row(staging_row: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform a staging row to core schema format.

    NEGATIVE SPACE CONTRACT:
    - Returns None for rows that fail transformation
    - Logs transformation failures
    - Preserves NULL values

    Args:
        staging_row: Raw row from staging_profiles_raw

    Returns:
        Transformed row dict or None if transformation fails
    """
    try:
        # Parse skills
        skills_raw = staging_row.get('Skills')
        skills = tf.parse_skills(skills_raw)
        skills_normalized = [tf.normalize_skill(s) for s in skills]

        # Parse geographic fields (USA_filtered.parquet format)
        geo = tf.map_geo_fields({
            'Location': staging_row.get('Location'),
            'Locality': staging_row.get('Locality'),
            'Region': staging_row.get('Region'),
            'Location Country': staging_row.get('Location Country'),
        })

        # Parse email from "Emails" column (may contain multiple, comma-separated)
        emails_raw = staging_row.get('Emails')
        email = None
        if emails_raw:
            # Split by comma and take first valid email
            email_list = [e.strip() for e in str(emails_raw).split(',')]
            for e in email_list:
                validated = tf.validate_email(e)
                if validated:
                    email = validated
                    break

        # Parse phone from multiple sources
        phone = staging_row.get('Mobile') or staging_row.get('Phone numbers')

        # Build core row
        core_row = {
            # Identity
            'full_name': tf.clean_text_field(staging_row.get('Full name')),
            'first_name': tf.clean_text_field(staging_row.get('First Name')),
            'last_name': tf.clean_text_field(staging_row.get('Last Name')),
            'linkedin_url': tf.clean_text_field(staging_row.get('LinkedIn Url')),
            'linkedin_username': tf.validate_linkedin_username(staging_row.get('LinkedIn Username')),

            # Professional
            'job_title': tf.clean_text_field(staging_row.get('Job title')),
            'company_name': tf.clean_text_field(staging_row.get('Company Name')),
            'industry': tf.clean_text_field(staging_row.get('Industry')),
            'years_experience': tf.parse_years_experience(staging_row.get('Years Experience')),

            # Location
            'location': geo['location'],
            'locality': geo['locality'],
            'region': geo['region'],
            'location_country': geo['location_country'],

            # Skills
            'skills': skills if skills else None,
            'skills_normalized': skills_normalized if skills_normalized else None,

            # Profile content
            'headline': tf.clean_text_field(staging_row.get('Headline'), max_length=500),
            'summary': tf.clean_text_field(staging_row.get('Summary'), max_length=5000),

            # Contact
            'email': email,
            'phone': tf.clean_text_field(phone),
            'website': tf.clean_text_field(staging_row.get('Company Website')),

            # Social
            'twitter': tf.clean_text_field(staging_row.get('Twitter Username')),
            'github': tf.clean_text_field(staging_row.get('Github Username')),

            # Metadata (embedding added later in Phase 3)
            'embedding': None,
        }

        # Calculate quality score
        core_row['content_quality_score'] = val.calculate_quality_score(core_row)

        # Calculate profile completeness (0-100)
        completeness_raw = staging_row.get('Profile Completeness')
        if completeness_raw:
            try:
                # Handle percentage strings like "85%"
                completeness_str = str(completeness_raw).strip().replace('%', '')
                completeness = int(float(completeness_str))
                core_row['profile_completeness'] = max(0, min(100, completeness))
            except (ValueError, TypeError):
                core_row['profile_completeness'] = None
        else:
            core_row['profile_completeness'] = None

        return core_row

    except Exception as e:
        username = staging_row.get('LinkedIn Username', 'UNKNOWN')
        logger.error(
            f"NEGATIVE SPACE: Failed to transform row for username={username}: {e}",
            exc_info=True
        )
        return None


def insert_profile(conn: psycopg.Connection, row: Dict[str, Any]) -> bool:
    """
    Insert or update profile in core table using UPSERT.

    NEGATIVE SPACE CONTRACT:
    - Uses ON CONFLICT to handle duplicates
    - Updates existing records with latest data
    - Returns True if successful, False otherwise

    Args:
        conn: Database connection
        row: Transformed row dict

    Returns:
        Success boolean
    """
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO profiles (
                    full_name, first_name, last_name, linkedin_url, linkedin_username,
                    job_title, company_name, industry, years_experience,
                    location, locality, region, location_country,
                    skills, skills_normalized,
                    headline, summary,
                    email, phone, website,
                    twitter, github,
                    embedding,
                    content_quality_score, profile_completeness,
                    updated_at
                )
                VALUES (
                    %(full_name)s, %(first_name)s, %(last_name)s, %(linkedin_url)s, %(linkedin_username)s,
                    %(job_title)s, %(company_name)s, %(industry)s, %(years_experience)s,
                    %(location)s, %(locality)s, %(region)s, %(location_country)s,
                    %(skills)s, %(skills_normalized)s,
                    %(headline)s, %(summary)s,
                    %(email)s, %(phone)s, %(website)s,
                    %(twitter)s, %(github)s,
                    %(embedding)s,
                    %(content_quality_score)s, %(profile_completeness)s,
                    NOW()
                )
                ON CONFLICT (linkedin_username)
                DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    first_name = EXCLUDED.first_name,
                    last_name = EXCLUDED.last_name,
                    linkedin_url = EXCLUDED.linkedin_url,
                    job_title = EXCLUDED.job_title,
                    company_name = EXCLUDED.company_name,
                    industry = EXCLUDED.industry,
                    years_experience = EXCLUDED.years_experience,
                    location = EXCLUDED.location,
                    locality = EXCLUDED.locality,
                    region = EXCLUDED.region,
                    location_country = EXCLUDED.location_country,
                    skills = EXCLUDED.skills,
                    skills_normalized = EXCLUDED.skills_normalized,
                    headline = EXCLUDED.headline,
                    summary = EXCLUDED.summary,
                    email = EXCLUDED.email,
                    phone = EXCLUDED.phone,
                    website = EXCLUDED.website,
                    twitter = EXCLUDED.twitter,
                    github = EXCLUDED.github,
                    content_quality_score = EXCLUDED.content_quality_score,
                    profile_completeness = EXCLUDED.profile_completeness,
                    updated_at = NOW()
            """, row)

        return True

    except psycopg.Error as e:
        logger.error(
            f"NEGATIVE SPACE: Failed to insert profile {row.get('linkedin_username')}: {e}"
        )
        return False


def load_staging_to_core(
    dsn: str,
    batch_size: int = 5000,
    batch_id_filter: Optional[str] = None
) -> Tuple[int, int]:
    """
    Load all staging data to core tables.

    NEGATIVE SPACE CONTRACT:
    - Processes in batches for memory efficiency
    - Skips invalid rows with logging
    - Uses transactions for consistency
    - Returns (success_count, skip_count)

    Args:
        dsn: PostgreSQL connection string
        batch_size: Number of rows to process per batch
        batch_id_filter: Optional filter for specific batch IDs (LIKE pattern)

    Returns:
        Tuple of (successful_loads, skipped_rows)

    Raises:
        CoreLoadError: If critical error occurs
    """
    if batch_size <= 0:
        raise CoreLoadError(
            f"NEGATIVE SPACE VIOLATION: batch_size must be > 0, got {batch_size}"
        )

    logger.info("Starting staging → core transformation")

    try:
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            # Get total count
            with conn.cursor() as cur:
                if batch_id_filter:
                    cur.execute(
                        "SELECT count(*) FROM staging_profiles_raw WHERE import_batch_id LIKE %s",
                        (batch_id_filter,)
                    )
                else:
                    cur.execute("SELECT count(*) FROM staging_profiles_raw")

                total_rows = cur.fetchone()['count']

            if total_rows == 0:
                logger.warning("NEGATIVE SPACE: No rows found in staging table")
                return 0, 0

            logger.info(f"Processing {total_rows:,} rows from staging")

            success_count = 0
            skip_count = 0

            # Process in batches
            with tqdm(total=total_rows, desc="Transforming rows", unit="rows") as pbar:
                offset = 0

                while offset < total_rows:
                    # Fetch batch
                    with conn.cursor() as cur:
                        if batch_id_filter:
                            cur.execute(
                                """
                                SELECT * FROM staging_profiles_raw
                                WHERE import_batch_id LIKE %s
                                ORDER BY import_timestamp
                                LIMIT %s OFFSET %s
                                """,
                                (batch_id_filter, batch_size, offset)
                            )
                        else:
                            cur.execute(
                                """
                                SELECT * FROM staging_profiles_raw
                                ORDER BY import_timestamp
                                LIMIT %s OFFSET %s
                                """,
                                (batch_size, offset)
                            )

                        batch = cur.fetchall()

                    if not batch:
                        break

                    # Transform and load batch
                    for staging_row in batch:
                        # Transform
                        core_row = transform_staging_row(staging_row)

                        if core_row is None:
                            skip_count += 1
                            pbar.update(1)
                            continue

                        # Validate
                        should_skip, reason = val.should_skip_row(core_row)

                        if should_skip:
                            skip_count += 1
                            logger.debug(f"Skipping row: {reason}")
                            pbar.update(1)
                            continue

                        # Insert to core
                        if insert_profile(conn, core_row):
                            success_count += 1
                        else:
                            skip_count += 1

                        pbar.update(1)

                    # Commit batch
                    conn.commit()

                    offset += len(batch)

            logger.info(
                f"✅ Core load complete: {success_count:,} rows loaded, {skip_count:,} rows skipped"
            )

            return success_count, skip_count

    except psycopg.Error as e:
        raise CoreLoadError(
            f"NEGATIVE SPACE VIOLATION: Database error during core load: {e}"
        ) from e


def main():
    """
    Main entry point for CLI execution.
    """
    load_dotenv()

    # Get environment variables
    dsn = os.getenv('PG_DSN')
    if not dsn:
        logger.error("NEGATIVE SPACE VIOLATION: PG_DSN environment variable not set")
        sys.exit(1)

    # Get batch size
    batch_size = int(os.getenv('BATCH_SIZE', '5000'))

    # Get optional batch filter from command line
    batch_id_filter = sys.argv[1] if len(sys.argv) > 1 else None

    try:
        success, skipped = load_staging_to_core(
            dsn=dsn,
            batch_size=batch_size,
            batch_id_filter=batch_id_filter
        )

        logger.info(
            f"🎉 Success! {success:,} profiles loaded to core tables, {skipped:,} skipped"
        )

        sys.exit(0)

    except CoreLoadError as e:
        logger.error(f"❌ Core load failed: {e}")
        sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
