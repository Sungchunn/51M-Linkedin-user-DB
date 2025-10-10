"""
INSIGHT - Migrate Existing Profiles to Hot/Detail Schema
Preserves existing embeddings and migrates to optimized hot/detail tables
"""

import os
import sys
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
import logging
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_hot_detail_tables(conn):
    """Create profiles_hot and profiles_detail tables if they don't exist"""
    logger.info("Creating hot/detail schema tables...")

    with conn.cursor() as cur:
        # Read schema from sql/02_schema.sql
        schema_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'sql', '02_schema.sql'
        )

        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        cur.execute(schema_sql)
        conn.commit()

    logger.info("✅ Hot/detail tables created")


def migrate_profiles_to_hot_detail(dsn: str, batch_size: int = 5000):
    """
    Migrate existing profiles to hot/detail schema.

    Strategy:
    1. Select from profiles table
    2. Split data into hot (narrow fields) and detail (long fields)
    3. Insert into profiles_hot and profiles_detail
    """
    logger.info("Starting migration from profiles → hot/detail schema...")

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        # Get total count
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM profiles WHERE is_deleted = FALSE")
            total = cur.fetchone()['count']

        if total == 0:
            logger.warning("No profiles to migrate")
            return

        logger.info(f"Found {total:,} profiles to migrate")

        migrated = 0
        skipped = 0

        with tqdm(total=total, desc="Migrating", unit=" profiles") as pbar:
            offset = 0

            while offset < total:
                # Fetch batch
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT
                            id,
                            linkedin_username,
                            full_name,
                            job_title,
                            company_name,
                            headline,
                            location_country,
                            industry,
                            -- Note: seniority_level doesn't exist in old schema
                            years_experience,
                            skills,
                            embedding,
                            content_quality_score,
                            summary,
                            email,
                            phone,
                            website,
                            twitter,
                            github,
                            profile_completeness
                        FROM profiles
                        WHERE is_deleted = FALSE
                        ORDER BY created_at
                        LIMIT %s OFFSET %s
                    """, (batch_size, offset))

                    batch = cur.fetchall()

                if not batch:
                    break

                # Insert into hot/detail tables
                for row in batch:
                    try:
                        # Prepare hot table data (narrow fields)
                        hot_data = {
                            'id': row['id'],
                            'linkedin_username': row['linkedin_username'],
                            'full_name': row['full_name'],
                            'job_title': row['job_title'],
                            'company_name': row['company_name'],
                            'headline': row['headline'][:500] if row['headline'] else None,  # Truncate
                            'location_country': row['location_country'],
                            'industry': row['industry'],
                            'seniority_level': None,  # Will need to infer or leave NULL
                            'years_experience': row['years_experience'],
                            'top_skills': row['skills'][:10] if row['skills'] else None,  # Top 10 only
                            'embedding': row['embedding'],  # Preserve existing embeddings!
                            'quality_score': row['content_quality_score']
                        }

                        # Prepare detail table data (long fields)
                        detail_data = {
                            'id': row['id'],
                            'summary': row['summary'],
                            'email': row['email'],
                            'phone': row['phone'],
                            'website': row['website'],
                            'twitter': row['twitter'],
                            'github': row['github'],
                            'all_skills': row['skills'],
                            'profile_completeness': row['profile_completeness'],
                            'experience_json': None,  # Not in old schema
                            'education_json': None   # Not in old schema
                        }

                        # Insert into profiles_hot
                        with conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO profiles_hot (
                                    id, linkedin_username, full_name, job_title, company_name,
                                    headline, location_country, industry, seniority_level,
                                    years_experience, top_skills, embedding, quality_score
                                )
                                VALUES (
                                    %(id)s, %(linkedin_username)s, %(full_name)s, %(job_title)s,
                                    %(company_name)s, %(headline)s, %(location_country)s,
                                    %(industry)s, %(seniority_level)s, %(years_experience)s,
                                    %(top_skills)s, %(embedding)s, %(quality_score)s
                                )
                                ON CONFLICT (linkedin_username) DO NOTHING
                            """, hot_data)

                        # Insert into profiles_detail
                        with conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO profiles_detail (
                                    id, summary, email, phone, website, twitter, github,
                                    all_skills, profile_completeness,
                                    experience_json, education_json
                                )
                                VALUES (
                                    %(id)s, %(summary)s, %(email)s, %(phone)s, %(website)s,
                                    %(twitter)s, %(github)s, %(all_skills)s,
                                    %(profile_completeness)s, %(experience_json)s,
                                    %(education_json)s
                                )
                                ON CONFLICT (id) DO NOTHING
                            """, detail_data)

                        migrated += 1

                    except Exception as e:
                        logger.error(f"Failed to migrate {row['linkedin_username']}: {e}")
                        skipped += 1

                    pbar.update(1)

                # Commit batch
                conn.commit()
                offset += len(batch)

        logger.info(f"✅ Migration complete: {migrated:,} migrated, {skipped:,} skipped")

        # Report on embeddings
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM profiles_hot WHERE embedding IS NOT NULL")
            embedded_count = cur.fetchone()['count']

        logger.info(f"📊 Embeddings preserved: {embedded_count:,}/{migrated:,} profiles")


def main():
    load_dotenv()

    dsn = os.getenv('PG_DSN')
    if not dsn:
        logger.error("PG_DSN not set in environment")
        sys.exit(1)

    try:
        with psycopg.connect(dsn) as conn:
            # Step 1: Create tables
            create_hot_detail_tables(conn)

            # Step 2: Migrate data
            migrate_profiles_to_hot_detail(dsn)

        logger.info("🎉 Migration complete!")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
