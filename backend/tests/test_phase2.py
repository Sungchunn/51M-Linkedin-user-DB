"""
INSIGHT - Phase 2 Test Suite
Tests data ingestion pipeline (staging → core transformation)
"""

import os
from dotenv import load_dotenv
import pytest
from backend.data_pipeline.ingestion import transformers as tf
from backend.data_pipeline.ingestion import validators as val


class TestPhase2Transformers:
    """Phase 2: Data Transformation Tests"""

    def test_tc_2_2_skills_parsing(self):
        """TC-2.2: Skills Parsing"""
        test_cases = [
            ("Python, SQL, Docker", ["python", "sql", "docker"]),
            ("Python; SQL; Docker", ["python", "sql", "docker"]),
            ("Python,SQL,Docker", ["python", "sql", "docker"]),
            ("", []),
            (None, []),
            ("  Python  ,  SQL  ", ["python", "sql"]),
        ]

        for input_val, expected in test_cases:
            result = tf.parse_skills(input_val)
            assert result == expected, (
                f"NEGATIVE SPACE: parse_skills({input_val!r}) = {result}, expected {expected}"
            )

    def test_tc_2_3_years_experience_extraction(self):
        """TC-2.3: Years Experience Extraction"""
        test_cases = [
            ("5", 5),
            ("5 years", 5),
            ("10+", 10),
            ("3-5", 3),  # Take lower bound
            ("abc", None),
            ("", None),
            (None, None),
            ("150", None),  # Over 80 years - invalid
            ("0", 0),  # Edge case
            ("80", 80),  # Max valid
            ("81", None),  # Over max
        ]

        for input_val, expected in test_cases:
            result = tf.parse_years_experience(input_val)
            assert result == expected, (
                f"NEGATIVE SPACE: parse_years_experience({input_val!r}) = {result}, expected {expected}"
            )

    def test_tc_2_6_geographic_field_mapping(self):
        """TC-2.6: Geographic Field Mapping"""
        test_row = {
            "Location": "Bangkok Metropolitan Area",
            "Locality": "Bangkok",
            "Region": "Bangkok",
            "Location Country": "Thailand"
        }

        result = tf.map_geo_fields(test_row)

        assert result['location'] == "Bangkok Metropolitan Area"
        assert result['locality'] == "Bangkok"
        assert result['region'] == "Bangkok"
        assert result['location_country'] == "Thailand"

        # Test null handling
        null_row = {
            "Location": None,
            "Locality": None,
            "Region": None,
            "Location Country": None
        }

        result = tf.map_geo_fields(null_row)
        assert all(v is None for v in result.values()), \
            "NEGATIVE SPACE: NULL geo fields not preserved"

        # Test empty string handling
        empty_row = {
            "Location": "",
            "Locality": "  ",
            "Region": "",
            "Location Country": "   "
        }

        result = tf.map_geo_fields(empty_row)
        assert all(v is None for v in result.values()), \
            "NEGATIVE SPACE: Empty geo fields should become None"

    def test_skill_normalization(self):
        """Test skill normalization for fuzzy matching"""
        test_cases = [
            ("Machine Learning", "machinelearning"),
            ("C++", "c"),
            ("Node.js", "nodejs"),
            ("data-science", "datascience"),
            ("", ""),
            (None, ""),
        ]

        for input_val, expected in test_cases:
            result = tf.normalize_skill(input_val)
            assert result == expected, \
                f"NEGATIVE SPACE: normalize_skill({input_val!r}) = {result}, expected {expected}"

    def test_clean_text_field(self):
        """Test text field cleaning"""
        assert tf.clean_text_field("  Hello  ") == "Hello"
        assert tf.clean_text_field("") is None
        assert tf.clean_text_field("   ") is None
        assert tf.clean_text_field(None) is None

        # Test truncation
        long_text = "a" * 200
        result = tf.clean_text_field(long_text, max_length=100)
        assert len(result) == 100

    def test_validate_email(self):
        """Test email validation"""
        # Valid
        assert tf.validate_email("user@example.com") == "user@example.com"
        assert tf.validate_email("USER@EXAMPLE.COM") == "user@example.com"  # Lowercased

        # Invalid
        assert tf.validate_email("not-an-email") is None
        assert tf.validate_email("") is None
        assert tf.validate_email(None) is None
        assert tf.validate_email("@example.com") is None

    def test_validate_linkedin_username(self):
        """Test LinkedIn username validation"""
        # Valid
        assert tf.validate_linkedin_username("john-doe") == "john-doe"
        assert tf.validate_linkedin_username("john_doe_123") == "john_doe_123"

        # Invalid
        assert tf.validate_linkedin_username("john@doe") is None  # @ not allowed
        assert tf.validate_linkedin_username("john.doe") is None  # . not allowed
        assert tf.validate_linkedin_username("") is None
        assert tf.validate_linkedin_username(None) is None


class TestPhase2Validators:
    """Phase 2: Data Validation Tests"""

    def test_validate_required_fields(self):
        """Test required field validation"""
        # Valid
        valid_row = {
            'full_name': 'John Doe',
            'linkedin_username': 'johndoe'
        }
        is_valid, error = val.validate_required_fields(valid_row)
        assert is_valid is True
        assert error is None

        # Missing full_name
        invalid_row = {
            'full_name': None,
            'linkedin_username': 'johndoe'
        }
        is_valid, error = val.validate_required_fields(invalid_row)
        assert is_valid is False
        assert "full_name" in error

        # Empty linkedin_username
        invalid_row = {
            'full_name': 'John Doe',
            'linkedin_username': ''
        }
        is_valid, error = val.validate_required_fields(invalid_row)
        assert is_valid is False
        assert "linkedin_username" in error

    def test_validate_numeric_ranges(self):
        """Test numeric range validation"""
        # Valid
        valid_row = {
            'years_experience': 5,
            'content_quality_score': 0.8,
            'profile_completeness': 75
        }
        is_valid, error = val.validate_numeric_ranges(valid_row)
        assert is_valid is True

        # Invalid years_experience
        invalid_row = {
            'years_experience': 150,
        }
        is_valid, error = val.validate_numeric_ranges(invalid_row)
        assert is_valid is False
        assert "years_experience" in error

        # Invalid quality score
        invalid_row = {
            'content_quality_score': 1.5,
        }
        is_valid, error = val.validate_numeric_ranges(invalid_row)
        assert is_valid is False
        assert "content_quality_score" in error

    def test_calculate_quality_score(self):
        """Test quality score calculation"""
        # Full profile
        full_row = {
            'full_name': 'John Doe',
            'linkedin_username': 'johndoe',
            'job_title': 'Engineer',
            'company_name': 'Tech Corp',
            'industry': 'Technology',
            'location': 'Bangkok',
            'skills': ['python', 'sql']
        }
        score = val.calculate_quality_score(full_row)
        assert score == 1.0, f"NEGATIVE SPACE: Expected 1.0, got {score}"

        # Minimal profile
        minimal_row = {
            'full_name': 'John Doe',
            'linkedin_username': 'johndoe',
        }
        score = val.calculate_quality_score(minimal_row)
        assert score == 0.3, f"NEGATIVE SPACE: Expected 0.3, got {score}"  # 0.15 + 0.15

        # Empty profile (should still have full_name and username from validation)
        empty_row = {
            'full_name': 'John',
            'linkedin_username': 'john',
            'job_title': None,
            'company_name': None,
            'industry': None,
            'location': None,
            'skills': None
        }
        score = val.calculate_quality_score(empty_row)
        assert 0.0 <= score <= 1.0, \
            f"NEGATIVE SPACE: score={score} outside [0.0, 1.0]"

    def test_validate_embedding_dimension(self):
        """Test embedding dimension validation"""
        # Valid
        valid_embedding = [0.1] * 1536
        is_valid, error = val.validate_embedding_dimension(valid_embedding)
        assert is_valid is True

        # None is valid (not all profiles have embeddings)
        is_valid, error = val.validate_embedding_dimension(None)
        assert is_valid is True

        # Wrong dimension
        wrong_dim = [0.1] * 100
        is_valid, error = val.validate_embedding_dimension(wrong_dim)
        assert is_valid is False
        assert "1536" in error

        # Non-numeric values
        invalid_embedding = [0.1] * 1535 + ["not a number"]
        is_valid, error = val.validate_embedding_dimension(invalid_embedding)
        assert is_valid is False

    def test_build_content_for_embedding(self):
        """Test content template building for embeddings"""
        test_row = {
            'job_title': 'Senior ML Engineer',
            'company_name': 'Tech Corp',
            'industry': 'Technology',
            'location': 'Bangkok, Thailand',
            'skills': ['python', 'nlp', 'pytorch']
        }

        result = tf.build_content_for_embedding(test_row)

        expected = (
            "Professional: Senior ML Engineer at Tech Corp | "
            "Industry: Technology | "
            "Location: Bangkok, Thailand | "
            "Skills: python, nlp, pytorch"
        )

        assert result == expected, \
            f"NEGATIVE SPACE: Template mismatch\nGot: {result}\nExpected: {expected}"

        # Test NULL handling
        null_row = {
            'job_title': None,
            'company_name': None,
            'industry': None,
            'location': None,
            'skills': None
        }

        result = tf.build_content_for_embedding(null_row)

        # Should not crash, should use "N/A"
        assert "Professional:" in result, "NEGATIVE SPACE: Template broken with NULLs"
        assert "N/A" in result, "NEGATIVE SPACE: Missing N/A placeholder"


class TestPhase2Integration:
    """Phase 2: Integration Tests (require database)"""

    @pytest.fixture(scope="class")
    def db_conn(self):
        """Database connection fixture"""
        load_dotenv()
        import psycopg
        dsn = os.getenv("PG_DSN")

        if not dsn:
            pytest.skip("PG_DSN not set, skipping database tests")

        with psycopg.connect(dsn) as conn:
            yield conn

    def test_upsert_handling(self, db_conn):
        """TC-2.4: Duplicate Handling (UPSERT)"""
        from backend.data_pipeline.ingestion.load_to_core import insert_profile

        # Clean up first
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM profiles WHERE linkedin_username = 'test_upsert_user'")
        db_conn.commit()

        # Insert initial record
        row1 = {
            'full_name': 'Test User',
            'first_name': 'Test',
            'last_name': 'User',
            'linkedin_url': None,
            'linkedin_username': 'test_upsert_user',
            'job_title': 'Engineer',
            'company_name': 'Company A',
            'industry': 'Tech',
            'years_experience': 5,
            'location': None,
            'locality': None,
            'region': None,
            'location_country': None,
            'skills': ['python'],
            'skills_normalized': ['python'],
            'headline': None,
            'summary': None,
            'email': None,
            'phone': None,
            'website': None,
            'twitter': None,
            'github': None,
            'embedding': None,
            'content_quality_score': 0.7,
            'profile_completeness': 50
        }

        success = insert_profile(db_conn, row1)
        assert success, "NEGATIVE SPACE: Initial insert failed"
        db_conn.commit()

        # Insert duplicate with updated info
        row2 = row1.copy()
        row2['job_title'] = 'Senior Engineer'
        row2['company_name'] = 'Company B'

        success = insert_profile(db_conn, row2)
        assert success, "NEGATIVE SPACE: UPSERT failed"
        db_conn.commit()

        # Verify only one record exists with updated data
        with db_conn.cursor() as cur:
            cur.execute("""
                SELECT count(*), job_title, company_name
                FROM profiles
                WHERE linkedin_username = 'test_upsert_user'
                GROUP BY job_title, company_name
            """)
            result = cur.fetchone()

            assert result is not None, "NEGATIVE SPACE: No record found after UPSERT"
            count, title, company = result

            assert count == 1, f"NEGATIVE SPACE: Expected 1 record, got {count}"
            assert title == 'Senior Engineer', f"NEGATIVE SPACE: Title not updated"
            assert company == 'Company B', f"NEGATIVE SPACE: Company not updated"

        # Clean up
        with db_conn.cursor() as cur:
            cur.execute("DELETE FROM profiles WHERE linkedin_username = 'test_upsert_user'")
        db_conn.commit()

        print("✅ UPSERT handling working correctly")
