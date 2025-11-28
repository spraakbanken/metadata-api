"""Memcached client management."""

import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)


class CacheManager:
    """Manages the cache client instance."""

    def __init__(self) -> None:
        """Initialize the CacheManager without connecting."""
        self.server = None

    def initialize(self, cache_server: str) -> None:
        """Initialize the cache client."""
        self.server = cache_server
        if not self.server:
            logger.info("Caching server not configured. Caching is disabled.")
            return

        try:
            with self.get_client() as cache_client:
                cache_client.get("test_connection")
            logger.info("Connected to memcached on %s", cache_server)
        except Exception as e:
            logger.warning("Failed to connect to memcached on %s: %s", cache_server, e)

    @contextmanager
    def get_client(self) -> Generator[Any, None, None]:
        """Retrieve a connected Memcached client."""
        if self.server is None:
            logger.info("Caching is disabled.")
            yield None
            return

        try:
            from pymemcache import serde  # noqa: PLC0415
            from pymemcache.client.base import Client  # noqa: PLC0415
        except ImportError:
            logger.warning("Library pymemcache not available, disabling caching.")
            yield None
            return

        client: Client | None = None
        try:
            client = Client(self.server, serde=serde.pickle_serde)
            yield client
        except Exception:
            logger.exception("Error initializing memcache client")
            yield None

        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass


cache = CacheManager()
