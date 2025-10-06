"""
INSIGHT - Phase 0 Test Suite
Tests foundation infrastructure setup
"""

import os
import psycopg
from dotenv import load_dotenv
import pytest


class TestPhase0:
    """Phase 0: Foundation & Infrastructure Setup"""

    def test_tc_0_2_pgvector_extension(self):
        """TC-0.2: pgvector Extension Available"""
        load_dotenv()
        dsn = os.getenv("PG_DSN")

        if not dsn:
            pytest.skip("PG_DSN not set, skipping database tests")

        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT extname FROM pg_extension WHERE extname = 'vector'
                """)
                result = cur.fetchone()

                assert result is not None, \
                    "NEGATIVE SPACE VIOLATION: vector extension not found"
                assert result[0] == 'vector', \
                    f"NEGATIVE SPACE VIOLATION: Expected 'vector', got {result[0]}"

    def test_tc_0_3_database_connection(self):
        """TC-0.3: Database Connection from Python"""
        load_dotenv()
        dsn = os.getenv("PG_DSN")

        if not dsn:
            pytest.skip("PG_DSN not set, skipping database tests")

        try:
            with psycopg.connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    version = cur.fetchone()[0]

                    assert "PostgreSQL" in version, \
                        f"NEGATIVE SPACE VIOLATION: Not PostgreSQL: {version}"

                    print(f"✅ Connected: {version}")

        except Exception as e:
            raise RuntimeError(
                f"NEGATIVE SPACE VIOLATION: Cannot connect to DB: {e}"
            ) from e

    def test_tc_0_5_environment_variables(self):
        """TC-0.5: Environment Variable Loading"""
        load_dotenv()

        required_vars = [
            "PG_DSN", "PGUSER", "PGPASSWORD", "PGDATABASE", "PGHOST", "PGPORT"
        ]

        missing = [v for v in required_vars if not os.getenv(v)]

        if missing:
            raise EnvironmentError(
                f"NEGATIVE SPACE VIOLATION: Missing required env vars: {missing}"
            )

        print(f"✅ All {len(required_vars)} required environment variables present")
