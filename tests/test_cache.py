"""
Test QueryCache implementation

Tests verify:
1. Cache failures don't break the system
2. All operations have timeouts
3. Keys are hashed for consistency
4. TTLs prevent stale data
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import redis
import json
import hashlib
import time


class TestQueryCacheInitialization:
    """Test cache initialization and connection handling"""

    def test_cache_initialization_success(self):
        """Cache should initialize and connect to Redis successfully"""
        with patch('redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_redis.return_value = mock_client

            from cache import QueryCache
            cache = QueryCache(host="redis", port=6379)

            assert cache.connected is True
            mock_client.ping.assert_called_once()

    def test_cache_initialization_failure_graceful(self):
        """Cache should handle Redis connection failure gracefully"""
        with patch('redis.Redis') as mock_redis:
            mock_redis.side_effect = redis.ConnectionError("Connection refused")

            from cache import QueryCache
            cache = QueryCache(host="nonexistent", port=6379)

            # Should not raise exception, set connected=False
            assert cache.connected is False

    def test_cache_timeout_configured(self):
        """Cache should have 5-second timeout configured"""
        with patch('redis.Redis') as mock_redis:
            from cache import QueryCache
            cache = QueryCache(host="redis", port=6379)

            # Verify timeout parameters passed to Redis client
            call_kwargs = mock_redis.call_args[1]
            assert call_kwargs.get('socket_connect_timeout') == 5
            assert call_kwargs.get('socket_timeout') == 5


class TestQueryCacheGet:
    """Test cache GET operations"""

    def test_cache_get_hit(self):
        """Cache GET should return cached value if exists"""
        with patch('redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            cached_value = json.dumps({"results": ["test"]})
            mock_client.get.return_value = cached_value
            mock_redis.return_value = mock_client

            from cache import QueryCache
            cache = QueryCache(host="redis")

            result = cache.get("test query", {"k": 5})

            assert result is not None
            assert result == {"results": ["test"]}

    def test_cache_get_miss(self):
        """Cache GET should return None if key doesn't exist"""
        with patch('redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_client.get.return_value = None  # Cache miss
            mock_redis.return_value = mock_client

            from cache import QueryCache
            cache = QueryCache(host="redis")

            result = cache.get("test query", {"k": 5})

            assert result is None

    def test_cache_get_timeout_graceful(self):
        """Cache GET timeout should return None, not crash"""
        with patch('redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_client.get.side_effect = redis.TimeoutError("Timeout")
            mock_redis.return_value = mock_client

            from cache import QueryCache
            cache = QueryCache(host="redis")

            result = cache.get("test query")

            # Should return None, not raise exception
            assert result is None

    def test_cache_get_redis_disconnected(self):
        """Cache GET when Redis down should return None"""
        with patch('redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_client.get.side_effect = redis.ConnectionError("Disconnected")
            mock_redis.return_value = mock_client

            from cache import QueryCache
            cache = QueryCache(host="redis")

            result = cache.get("test query")

            # Should return None and mark as disconnected
            assert result is None
            assert cache.connected is False

    def test_cache_get_corrupted_json(self):
        """Cache GET with corrupted JSON should handle gracefully"""
        with patch('redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_client.get.return_value = "{invalid json"  # Corrupted
            mock_redis.return_value = mock_client

            from cache import QueryCache
            cache = QueryCache(host="redis")

            result = cache.get("test query")

            # Should return None and attempt to delete corrupted key
            assert result is None
            mock_client.delete.assert_called_once()

    def test_cache_get_when_not_connected(self):
        """Cache GET should return None if not connected"""
        with patch('redis.Redis') as mock_redis:
            mock_redis.side_effect = redis.ConnectionError()

            from cache import QueryCache
            cache = QueryCache(host="nonexistent")

            result = cache.get("test query")

            assert result is None


class TestQueryCacheSet:
    """Test cache SET operations"""

    def test_cache_set_success(self):
        """Cache SET should store value with TTL"""
        with patch('redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_redis.return_value = mock_client

            from cache import QueryCache
            cache = QueryCache(host="redis")

            cache.set("test query", {"k": 5}, {"result": "test"})

            # Should use SETEX for atomic set-with-TTL
            mock_client.setex.assert_called_once()
            call_args = mock_client.setex.call_args[0]
            assert call_args[1] == 3600  # TTL = 1 hour

    def test_cache_set_fire_and_forget(self):
        """Cache SET failure should not raise exception"""
        with patch('redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_client.setex.side_effect = redis.TimeoutError()
            mock_redis.return_value = mock_client

            from cache import QueryCache
            cache = QueryCache(host="redis")

            # Should not raise exception
            cache.set("test query", {}, {"result": "test"})

    def test_cache_set_when_not_connected(self):
        """Cache SET should do nothing if not connected"""
        with patch('redis.Redis') as mock_redis:
            mock_redis.side_effect = redis.ConnectionError()

            from cache import QueryCache
            cache = QueryCache(host="nonexistent")

            # Should not raise exception
            cache.set("test query", {}, {"result": "test"})


class TestCacheKeyGeneration:
    """Test cache key generation logic"""

    def test_cache_key_generation_consistency(self):
        """Same query+filters should generate same cache key"""
        with patch('redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_redis.return_value = mock_client

            from cache import QueryCache
            cache = QueryCache(host="redis")

            key1 = cache._make_key("Docker networking", {"k": 5, "collection": "docs"})
            key2 = cache._make_key("Docker networking", {"k": 5, "collection": "docs"})

            assert key1 == key2

    def test_cache_key_generation_different_query(self):
        """Different queries should generate different cache keys"""
        with patch('redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_redis.return_value = mock_client

            from cache import QueryCache
            cache = QueryCache(host="redis")

            key1 = cache._make_key("Docker networking", {"k": 5})
            key2 = cache._make_key("Kubernetes pods", {"k": 5})

            assert key1 != key2

    def test_cache_key_generation_different_filters(self):
        """Same query with different filters = different keys"""
        with patch('redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_redis.return_value = mock_client

            from cache import QueryCache
            cache = QueryCache(host="redis")

            key1 = cache._make_key("Docker", {"k": 5})
            key2 = cache._make_key("Docker", {"k": 10})

            assert key1 != key2

    def test_cache_key_lowercase_normalized(self):
        """Cache keys should normalize query to lowercase"""
        with patch('redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_redis.return_value = mock_client

            from cache import QueryCache
            cache = QueryCache(host="redis")

            key1 = cache._make_key("DOCKER NETWORKING", {})
            key2 = cache._make_key("docker networking", {})

            # Should be same (case-insensitive)
            assert key1 == key2

    def test_cache_key_strips_whitespace(self):
        """Cache keys should strip whitespace from query"""
        with patch('redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_redis.return_value = mock_client

            from cache import QueryCache
            cache = QueryCache(host="redis")

            key1 = cache._make_key("  Docker networking  ", {})
            key2 = cache._make_key("Docker networking", {})

            assert key1 == key2

    def test_cache_key_format(self):
        """Cache keys should use alfred:query: prefix"""
        with patch('redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_redis.return_value = mock_client

            from cache import QueryCache
            cache = QueryCache(host="redis")

            key = cache._make_key("test", {})

            assert key.startswith("alfred:query:")


class TestCacheTTL:
    """Test TTL (Time-To-Live) behavior"""

    def test_cache_ttl_default_one_hour(self):
        """Default TTL should be 1 hour (3600 seconds)"""
        with patch('redis.Redis') as mock_redis:
            mock_client = MagicMock()
            mock_client.ping.return_value = True
            mock_redis.return_value = mock_client

            from cache import QueryCache
            cache = QueryCache(host="redis")

            assert cache.ttl_seconds == 3600


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
