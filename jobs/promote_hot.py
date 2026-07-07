"""
INSIGHT - Promote to Hot Job
Calculates hotness scores and promotes/demotes profiles based on:
- Quality score (α = 50)
- Recency (β = 5-30)
- Completeness (γ = 20)
- Engagement (δ = query/click counts)

Run frequency: Daily or after large data loads
"""

import os
import sys
from pathlib import Path
from typing import Optional
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
import logging
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def calculate_hotness_scores(
    conn: psycopg.Connection,
    top_n: Optional[int] = None
):
    """
    Calculate hotness scores for all profiles.

    Formula:
    hotness = α * quality_score
            + β * recency_score
            + γ * completeness_score
            + δ * engagement_score

    Where:
    - α (quality): 50 points for quality_score (0-1 → 0-50)
    - β (recency): 30 for <30d, 15 for <90d, 5 for older
    - γ (completeness): 20 for rich profiles (10+ skills)
    - δ (engagement): query_count_7d + click_count_7d * 2

    Args:
        conn: Database connection
        top_n: Optional limit to top N profiles (for testing)
    """
    logger.info("Calculating hotness scores...")

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE profiles_hot
            SET hotness_score = (
                -- α: Quality (0-50)
                COALESCE(quality_score, 0) * 50 +

                -- β: Recency (5-30)
                CASE
                    WHEN updated_at > NOW() - INTERVAL '30 days' THEN 30
                    WHEN updated_at > NOW() - INTERVAL '90 days' THEN 15
                    ELSE 5
                END +

                -- γ: Completeness (0-20)
                CASE
                    WHEN top_skills IS NOT NULL AND array_length(top_skills, 1) >= 10 THEN 20
                    WHEN top_skills IS NOT NULL AND array_length(top_skills, 1) >= 5 THEN 10
                    ELSE 0
                END +

                -- δ: Engagement (query + click*2)
                COALESCE(query_count_7d, 0) + COALESCE(click_count_7d, 0) * 2
            ),
            last_promoted_at = NOW()
            WHERE is_deleted = FALSE
        """)

        affected = cur.rowcount
        conn.commit()

    logger.info(f"✅ Updated hotness scores for {affected:,} profiles")


def promote_top_profiles(
    conn: psycopg.Connection,
    target_count: int = 5000000,
    min_quality: float = 0.5
):
    """
    Promote top N profiles to hot table (soft delete rest).

    Strategy:
    1. Calculate hotness for all profiles
    2. Rank by hotness_score
    3. Keep top N, soft-delete rest (is_deleted = TRUE)
    4. Log promotions/demotions to hot_audit

    Args:
        conn: Database connection
        target_count: Target hot profiles (default 5M)
        min_quality: Minimum quality threshold
    """
    logger.info(f"Promoting top {target_count:,} profiles (min_quality={min_quality})...")

    # Get current counts
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE is_deleted = FALSE) as active_count,
                COUNT(*) as total_count
            FROM profiles_hot
        """)
        stats = cur.fetchone()

    logger.info(
        f"Current: {stats['active_count']:,} active / {stats['total_count']:,} total"
    )

    # Calculate hotness
    calculate_hotness_scores(conn)

    # Create temp ranking table
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TEMP TABLE hotness_rank AS
            SELECT
                id,
                hotness_score,
                ROW_NUMBER() OVER (ORDER BY hotness_score DESC, updated_at DESC) as rank
            FROM profiles_hot
            WHERE quality_score >= %s
        """, (min_quality,))

        conn.commit()

    logger.info("Ranked profiles by hotness")

    # Promote top N (mark as active)
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE profiles_hot
            SET is_deleted = FALSE
            WHERE id IN (
                SELECT id FROM hotness_rank
                WHERE rank <= %s
            )
            AND is_deleted = TRUE
        """, (target_count,))

        promoted = cur.rowcount
        conn.commit()

    logger.info(f"Promoted {promoted:,} profiles to hot")

    # Demote rest (soft delete)
    with conn.cursor() as cur:
        cur.execute("""
            UPDATE profiles_hot
            SET is_deleted = TRUE
            WHERE id IN (
                SELECT id FROM hotness_rank
                WHERE rank > %s
            )
            AND is_deleted = FALSE
        """, (target_count,))

        demoted = cur.rowcount
        conn.commit()

    logger.info(f"Demoted {demoted:,} profiles from hot")

    # Log to audit table
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO hot_audit (action, affected_count, details)
            VALUES ('promote_hot', %s, jsonb_build_object(
                'promoted', %s,
                'demoted', %s,
                'target_count', %s,
                'min_quality', %s
            ))
        """, (promoted + demoted, promoted, demoted, target_count, min_quality))

        conn.commit()

    logger.info("Logged to hot_audit")

    # Get final stats
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE is_deleted = FALSE) as active_count,
                COUNT(*) as total_count,
                AVG(hotness_score) FILTER (WHERE is_deleted = FALSE) as avg_hotness,
                MIN(hotness_score) FILTER (WHERE is_deleted = FALSE) as min_hotness,
                MAX(hotness_score) FILTER (WHERE is_deleted = FALSE) as max_hotness
            FROM profiles_hot
        """)
        final_stats = cur.fetchone()

    logger.info(f"""
✅ Promotion complete!
  Active profiles: {final_stats['active_count']:,}
  Avg hotness: {final_stats['avg_hotness']:.2f}
  Min hotness: {final_stats['min_hotness']:.2f}
  Max hotness: {final_stats['max_hotness']:.2f}
    """)


def reset_weekly_counters(conn: psycopg.Connection):
    """Reset query/click counters (run weekly)"""
    logger.info("Resetting weekly counters...")

    with conn.cursor() as cur:
        cur.execute("""
            UPDATE profiles_hot
            SET query_count_7d = 0,
                click_count_7d = 0
            WHERE query_count_7d > 0 OR click_count_7d > 0
        """)

        affected = cur.rowcount
        conn.commit()

    logger.info(f"✅ Reset counters for {affected:,} profiles")


def main():
    """CLI entry point"""
    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python promote_hot.py calculate")
        print("  python promote_hot.py promote [--target 5000000] [--min-quality 0.5]")
        print("  python promote_hot.py reset-counters")
        sys.exit(1)

    action = sys.argv[1]

    # Get DSN
    dsn = os.getenv("PG_DSN")
    if not dsn:
        logger.error("PG_DSN not set")
        sys.exit(1)

    try:
        with psycopg.connect(dsn) as conn:
            if action == "calculate":
                calculate_hotness_scores(conn)

            elif action == "promote":
                # Parse options
                target_count = 5000000
                min_quality = 0.5

                for i, arg in enumerate(sys.argv[2:], start=2):
                    if arg == "--target" and i + 1 < len(sys.argv):
                        target_count = int(sys.argv[i + 1])
                    elif arg == "--min-quality" and i + 1 < len(sys.argv):
                        min_quality = float(sys.argv[i + 1])

                promote_top_profiles(conn, target_count, min_quality)

            elif action == "reset-counters":
                reset_weekly_counters(conn)

            else:
                logger.error(f"Unknown action: {action}")
                sys.exit(1)

        logger.info("🎉 Success!")
        sys.exit(0)

    except Exception as e:
        logger.error(f"❌ Failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
