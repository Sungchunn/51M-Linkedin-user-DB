"""
INSIGHT - Database Reset Script

This script drops and recreates the database schema with all migrations.
USE WITH CAUTION: This will DELETE ALL DATA.

Negative Spaces Implementation:
- Validates environment before proceeding
- Confirms destructive operations
- Logs all actions with context
- Fails fast on errors
"""

import os
import sys
from pathlib import Path
from typing import List
import psycopg
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Sentinel for uninitialized state
UNINITIALIZED = object()


class DatabaseResetError(Exception):
    """Raised when database reset fails"""
    pass


class EnvironmentError(Exception):
    """Raised when environment is not properly configured"""
    pass


def validate_environment() -> dict:
    """
    Validate required environment variables exist.

    NEGATIVE SPACE CONTRACT:
    - All required vars must be present
    - DSN must be parseable
    - Returns validated config dict

    Raises:
        EnvironmentError: If validation fails
    """
    load_dotenv()

    required_vars = ['PG_DSN', 'PGDATABASE']
    missing = [v for v in required_vars if not os.getenv(v)]

    if missing:
        raise EnvironmentError(
            f"NEGATIVE SPACE VIOLATION: Missing required environment variables: {missing}\\n"
            f"Please ensure .env file exists and contains: {', '.join(required_vars)}"
        )

    config = {
        'dsn': os.getenv('PG_DSN'),
        'database': os.getenv('PGDATABASE'),
        'user': os.getenv('PGUSER', 'postgres'),
        'host': os.getenv('PGHOST', 'localhost'),
        'port': os.getenv('PGPORT', '5433')
    }

    logger.info(f"Environment validated: {config['database']} @ {config['host']}:{config['port']}")
    return config


def get_migration_files(migrations_dir: Path) -> List[Path]:
    """
    Get all SQL migration files in order.

    NEGATIVE SPACE CONTRACT:
    - migrations_dir must exist
    - Must return at least 1 migration file
    - Files must be sorted numerically

    Raises:
        DatabaseResetError: If no migrations found or directory missing
    """
    if not migrations_dir.exists():
        raise DatabaseResetError(
            f"NEGATIVE SPACE VIOLATION: Migrations directory not found: {migrations_dir}\\n"
            f"Expected location: {migrations_dir.absolute()}"
        )

    sql_files = sorted(migrations_dir.glob('*.sql'))

    if not sql_files:
        raise DatabaseResetError(
            f"NEGATIVE SPACE VIOLATION: No migration files found in {migrations_dir}\\n"
            f"Expected files matching pattern: *.sql"
        )

    logger.info(f"Found {len(sql_files)} migration files")
    for f in sql_files:
        logger.debug(f"  - {f.name}")

    return sql_files


def confirm_reset(database: str) -> bool:
    """
    Ask user to confirm destructive operation.

    NEGATIVE SPACE: Must explicitly type 'DELETE' to proceed
    """
    print(f"\\n⚠️  WARNING: This will DELETE ALL DATA in database '{database}'\\n")
    print("This operation is IRREVERSIBLE.")
    print("\\nType 'DELETE' (in capitals) to confirm: ", end='')

    confirmation = input().strip()

    if confirmation != 'DELETE':
        print("\\n❌ Operation cancelled (confirmation did not match 'DELETE')")
        return False

    print("\\n✅ Confirmation received, proceeding with reset...")
    return True


def execute_migration(conn: psycopg.Connection, migration_file: Path):
    """
    Execute a single migration file.

    NEGATIVE SPACE CONTRACT:
    - File must be readable
    - SQL must be valid
    - Transaction must succeed

    Raises:
        DatabaseResetError: If migration fails
    """
    logger.info(f"Executing migration: {migration_file.name}")

    try:
        sql = migration_file.read_text()

        if not sql or sql.strip() == '':
            raise DatabaseResetError(
                f"NEGATIVE SPACE VIOLATION: Migration file is empty: {migration_file.name}"
            )

        with conn.cursor() as cur:
            cur.execute(sql)

        conn.commit()
        logger.info(f"✅ Successfully executed: {migration_file.name}")

    except psycopg.Error as e:
        conn.rollback()
        raise DatabaseResetError(
            f"NEGATIVE SPACE VIOLATION: Migration failed: {migration_file.name}\\n"
            f"PostgreSQL Error: {e}\\n"
            f"SQL may contain syntax errors or constraint violations."
        ) from e


def drop_schema(conn: psycopg.Connection):
    """
    Drop all tables and extensions.

    NEGATIVE SPACE: Ensures clean slate before recreation
    """
    logger.info("Dropping existing schema...")

    try:
        with conn.cursor() as cur:
            # Drop tables in dependency order
            cur.execute("""
                DROP TABLE IF EXISTS profile_certifications CASCADE;
                DROP TABLE IF EXISTS profile_education CASCADE;
                DROP TABLE IF EXISTS profile_experiences CASCADE;
                DROP TABLE IF EXISTS profiles CASCADE;
                DROP TABLE IF EXISTS companies CASCADE;
                DROP TABLE IF EXISTS staging_profiles_raw CASCADE;

                -- Drop extensions (will be recreated)
                DROP EXTENSION IF EXISTS vector CASCADE;
                DROP EXTENSION IF EXISTS pg_trgm CASCADE;
                DROP EXTENSION IF EXISTS "uuid-ossp" CASCADE;
            """)
        conn.commit()
        logger.info("✅ Schema dropped successfully")

    except psycopg.Error as e:
        conn.rollback()
        raise DatabaseResetError(
            f"NEGATIVE SPACE VIOLATION: Failed to drop schema: {e}"
        ) from e


def main():
    """
    Main reset function with full Negative Space validation.
    """
    try:
        # 1. Validate environment
        config = validate_environment()

        # 2. Get migration files
        project_root = Path(__file__).parent.parent.parent.parent
        migrations_dir = project_root / 'migrations'
        migration_files = get_migration_files(migrations_dir)

        # 3. Confirm destructive operation
        if '--force' not in sys.argv:
            if not confirm_reset(config['database']):
                sys.exit(0)

        # 4. Connect to database
        logger.info(f"Connecting to database: {config['dsn']}")
        with psycopg.connect(config['dsn']) as conn:
            logger.info("✅ Database connection established")

            # 5. Drop existing schema
            drop_schema(conn)

            # 6. Execute migrations in order
            for migration_file in migration_files:
                execute_migration(conn, migration_file)

            # 7. Verify schema
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    ORDER BY table_name;
                """)
                tables = [row[0] for row in cur.fetchall()]

            logger.info(f"\\n✅ Database reset complete!")
            logger.info(f"Created {len(tables)} tables: {', '.join(tables)}")

    except (EnvironmentError, DatabaseResetError) as e:
        logger.error(f"❌ Reset failed: {e}")
        sys.exit(1)

    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
