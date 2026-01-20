"""
Alfred AI - Redis Query Cache
Redis-based caching layer with graceful degradation
"""

import redis
import json
import hashlib
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class QueryCache:
    """Redis-based query caching with graceful degradation"""

    def __init__(
        self,
        host: str = "redis",
        port: int = 6379,
        db: int = 0,
        timeout: int = 5
    ):
        """Initialize Redis cache connection"""
        try:
            self.client = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=True,
                socket_connect_timeout=timeout,
                socket_timeout=timeout,
                socket_keepalive=True,
                health_check_interval=30
            )
            # Test connection
            self.client.ping()
            self.connected = True
            logger.info(f"Redis cache connected ({host}:{port})")
        except redis.ConnectionError as e:
            logger.warning(f"Redis not available: {e}. Running without cache.")
            self.connected = False
        except Exception as e:
            logger.warning(f"Redis initialization failed: {e}. Running without cache.")
            self.connected = False

        self.ttl_seconds = 3600  # 1 hour default

    def get(self, query: str, filters: Dict | None = None) -> Dict | None:
        """
        Get cached response.

        Returns None on cache miss or any error (graceful degradation).
        """
        if not self.connected:
            return None

        try:
            key = self._make_key(query, filters)
            cached = self.client.get(key)

            if cached:
                logger.info(f"Cache HIT for key: {key[:16]}...")
                assert isinstance(cached, str), "cached should be str with decode_responses=True"
                return json.loads(cached)

            logger.debug(f"Cache MISS for key: {key[:16]}...")
            return None

        except redis.TimeoutError:
            logger.error("Cache GET timeout - Redis slow")
            return None
        except redis.ConnectionError:
            logger.error("Cache GET failed - Redis disconnected")
            self.connected = False
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Cache GET failed - Invalid JSON: {e}")
            try:
                self.client.delete(key)
                logger.info(f"Deleted corrupted cache key: {key[:16]}...")
            except:
                pass
            return None
        except Exception as e:
            logger.error(f"Cache GET unexpected error: {e}")
            return None

    def set(self, query: str, filters: Dict, response: Dict):
        """
        Cache response.

        Failures are logged but don't raise exceptions (fire and forget).
        """
        if not self.connected:
            return

        try:
            key = self._make_key(query, filters)
            value = json.dumps(response)

            self.client.setex(key, self.ttl_seconds, value)
            logger.info(f"Cache SET for key: {key[:16]}...")

        except redis.TimeoutError:
            logger.error("Cache SET timeout - Redis slow")
        except redis.ConnectionError:
            logger.error("Cache SET failed - Redis disconnected")
            self.connected = False
        except Exception as e:
            logger.error(f"Cache SET unexpected error: {e}")

    def _make_key(self, query: str, filters: Dict | None = None) -> str:
        """
        Generate deterministic cache key using SHA256 hash.
        """
        content = json.dumps({
            "query": query.lower().strip(),
            "filters": filters or {}
        }, sort_keys=True)

        hash_val = hashlib.sha256(content.encode()).hexdigest()
        return f"alfred:query:{hash_val}"
