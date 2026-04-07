from __future__ import annotations

import copy
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict


logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Stores a cached value alongside its creation timestamp."""

    value: Any
    created_at: float


class AstrologyCache:
    """
    Lightweight in-memory cache for expensive astrology results.

    The cache is namespaced and keyed by ``user_id`` to preserve backward
    compatibility with the current service APIs while allowing targeted
    invalidation later.
    """

    def __init__(self, *, default_ttl_seconds: int | None = 900):
        self.default_ttl_seconds = default_ttl_seconds
        self._lock = threading.RLock()
        self._store: Dict[str, Dict[int, CacheEntry]] = {}

    def get(self, namespace: str, user_id: int, *, ttl_seconds: int | None = None) -> Any | None:
        """Returns a deep-copied cached value or ``None`` when absent or expired."""
        with self._lock:
            namespace_store = self._store.get(namespace, {})
            entry = namespace_store.get(int(user_id))
            if entry is None:
                logger.debug("Cache miss for namespace=%s user_id=%s.", namespace, user_id)
                return None

            max_age = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
            if max_age is not None and (time.time() - entry.created_at) > max_age:
                namespace_store.pop(int(user_id), None)
                logger.debug("Cache expired for namespace=%s user_id=%s.", namespace, user_id)
                return None

            logger.debug("Cache hit for namespace=%s user_id=%s.", namespace, user_id)
            return copy.deepcopy(entry.value)

    def set(self, namespace: str, user_id: int, value: Any) -> None:
        """Stores a deep-copied value in the cache."""
        with self._lock:
            namespace_store = self._store.setdefault(namespace, {})
            namespace_store[int(user_id)] = CacheEntry(value=copy.deepcopy(value), created_at=time.time())
            logger.debug("Cache set for namespace=%s user_id=%s.", namespace, user_id)

    def invalidate_user(self, user_id: int, namespaces: list[str] | tuple[str, ...] | None = None) -> None:
        """Removes cached entries for one user across selected namespaces or all namespaces."""
        with self._lock:
            target_namespaces = namespaces or tuple(self._store.keys())
            for namespace in target_namespaces:
                namespace_store = self._store.get(namespace)
                if namespace_store is not None:
                    namespace_store.pop(int(user_id), None)
            logger.debug("Cache invalidated for user_id=%s namespaces=%s.", user_id, list(target_namespaces))

    def clear(self, namespaces: list[str] | tuple[str, ...] | None = None) -> None:
        """Clears all cached entries, optionally restricting to specific namespaces."""
        with self._lock:
            if namespaces is None:
                self._store.clear()
                logger.info("Cleared all astrology caches.")
                return

            for namespace in namespaces:
                self._store.pop(namespace, None)
            logger.info("Cleared astrology caches for namespaces=%s.", list(namespaces))


_GLOBAL_CACHE = AstrologyCache()


def get_astrology_cache() -> AstrologyCache:
    """Returns the shared application cache instance."""
    return _GLOBAL_CACHE
