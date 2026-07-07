"""
INSIGHT - Phase 1 Test Suite
Tests database schema and migrations
"""

import os
import psycopg
from dotenv import load_dotenv
import pytest


class TestPhase1:
    """Phase 1: Database Schema & Migrations"""

    @pytest.fixture(scope="class")
    def db_conn(self):
        """Database connection fixture"""
        load_dotenv()
        dsn = os.getenv("PG_DSN")

        if not dsn:
            pytest.skip("PG_DSN not set, skipping database tests")

        with psycopg.connect(dsn) as conn:
            yield conn

    def test_tc_1_1_staging_table_creation(self, db_conn):
        """TC-1.1: Staging Table Creation"""
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT count(*) FROM information_schema.columns
                WHERE table_name = 'staging_profiles_raw'
            """)
            column_count = cur.fetchone()[0]

            # Should have 62 columns + import_batch_id + import_timestamp = 64
            assert column_count >= 62, \
                f"NEGATIVE SPACE VIOLATION: Expected ≥62 columns, got {column_count}"

    def test_tc_1_2_core_table_constraints_empty_name(self, db_conn):
        """TC-1.2a: Core Table Constraints - Empty full_name"""
        with db_conn.cursor() as cur:
            try:
                cur.execute("""
                    INSERT INTO profiles (full_name, linkedin_username, years_experience)
                    VALUES ('', 'test_user_empty', 5)
                """)
                db_conn.commit()
                raise AssertionError(
                    "NEGATIVE SPACE VIOLATION: Empty full_name accepted"
                )
            except psycopg.errors.CheckViolation:
                db_conn.rollback()
                print("✅ Empty full_name correctly rejected")

    def test_tc_1_2_core_table_constraints_invalid_username(self, db_conn):
        """TC-1.2b: Core Table Constraints - Invalid username format"""
        with db_conn.cursor() as cur:
            try:
                cur.execute("""
                    INSERT INTO profiles (full_name, linkedin_username, years_experience)
                    VALUES ('John Doe', 'test@invalid', 5)
                """)
                db_conn.commit()
                raise AssertionError(
                    "NEGATIVE SPACE VIOLATION: Invalid username format accepted"
                )
            except psycopg.errors.CheckViolation:
                db_conn.rollback()
                print("✅ Invalid username format correctly rejected")

    def test_tc_1_2_core_table_constraints_years_experience(self, db_conn):
        """TC-1.2c: Core Table Constraints - years_experience > 80"""
        with db_conn.cursor() as cur:
            try:
                cur.execute("""
                    INSERT INTO profiles (full_name, linkedin_username, years_experience)
                    VALUES ('John Doe', 'test_user_150yrs', 150)
                """)
                db_conn.commit()
                raise AssertionError(
                    "NEGATIVE SPACE VIOLATION: years_experience=150 accepted"
                )
            except psycopg.errors.CheckViolation:
                db_conn.rollback()
                print("✅ years_experience > 80 correctly rejected")

    def test_tc_1_3_vector_dimension_enforcement(self, db_conn):
        """TC-1.3: Vector Dimension Enforcement"""
        with db_conn.cursor() as cur:
            try:
                cur.execute("""
                    INSERT INTO profiles (full_name, linkedin_username, embedding)
                    VALUES ('John Doe', 'test_user_wrong_dims', '[1,2,3]'::vector)
                """)
                db_conn.commit()
                raise AssertionError(
                    "NEGATIVE SPACE VIOLATION: Wrong embedding dimensions accepted"
                )
            except (psycopg.errors.DataException, psycopg.errors.InternalError):
                db_conn.rollback()
                print("✅ Wrong embedding dimensions correctly rejected")

    def test_tc_1_4_hnsw_index_creation(self, db_conn):
        """TC-1.4: HNSW Index Creation"""
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'profiles'
                AND indexname = 'idx_profiles_embedding_hnsw'
            """)
            result = cur.fetchone()

            assert result is not None, \
                "NEGATIVE SPACE VIOLATION: HNSW index not found"

            indexname, indexdef = result
            indexdef_lower = indexdef.lower()

            assert 'hnsw' in indexdef_lower, \
                f"NEGATIVE SPACE VIOLATION: Index not using HNSW: {indexdef}"

            # Check for m=16 with various formats (m=16, m='16', m = 16, etc.)
            assert "m='16'" in indexdef_lower or 'm=16' in indexdef_lower or 'm = 16' in indexdef_lower, \
                f"NEGATIVE SPACE VIOLATION: Wrong m parameter: {indexdef}"

            print(f"✅ HNSW index found: {indexname}")

    def test_tc_1_5_foreign_key_cascade(self, db_conn):
        """TC-1.5: Foreign Key Cascade"""
        test_profile_id = '550e8400-e29b-41d4-a716-446655440000'

        with db_conn.cursor() as cur:
            # Clean up any existing test data
            cur.execute("DELETE FROM profiles WHERE id = %s", (test_profile_id,))

            # Insert test profile
            cur.execute("""
                INSERT INTO profiles (id, full_name, linkedin_username)
                VALUES (%s, 'Test User Cascade', 'test_user_cascade')
            """, (test_profile_id,))

            # Insert experience
            cur.execute("""
                INSERT INTO profile_experiences (profile_id, company_name, title)
                VALUES (%s, 'Test Co', 'Engineer')
            """, (test_profile_id,))

            db_conn.commit()

            # Delete profile
            cur.execute("DELETE FROM profiles WHERE id = %s", (test_profile_id,))
            db_conn.commit()

            # Check experiences were cascaded
            cur.execute("""
                SELECT count(*) FROM profile_experiences
                WHERE profile_id = %s
            """, (test_profile_id,))

            count = cur.fetchone()[0]

            assert count == 0, \
                f"NEGATIVE SPACE VIOLATION: Expected 0 experiences after cascade, got {count}"

            print("✅ Foreign key cascade working correctly")

    def test_tc_1_6_valid_insert(self, db_conn):
        """TC-1.6: Valid Insert Should Succeed"""
        with db_conn.cursor() as cur:
            # Clean up first
            cur.execute("DELETE FROM profiles WHERE linkedin_username = 'test_user_valid'")

            # Valid insert
            cur.execute("""
                INSERT INTO profiles (full_name, linkedin_username, years_experience)
                VALUES ('Valid User', 'test_user_valid', 5)
                RETURNING id, full_name, linkedin_username, years_experience
            """)

            result = cur.fetchone()
            db_conn.commit()

            assert result is not None, "NEGATIVE SPACE VIOLATION: Valid insert failed"
            uuid, name, username, years = result

            assert name == 'Valid User'
            assert username == 'test_user_valid'
            assert years == 5

            print(f"✅ Valid insert succeeded: {uuid}")

            # Clean up
            cur.execute("DELETE FROM profiles WHERE linkedin_username = 'test_user_valid'")
            db_conn.commit()
