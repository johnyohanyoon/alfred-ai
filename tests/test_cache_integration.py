"""
Test cache integration into API query flow

Tests verify:
1. Cache miss/hit behavior
2. Metadata tracking
3. Graceful degradation when Redis down
4. Cache bypass functionality
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
import time


class TestCacheIntegration:
    """Test cache integration into API endpoints"""

    @pytest.fixture
    def client(self):
        """Create FastAPI test client"""
        from main import app
        return TestClient(app)

    def test_query_cache_miss_first_request(self, client):
        """
        First query should be cache miss, hit database
        Verify metadata["cache_hit"] = False
        """
        response = client.post(
            "/api/search",
            json={"query": "Docker networking test", "k": 5, "use_cache": True}
        )

        assert response.status_code == 200
        data = response.json()
        assert "metadata" in data
        assert data["metadata"]["cache_hit"] is False

    def test_query_cache_hit_second_request(self, client):
        """
        Repeat query should be cache hit
        Verify metadata["cache_hit"] = True
        Verify response time <100ms (faster than first request)
        """
        query = {"query": "Docker cache hit test", "k": 5, "use_cache": True}

        # First request (cache miss)
        start = time.time()
        response1 = client.post("/api/search", json=query)
        latency_miss = (time.time() - start) * 1000

        # Second request (cache hit)
        start = time.time()
        response2 = client.post("/api/search", json=query)
        latency_hit = (time.time() - start) * 1000

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # First should be cache miss
        assert data1["metadata"]["cache_hit"] is False

        # Second should be cache hit
        assert data2["metadata"]["cache_hit"] is True

        # Cache hit should be faster
        assert latency_hit < latency_miss, \
            f"Cache hit ({latency_hit}ms) should be faster than miss ({latency_miss}ms)"

    def test_query_cache_bypass_option(self, client):
        """
        Query with use_cache=False should bypass cache
        Even repeat queries should show cache_hit=False
        """
        query_base = {"query": "Docker bypass test", "k": 5}

        # First request with cache
        response1 = client.post("/api/search", json={**query_base, "use_cache": True})

        # Second request with cache bypass
        response2 = client.post("/api/search", json={**query_base, "use_cache": False})

        assert response1.status_code == 200
        assert response2.status_code == 200

        data2 = response2.json()
        # Should be cache miss even though query was cached
        assert data2["metadata"]["cache_hit"] is False

    def test_query_works_when_redis_down(self, client):
        """System should work even if Redis is down (graceful degradation)"""
        with patch('scraper.QueryCache') as MockCache:
            # Simulate Redis being down
            mock_cache_instance = MagicMock()
            mock_cache_instance.connected = False
            mock_cache_instance.get.return_value = None
            MockCache.return_value = mock_cache_instance

            response = client.post(
                "/api/search",
                json={"query": "Docker test", "k": 5}
            )

            # Should still work, just slower
            assert response.status_code == 200
            data = response.json()
            # Should show cache miss (Redis down)
            assert data["metadata"]["cache_hit"] is False

    def test_different_queries_different_cache(self, client):
        """Different queries should not hit same cache entry"""
        query1 = {"query": "Docker networking", "k": 5, "use_cache": True}
        query2 = {"query": "Kubernetes pods", "k": 5, "use_cache": True}

        response1 = client.post("/api/search", json=query1)
        response2 = client.post("/api/search", json=query2)

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Both should be cache misses (different queries)
        assert data1["metadata"]["cache_hit"] is False
        assert data2["metadata"]["cache_hit"] is False

    def test_query_with_filters_cached_separately(self, client):
        """Same query with different filters should use different cache entries"""
        base_query = "Docker test"

        query1 = {"query": base_query, "k": 5, "use_cache": True}
        query2 = {"query": base_query, "k": 10, "use_cache": True}

        # Both should be cache misses (different k values)
        response1 = client.post("/api/search", json=query1)
        response2 = client.post("/api/search", json=query2)

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Both should be cache misses (different filters)
        assert data1["metadata"]["cache_hit"] is False
        assert data2["metadata"]["cache_hit"] is False

    def test_cache_returns_consistent_results(self, client):
        """Cache hit should return identical results to cache miss"""
        query = {"query": "Docker consistency test", "k": 5, "use_cache": True}

        # First request (cache miss)
        response1 = client.post("/api/search", json=query)
        data1 = response1.json()

        # Second request (cache hit)
        response2 = client.post("/api/search", json=query)
        data2 = response2.json()

        # Results should be identical (except cache_hit metadata)
        assert data1["results"] == data2["results"]
        assert data1["query"] == data2["query"]


class TestCacheMetadata:
    """Test cache metadata tracking"""

    @pytest.fixture
    def client(self):
        from main import app
        return TestClient(app)

    def test_response_includes_cache_metadata(self, client):
        """All responses should include cache metadata"""
        response = client.post(
            "/api/search",
            json={"query": "Docker test", "k": 5}
        )

        assert response.status_code == 200
        data = response.json()

        assert "metadata" in data
        assert "cache_hit" in data["metadata"]
        assert isinstance(data["metadata"]["cache_hit"], bool)

    def test_metadata_includes_query_params(self, client):
        """Metadata should track query parameters"""
        response = client.post(
            "/api/search",
            json={"query": "Docker test", "k": 7}
        )

        assert response.status_code == 200
        data = response.json()

        assert data["metadata"]["query"] == "Docker test"
        assert data["metadata"]["k"] == 7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
