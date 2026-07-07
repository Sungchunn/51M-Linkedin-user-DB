"""
INSIGHT - Phase 4 Test Suite
Tests FastAPI search endpoints
"""

import os
from dotenv import load_dotenv
import pytest
from httpx import AsyncClient, ASGITransport
from backend.api.app import app
from backend.api import database


class TestPhase4API:
    """Phase 4: API Endpoint Tests"""

    @pytest.fixture(scope="class", autouse=True)
    def setup(self):
        """Setup: Load environment variables"""
        load_dotenv()

        dsn = os.getenv('PG_DSN')
        if not dsn:
            pytest.skip("PG_DSN not configured")

        yield

        # Note: Pool cleanup happens in app lifespan

    @pytest.mark.asyncio
    async def test_tc_4_1_root_endpoint(self):
        """TC-4.1: Root endpoint returns API info"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/")

        assert response.status_code == 200

        data = response.json()
        assert "name" in data
        assert "INSIGHT" in data["name"]
        assert "version" in data
        assert data["status"] == "running"

        print("✅ Root endpoint working")

    @pytest.mark.asyncio
    async def test_tc_4_2_health_endpoint(self):
        """TC-4.2: Health endpoint returns database status"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert "profiles_total" in data
        assert "profiles_with_embeddings" in data
        assert isinstance(data["profiles_total"], int)
        assert isinstance(data["profiles_with_embeddings"], int)

        print(f"✅ Health check: {data['profiles_with_embeddings']:,} embedded profiles")

    @pytest.mark.asyncio
    async def test_tc_4_3_search_basic(self):
        """TC-4.3: Basic search returns results"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/search",
                json={"query": "software engineer"}
            )

        assert response.status_code == 200

        data = response.json()
        assert "results" in data
        assert "total_count" in data
        assert "returned_count" in data
        assert "query_time_ms" in data

        # Validate counts
        assert data["returned_count"] == len(data["results"])
        assert data["total_count"] >= data["returned_count"]

        # Validate results structure
        if data["results"]:
            result = data["results"][0]
            assert "id" in result
            assert "full_name" in result
            assert "score" in result
            assert 0.0 <= result["score"] <= 1.0

        print(f"✅ Basic search returned {data['returned_count']} results in {data['query_time_ms']:.1f}ms")

    @pytest.mark.asyncio
    async def test_tc_4_4_search_with_filters(self):
        """TC-4.4: Search with location filter"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/search",
                json={
                    "query": "engineer",
                    "location_country": "united states",
                    "limit": 10
                }
            )

        assert response.status_code == 200

        data = response.json()
        assert data["returned_count"] <= 10

        # Verify filter was applied
        assert "location_country" in data["filters_applied"]
        assert data["filters_applied"]["location_country"] == "united states"

        # Verify results match filter
        for result in data["results"]:
            if result.get("location_country"):
                assert result["location_country"].lower() == "united states"

        print(f"✅ Filtered search returned {data['returned_count']} US-based results")

    @pytest.mark.asyncio
    async def test_tc_4_5_search_pagination(self):
        """TC-4.5: Pagination works correctly"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # First page
            response1 = await client.post(
                "/search",
                json={"query": "engineer", "limit": 5, "offset": 0}
            )

            # Second page
            response2 = await client.post(
                "/search",
                json={"query": "engineer", "limit": 5, "offset": 5}
            )

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Same total count
        assert data1["total_count"] == data2["total_count"]

        # Different results (if enough data)
        if data1["returned_count"] == 5 and data2["returned_count"] > 0:
            ids1 = {r["id"] for r in data1["results"]}
            ids2 = {r["id"] for r in data2["results"]}
            assert len(ids1 & ids2) == 0, "NEGATIVE SPACE: Pages should not overlap"

        print(f"✅ Pagination working: page1={data1['returned_count']}, page2={data2['returned_count']}")

    @pytest.mark.asyncio
    async def test_tc_4_6_search_empty_query(self):
        """TC-4.6: Empty query returns validation error"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/search",
                json={"query": ""}
            )

        # Pydantic validation should catch this
        assert response.status_code == 422  # Unprocessable Entity

        print("✅ Empty query rejected with 422")

    @pytest.mark.asyncio
    async def test_tc_4_7_search_invalid_limit(self):
        """TC-4.7: Invalid limit returns validation error"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Limit > 100 (max)
            response = await client.post(
                "/search",
                json={"query": "engineer", "limit": 101}
            )

        assert response.status_code == 422

        print("✅ Invalid limit rejected with 422")

    @pytest.mark.asyncio
    async def test_tc_4_8_search_skills_filter(self):
        """TC-4.8: Skills filter works"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/search",
                json={
                    "query": "engineer",
                    "skills": ["python"],
                    "limit": 10
                }
            )

        assert response.status_code == 200

        data = response.json()

        # Verify filter was applied
        assert "skills" in data["filters_applied"]

        # Verify results contain required skill
        for result in data["results"]:
            if result.get("skills"):
                assert "python" in [s.lower() for s in result["skills"]], \
                    "NEGATIVE SPACE: Results should contain filtered skill"

        print(f"✅ Skills filter returned {data['returned_count']} Python engineers")

    @pytest.mark.asyncio
    async def test_tc_4_9_search_experience_filter(self):
        """TC-4.9: Experience range filter works"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/search",
                json={
                    "query": "engineer",
                    "min_years_experience": 5,
                    "max_years_experience": 10,
                    "limit": 10
                }
            )

        assert response.status_code == 200

        data = response.json()

        # Verify filters applied
        assert data["filters_applied"]["min_years_experience"] == 5
        assert data["filters_applied"]["max_years_experience"] == 10

        # Verify results match filter
        for result in data["results"]:
            if result.get("years_experience") is not None:
                assert 5 <= result["years_experience"] <= 10, \
                    "NEGATIVE SPACE: Experience should be in range"

        print(f"✅ Experience filter returned {data['returned_count']} results with 5-10 years")

    @pytest.mark.asyncio
    async def test_tc_4_10_search_weight_adjustment(self):
        """TC-4.10: Vector/lexical weight adjustment works"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Heavy vector weight
            response1 = await client.post(
                "/search",
                json={
                    "query": "machine learning engineer",
                    "vector_weight": 1.0,
                    "lexical_weight": 0.0,
                    "limit": 5
                }
            )

            # Heavy lexical weight
            response2 = await client.post(
                "/search",
                json={
                    "query": "machine learning engineer",
                    "vector_weight": 0.0,
                    "lexical_weight": 1.0,
                    "limit": 5
                }
            )

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Results may differ (semantic vs lexical ranking)
        print(f"✅ Weight adjustment working: "
              f"vector={data1['returned_count']}, lexical={data2['returned_count']}")


class TestPhase4Integration:
    """Phase 4: Integration Tests"""

    @pytest.fixture(scope="class", autouse=True)
    def setup(self):
        """Setup: Load environment variables"""
        load_dotenv()

        dsn = os.getenv('PG_DSN')
        if not dsn:
            pytest.skip("PG_DSN not configured")

        yield

        # Note: Pool cleanup happens in app lifespan

    @pytest.mark.asyncio
    async def test_semantic_search_quality(self):
        """Test that semantic search returns relevant results"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/search",
                json={
                    "query": "experienced python developer with machine learning expertise",
                    "limit": 10
                }
            )

        assert response.status_code == 200

        data = response.json()

        if data["results"]:
            # Check top result has reasonable score
            top_result = data["results"][0]
            assert top_result["score"] > 0.5, \
                "NEGATIVE SPACE: Top result should have score > 0.5"

            # Results should be sorted by score descending
            scores = [r["score"] for r in data["results"]]
            assert scores == sorted(scores, reverse=True), \
                "NEGATIVE SPACE: Results must be sorted by score DESC"

            print(f"✅ Semantic search quality check passed (top score: {top_result['score']:.3f})")

    @pytest.mark.asyncio
    async def test_multi_filter_combination(self):
        """Test combining multiple filters"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/search",
                json={
                    "query": "software engineer",
                    "location_country": "united states",
                    "min_years_experience": 3,
                    "skills": ["python"],
                    "min_quality_score": 0.8,
                    "limit": 10
                }
            )

        assert response.status_code == 200

        data = response.json()

        # Verify all filters applied
        filters = data["filters_applied"]
        assert len(filters) == 4

        print(f"✅ Multi-filter search returned {data['returned_count']} results")

    @pytest.mark.asyncio
    async def test_query_performance(self):
        """Test that queries complete in reasonable time"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/search",
                json={"query": "engineer", "limit": 20}
            )

        assert response.status_code == 200

        data = response.json()
        query_time = data["query_time_ms"]

        # Should complete in under 2 seconds for 20 results
        assert query_time < 2000, \
            f"NEGATIVE SPACE: Query took {query_time:.1f}ms (expected < 2000ms)"

        print(f"✅ Query performance: {query_time:.1f}ms for {data['returned_count']} results")
