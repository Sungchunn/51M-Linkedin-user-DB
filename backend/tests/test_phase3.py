"""
INSIGHT - Phase 3 Test Suite
Tests embedding generation pipeline
"""

import os
from dotenv import load_dotenv
import pytest
from backend.data_pipeline.embeddings import retry, providers
from backend.data_pipeline.ingestion import transformers as tf


class TestPhase3Retry:
    """Phase 3: Retry Logic Tests"""

    def test_tc_3_4_exponential_backoff(self):
        """TC-3.4: Exponential Backoff Retry"""
        import time

        test_cases = [
            (0, 1.0),    # 2^0 = 1s
            (1, 2.0),    # 2^1 = 2s
            (2, 4.0),    # 2^2 = 4s
            (3, 8.0),    # 2^3 = 8s
            (4, 16.0),   # 2^4 = 16s
            (5, 32.0),   # 2^5 = 32s
            (6, 60.0),   # 2^6 = 64s, capped at 60s
            (10, 60.0),  # 2^10 = 1024s, capped at 60s
        ]

        for retry_count, expected_delay in test_cases:
            delay = retry.exponential_backoff(retry_count, base_delay=1.0, max_delay=60.0)

            assert abs(delay - expected_delay) < 0.01, \
                f"NEGATIVE SPACE: backoff({retry_count}) = {delay}s, expected {expected_delay}s"

        print("✅ Exponential backoff working correctly")

    def test_retry_with_backoff_success(self):
        """Test retry succeeds on first attempt"""
        call_count = [0]

        def successful_func():
            call_count[0] += 1
            return "success"

        result = retry.retry_with_backoff(successful_func, max_retries=3)

        assert result == "success"
        assert call_count[0] == 1  # Should succeed on first try

    def test_retry_with_backoff_eventual_success(self):
        """Test retry succeeds after failures"""
        call_count = [0]

        def eventually_successful_func():
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Temporary failure")
            return "success"

        result = retry.retry_with_backoff(
            eventually_successful_func,
            max_retries=3,
            base_delay=0.1  # Fast test
        )

        assert result == "success"
        assert call_count[0] == 3  # Should succeed on 3rd attempt

    def test_retry_exhausted(self):
        """Test retry returns None after exhausting attempts"""
        call_count = [0]

        def always_fails():
            call_count[0] += 1
            raise Exception("Always fails")

        result = retry.retry_with_backoff(
            always_fails,
            max_retries=3,
            base_delay=0.1
        )

        assert result is None
        assert call_count[0] == 3  # Should try 3 times


class TestPhase3Embeddings:
    """Phase 3: Embedding Generation Tests"""

    @pytest.fixture(scope="class")
    def provider(self):
        """Embedding provider fixture"""
        load_dotenv()

        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key or api_key == 'sk-your-api-key-here':
            pytest.skip("OPENAI_API_KEY not configured")

        try:
            return providers.OpenAIEmbeddingProvider()
        except providers.EmbeddingProviderError as e:
            pytest.skip(f"Cannot initialize provider: {e}")

    def test_tc_3_1_content_template_building(self):
        """TC-3.1: Content Template Building"""
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

    def test_tc_3_6_embedding_dimension_validation(self, provider):
        """TC-3.6: Embedding Dimension Validation"""
        test_texts = ["test text 1", "test text 2", "test text 3"]

        embeddings = provider.embed_batch(test_texts)

        assert embeddings is not None, \
            "NEGATIVE SPACE: embed_batch returned None"

        assert len(embeddings) == 3, \
            f"NEGATIVE SPACE: Expected 3 embeddings, got {len(embeddings)}"

        for i, emb in enumerate(embeddings):
            assert len(emb) == 1536, \
                f"NEGATIVE SPACE: Embedding {i} has {len(emb)} dims, expected 1536"

            # Verify numeric values
            assert all(isinstance(x, (int, float)) for x in emb), \
                f"NEGATIVE SPACE: Embedding {i} contains non-numeric values"

        print(f"✅ Generated 3 embeddings, all 1536-dimensional")

    def test_embedding_single_text(self, provider):
        """Test embedding single text"""
        text = "Machine learning engineer with Python experience"

        embedding = provider.embed_single(text)

        assert embedding is not None, "NEGATIVE SPACE: embed_single returned None"
        assert len(embedding) == 1536, \
            f"NEGATIVE SPACE: Embedding has {len(embedding)} dims, expected 1536"

    def test_embedding_empty_text(self, provider):
        """Test embedding empty text returns None"""
        embedding = provider.embed_single("")

        assert embedding is None, \
            "NEGATIVE SPACE: Empty text should return None"

    def test_embedding_batch_size_limit(self, provider):
        """Test batch size limit enforcement"""
        # Try to embed 101 texts (exceeds OpenAI limit of 100)
        texts = [f"text {i}" for i in range(101)]

        # The retry decorator will catch the exception and return None
        result = provider.embed_batch(texts)

        assert result is None, \
            "NEGATIVE SPACE: Batch > 100 should return None (failed after retries)"

    def test_validate_embedding(self, provider):
        """Test embedding validation"""
        # Valid embedding
        valid_emb = [0.1] * 1536
        assert provider.validate_embedding(valid_emb) is True

        # Wrong dimension
        wrong_dim = [0.1] * 100
        assert provider.validate_embedding(wrong_dim) is False

        # Empty embedding
        assert provider.validate_embedding([]) is False

        # Non-numeric values
        invalid = [0.1] * 1535 + ["not a number"]
        assert provider.validate_embedding(invalid) is False


class TestPhase3Integration:
    """Phase 3: Integration Tests (require database and API key)"""

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

    def test_embedding_generation_flow(self, db_conn):
        """Test end-to-end embedding generation"""
        load_dotenv()

        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key or api_key == 'sk-your-api-key-here':
            pytest.skip("OPENAI_API_KEY not configured")

        from backend.data_pipeline.embeddings.generate import (
            get_profiles_needing_embeddings,
            build_embedding_text,
            update_profile_embedding
        )

        # Get one profile without embedding
        profiles = get_profiles_needing_embeddings(
            db_conn,
            min_quality_score=0.7,
            batch_size=1,
            offset=0
        )

        if not profiles:
            pytest.skip("No profiles available for testing")

        profile = profiles[0]

        # Build text
        text = build_embedding_text(profile)
        assert len(text) > 0, "NEGATIVE SPACE: Text should not be empty"

        # Generate embedding
        provider = providers.get_provider()
        embedding = provider.embed_single(text)

        assert embedding is not None, "NEGATIVE SPACE: Failed to generate embedding"
        assert len(embedding) == 1536, "NEGATIVE SPACE: Wrong embedding dimension"

        # Update profile
        success = update_profile_embedding(db_conn, profile['id'], embedding)
        assert success is True, "NEGATIVE SPACE: Failed to update profile"

        db_conn.commit()

        # Verify embedding was saved
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT embedding IS NOT NULL as has_embedding FROM profiles WHERE id = %s",
                (profile['id'],)
            )
            result = cur.fetchone()
            assert result[0] is True, "NEGATIVE SPACE: Embedding not saved"

        print(f"✅ Successfully generated and saved embedding for profile {profile['id']}")
