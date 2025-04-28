"""
Redis cache utility for caching data.
"""

import json
from datetime import datetime
from typing import Any, List, Optional, TypeVar

import redis

from ajf_live_re_wire_ETL.shared.schemas import EventDTO
from ajf_live_re_wire_ETL.shared.utils.configs import base_configs, redis_config
from ajf_live_re_wire_ETL.shared.utils.helpers import EventDTOEncoder
from ajf_live_re_wire_ETL.shared.utils.logger import logger

T = TypeVar("T")


class RedisCache:
    """
    Redis cache manager for storing and retrieving data.
    """

    def __init__(self):
        """Initialize the Redis connection."""
        try:
            redis_url = redis_config["redis_url"]
            self.redis_client = redis.from_url(
                redis_url,
                decode_responses=redis_config["redis_decode_responses"],
                socket_timeout=redis_config["redis_socket_timeout"],
                socket_connect_timeout=redis_config["redis_socket_connect_timeout"],
                retry_on_timeout=redis_config["redis_retry_on_timeout"],
            )
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {str(e)}")
            # Provide a fallback mechanism if Redis connection fails
            self.redis_client = None
            logger.warning("Using null Redis client - caching disabled")

    def is_connected(self) -> bool:
        """Check if Redis connection is working."""
        if not self.redis_client:
            return False
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False

    def _get_cache_key(self, key_prefix: str, identifier: str) -> str:
        """
        Generate a cache key.

        Args:
            key_prefix: Prefix for the cache key
            identifier: Unique identifier for the cache key

        Returns:
            Complete cache key
        """
        return f"{key_prefix}:{identifier}"

    def _get_ttl(self, date_str: str) -> Optional[int]:
        """
        Calculate TTL based on date string.

        Args:
            date_str: Date string to calculate TTL for

        Returns:
            TTL in seconds, or None for no expiration
        """
        try:
            event_date = datetime.strptime(date_str, base_configs["date_format"]).date()
            today = datetime.now(base_configs["timezone"]).date()
            days_diff = (event_date - today).days

            if days_diff < 0:
                # Past events - cache for 1 week
                return 60 * 60 * 24 * 7
            elif days_diff == 0:
                # Today's events - cache for 1 hour
                return 60 * 60
            elif days_diff <= 7:
                # This week's events - cache for 12 hours
                return 60 * 60 * 12
            else:
                # Future events - cache for 24 hours
                return 60 * 60 * 24

        except ValueError as e:
            logger.error(f"Invalid date format: {date_str}. Error: {e}")
            # Default to 24 hours
            return 60 * 60 * 24

    async def set(
        self, key_prefix: str, identifier: str, data: Any, ttl: Optional[int] = None
    ) -> bool:
        """
        Set data in the cache.

        Args:
            key_prefix: Prefix for the cache key
            identifier: Unique identifier for the cache key
            data: Data to store in the cache
            ttl: Time-to-live in seconds, or None for no expiration

        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            logger.warning("Redis not connected - skipping cache operation")
            return False

        try:
            cache_key = self._get_cache_key(key_prefix, identifier)

            # Convert data to JSON
            if isinstance(data, (list, dict, str, int, float, bool)):
                data_json = json.dumps(data)
            else:
                data_json = json.dumps(data, cls=EventDTOEncoder)

            # Set in Redis with TTL if provided
            if ttl is not None:
                self.redis_client.setex(cache_key, ttl, data_json)
            else:
                self.redis_client.set(cache_key, data_json)

            logger.info(f"Cached data with key {cache_key} and TTL {ttl} seconds")
            return True

        except Exception as e:
            logger.error(f"Error setting data in cache: {str(e)}")
            return False

    async def get(self, key_prefix: str, identifier: str) -> Optional[Any]:
        """
        Get data from the cache.

        Args:
            key_prefix: Prefix for the cache key
            identifier: Unique identifier for the cache key

        Returns:
            Cached data if found, None otherwise
        """
        if not self.is_connected():
            logger.warning("Redis not connected - skipping cache operation")
            return None

        try:
            cache_key = self._get_cache_key(key_prefix, identifier)
            cached_data = self.redis_client.get(cache_key)

            if cached_data:
                logger.info(f"Cache hit for {cache_key}")
                return json.loads(cached_data)

            logger.info(f"Cache miss for {cache_key}")
            return None

        except Exception as e:
            logger.error(f"Error getting data from cache: {str(e)}")
            return None

    async def delete(self, key_prefix: str, identifier: str) -> bool:
        """
        Delete data from the cache.

        Args:
            key_prefix: Prefix for the cache key
            identifier: Unique identifier for the cache key

        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            logger.warning("Redis not connected - skipping cache operation")
            return False

        try:
            cache_key = self._get_cache_key(key_prefix, identifier)
            self.redis_client.delete(cache_key)
            logger.info(f"Deleted cache key {cache_key}")
            return True

        except Exception as e:
            logger.error(f"Error deleting data from cache: {str(e)}")
            return False

    async def cache_events(self, date_str: str, events: List[EventDTO]) -> bool:
        """
        Cache events for a specific date.

        Args:
            date_str: Date string to use as identifier
            events: List of events to cache

        Returns:
            True if successful, False otherwise
        """
        ttl = self._get_ttl(date_str)
        return await self.set("events", date_str, events, ttl)

    async def get_cached_events(self, date_str: str) -> Optional[List[dict]]:
        """
        Get cached events for a specific date.

        Args:
            date_str: Date string to use as identifier

        Returns:
            List of cached events if found, None otherwise
        """
        return await self.get("events", date_str)

    async def clear_events_cache(self, date_str: str) -> bool:
        """
        Clear cached events for a specific date.

        Args:
            date_str: Date string to use as identifier

        Returns:
            True if successful, False otherwise
        """
        return await self.delete("events", date_str)


# Create a global Redis cache instance
redis_cache = RedisCache()
