"""
INSIGHT - Cloud Ingestion Worker (Tier 3)
Distributed worker for processing large-scale ingestion jobs

Architecture:
- Reads jobs from SQS queue
- Streams Parquet chunks from S3
- Uses Redis bloom filter for deduplication
- Writes to PostgreSQL RDS
- Reports progress to coordinator

Usage (local testing):
    python -m backend.data_pipeline.ingestion.cloud_worker

Deployment (ECS Fargate):
    - Docker image with this worker
    - Auto-scales based on SQS queue depth
    - Each task processes one chunk at a time
"""

import os
import sys
import asyncio
import logging
from typing import Dict, Optional
from dataclasses import dataclass
import asyncpg
from dotenv import load_dotenv

# Cloud dependencies (install for production deployment)
try:
    import boto3
    import redis.asyncio as redis
    from pyarrow import fs as pafs
    import pyarrow.parquet as pq
    CLOUD_DEPS_AVAILABLE = True
except ImportError:
    CLOUD_DEPS_AVAILABLE = False
    logging.warning("Cloud dependencies not installed. Install with: poetry add boto3 redis pyarrow-s3fs")

from backend.data_pipeline.ingestion import validators as val
from backend.data_pipeline.ingestion.load_to_core import transform_staging_row

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class IngestionJob:
    """Job definition for processing a chunk of data"""
    job_id: str
    s3_path: str
    start_row: int
    end_row: int
    chunk_id: str
    batch_size: int = 10000


class CloudIngestionWorker:
    """
    Cloud worker for distributed ingestion

    Features:
    - Streams Parquet from S3 (no full download)
    - Redis bloom filter for deduplication
    - AsyncPG for high-performance inserts
    - Progress tracking and error reporting
    """

    def __init__(
        self,
        pg_dsn: str,
        redis_url: str,
        aws_region: str = 'us-east-1',
        sqs_queue_url: Optional[str] = None
    ):
        self.pg_dsn = pg_dsn
        self.redis_url = redis_url
        self.aws_region = aws_region
        self.sqs_queue_url = sqs_queue_url

        # Will be initialized in async context
        self.pg_pool: Optional[asyncpg.Pool] = None
        self.redis_client: Optional[redis.Redis] = None
        self.s3_client: Optional[boto3.client] = None
        self.sqs_client: Optional[boto3.client] = None

    async def initialize(self):
        """Initialize async connections"""
        if not CLOUD_DEPS_AVAILABLE:
            raise RuntimeError("Cloud dependencies not installed")

        # PostgreSQL connection pool
        self.pg_pool = await asyncpg.create_pool(
            self.pg_dsn,
            min_size=2,
            max_size=5,
            command_timeout=60
        )
        logger.info("✅ Connected to PostgreSQL")

        # Redis client
        self.redis_client = await redis.from_url(
            self.redis_url,
            encoding='utf-8',
            decode_responses=True
        )
        logger.info("✅ Connected to Redis")

        # AWS clients (sync, used in thread pool)
        self.s3_client = boto3.client('s3', region_name=self.aws_region)
        if self.sqs_queue_url:
            self.sqs_client = boto3.client('sqs', region_name=self.aws_region)
        logger.info("✅ Connected to AWS")

    async def close(self):
        """Close connections"""
        if self.pg_pool:
            await self.pg_pool.close()
        if self.redis_client:
            await self.redis_client.close()

    async def check_duplicate(self, linkedin_username: str) -> bool:
        """
        Check if profile already exists using Redis bloom filter

        Returns:
            True if duplicate, False if new
        """
        # Check bloom filter (O(1), very fast)
        try:
            # Note: Requires Redis with RedisBloom module
            # Alternative: Use regular Redis SET with TTL for deduplication
            exists = await self.redis_client.execute_command(
                'BF.EXISTS',
                'linkedin_usernames',
                linkedin_username.lower()
            )
            return bool(exists)
        except Exception as e:
            logger.warning(f"Bloom filter check failed: {e}, falling back to SET")
            # Fallback: Use Redis SET
            return await self.redis_client.sismember('linkedin_usernames', linkedin_username.lower())

    async def mark_as_seen(self, linkedin_username: str):
        """Add username to deduplication cache"""
        try:
            await self.redis_client.execute_command(
                'BF.ADD',
                'linkedin_usernames',
                linkedin_username.lower()
            )
        except Exception:
            # Fallback: Use Redis SET
            await self.redis_client.sadd('linkedin_usernames', linkedin_username.lower())

    async def bulk_insert_profiles(
        self,
        conn: asyncpg.Connection,
        profiles: list
    ) -> int:
        """
        Bulk insert profiles using asyncpg COPY

        Returns:
            Number of profiles inserted
        """
        if not profiles:
            return 0

        # Prepare data for COPY
        rows = []
        for p in profiles:
            rows.append((
                p.get('linkedin_username'),
                p.get('full_name'),
                p.get('first_name'),
                p.get('last_name'),
                p.get('job_title'),
                p.get('company_name'),
                p.get('industry'),
                p.get('location'),
                p.get('location_country'),
                p.get('region'),
                p.get('locality'),
                p.get('skills', []),
                p.get('years_experience'),
                p.get('headline'),
                p.get('summary'),
                p.get('linkedin_url'),
                p.get('email'),
                p.get('phone'),
                p.get('website'),
                p.get('twitter'),
                p.get('github'),
                p.get('content_quality_score', 0.0)
            ))

        # Use COPY for maximum performance
        try:
            inserted = await conn.copy_records_to_table(
                'profiles',
                records=rows,
                columns=[
                    'linkedin_username', 'full_name', 'first_name', 'last_name',
                    'job_title', 'company_name', 'industry', 'location',
                    'location_country', 'region', 'locality', 'skills',
                    'years_experience', 'headline', 'summary', 'linkedin_url',
                    'email', 'phone', 'website', 'twitter', 'github',
                    'content_quality_score'
                ]
            )
            return len(rows)
        except Exception as e:
            logger.error(f"Bulk insert failed: {e}")
            # Try individual inserts as fallback
            success_count = 0
            for row in rows:
                try:
                    await conn.execute("""
                        INSERT INTO profiles (...)
                        VALUES ($1, $2, ...)
                        ON CONFLICT (linkedin_username) DO NOTHING
                    """, *row)
                    success_count += 1
                except Exception:
                    pass
            return success_count

    async def process_chunk(self, job: IngestionJob) -> Dict:
        """
        Process a chunk of Parquet data from S3

        Returns:
            Statistics dict
        """
        logger.info(f"📦 Processing chunk {job.chunk_id}: rows {job.start_row:,} to {job.end_row:,}")

        stats = {
            'processed': 0,
            'loaded': 0,
            'duplicates': 0,
            'failed': 0
        }

        try:
            # Stream Parquet from S3 (memory efficient)
            s3_fs = pafs.S3FileSystem()
            parquet_file = pq.ParquetFile(s3_fs.open_input_file(job.s3_path))

            # Iterate batches
            batch_num = 0
            rows_read = 0

            async with self.pg_pool.acquire() as conn:
                async with conn.transaction():
                    for batch_table in parquet_file.iter_batches(
                        batch_size=job.batch_size,
                        columns=None  # Read all columns
                    ):
                        # Skip rows before start_row
                        if rows_read < job.start_row:
                            rows_read += len(batch_table)
                            continue

                        # Stop if we've reached end_row
                        if rows_read >= job.end_row:
                            break

                        # Process batch
                        staging_rows = batch_table.to_pylist()
                        profiles_to_insert = []

                        for staging_row in staging_rows:
                            try:
                                # Transform
                                core_row = transform_staging_row(staging_row)
                                if not core_row:
                                    stats['failed'] += 1
                                    continue

                                # Validate quality
                                quality_score = val.calculate_quality_score(core_row)
                                if quality_score < 0.5:
                                    stats['failed'] += 1
                                    continue

                                core_row['content_quality_score'] = quality_score

                                # Check duplicate via Redis
                                username = core_row.get('linkedin_username')
                                if not username:
                                    stats['failed'] += 1
                                    continue

                                is_duplicate = await self.check_duplicate(username)
                                if is_duplicate:
                                    stats['duplicates'] += 1
                                    continue

                                # Add to batch and mark as seen
                                profiles_to_insert.append(core_row)
                                await self.mark_as_seen(username)

                            except Exception as e:
                                logger.debug(f"Transform error: {e}")
                                stats['failed'] += 1

                        # Bulk insert batch
                        if profiles_to_insert:
                            inserted = await self.bulk_insert_profiles(conn, profiles_to_insert)
                            stats['loaded'] += inserted

                        stats['processed'] += len(staging_rows)
                        rows_read += len(staging_rows)
                        batch_num += 1

                        # Log progress every 10 batches
                        if batch_num % 10 == 0:
                            logger.info(
                                f"  📊 Batch {batch_num}: "
                                f"✅ {stats['loaded']:,} loaded | "
                                f"⏭️ {stats['duplicates']:,} dups | "
                                f"❌ {stats['failed']:,} failed"
                            )

            # Update Redis with progress
            await self.redis_client.hincrby(f'ingestion:{job.job_id}:progress', 'loaded', stats['loaded'])
            await self.redis_client.hincrby(f'ingestion:{job.job_id}:progress', 'duplicates', stats['duplicates'])
            await self.redis_client.hincrby(f'ingestion:{job.job_id}:progress', 'failed', stats['failed'])

            logger.info(f"✅ Chunk {job.chunk_id} complete: {stats}")
            return stats

        except Exception as e:
            logger.error(f"❌ Chunk {job.chunk_id} failed: {e}", exc_info=True)
            stats['failed'] += 1
            return stats

    async def poll_sqs_and_process(self):
        """
        Poll SQS queue for jobs and process them (for cloud deployment)
        """
        if not self.sqs_client or not self.sqs_queue_url:
            logger.error("SQS not configured")
            return

        logger.info(f"👀 Polling SQS queue: {self.sqs_queue_url}")

        while True:
            try:
                # Poll for messages
                response = self.sqs_client.receive_message(
                    QueueUrl=self.sqs_queue_url,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=20,
                    VisibilityTimeout=3600  # 1 hour to process
                )

                messages = response.get('Messages', [])
                if not messages:
                    logger.info("No messages, waiting...")
                    await asyncio.sleep(5)
                    continue

                # Process message
                message = messages[0]
                receipt_handle = message['ReceiptHandle']
                body = eval(message['Body'])  # Parse job JSON

                # Create job object
                job = IngestionJob(**body)

                # Process chunk
                stats = await self.process_chunk(job)

                # Delete message from queue (mark as complete)
                self.sqs_client.delete_message(
                    QueueUrl=self.sqs_queue_url,
                    ReceiptHandle=receipt_handle
                )

                logger.info(f"✅ Job complete, message deleted from queue")

            except Exception as e:
                logger.error(f"❌ Error processing SQS message: {e}", exc_info=True)
                await asyncio.sleep(5)


async def main():
    """Entry point for worker"""
    load_dotenv()

    # Configuration from environment
    pg_dsn = os.getenv('PG_DSN')
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    aws_region = os.getenv('AWS_REGION', 'us-east-1')
    sqs_queue_url = os.getenv('SQS_QUEUE_URL')

    if not pg_dsn:
        logger.error("PG_DSN environment variable required")
        sys.exit(1)

    logger.info("=" * 70)
    logger.info("☁️  INSIGHT - Cloud Ingestion Worker (Tier 3)")
    logger.info("=" * 70)
    logger.info(f"PostgreSQL: {pg_dsn.split('@')[1] if '@' in pg_dsn else 'configured'}")
    logger.info(f"Redis: {redis_url}")
    logger.info(f"AWS Region: {aws_region}")
    logger.info("")

    # Initialize worker
    worker = CloudIngestionWorker(
        pg_dsn=pg_dsn,
        redis_url=redis_url,
        aws_region=aws_region,
        sqs_queue_url=sqs_queue_url
    )

    try:
        await worker.initialize()

        if sqs_queue_url:
            # Production mode: Poll SQS
            logger.info("🚀 Starting SQS polling mode...")
            await worker.poll_sqs_and_process()
        else:
            # Test mode: Process single test job
            logger.info("🧪 Test mode: Processing sample job...")
            test_job = IngestionJob(
                job_id='test_001',
                s3_path='s3://bucket/test.parquet',  # Replace with actual path
                start_row=0,
                end_row=10000,
                chunk_id='test_chunk_001'
            )
            stats = await worker.process_chunk(test_job)
            logger.info(f"Test complete: {stats}")

    except KeyboardInterrupt:
        logger.info("⏹️  Shutting down gracefully...")
    except Exception as e:
        logger.error(f"❌ Worker error: {e}", exc_info=True)
    finally:
        await worker.close()


if __name__ == '__main__':
    if not CLOUD_DEPS_AVAILABLE:
        print("❌ Cloud dependencies not installed.")
        print("Install with: poetry add boto3 'redis[hiredis]' pyarrow")
        sys.exit(1)

    asyncio.run(main())
