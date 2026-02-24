"""
Unified caching system for RAG LOCALE
Consolidates caching logic across rag_engine, async_rag_engine, and vector_store
"""

import time
from typing import Optional, Any, Dict
from collections import OrderedDict
from dataclasses import dataclass

from src.config import config

from src.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class CacheEntry:
    """Single cache entry with TTL tracking"""
    value: Any
    timestamp: float
    ttl: int  # Time to live in seconds

    def is_expired(self) -> bool:
        """Check if entry has expired"""
        return time.time() - self.timestamp > self.ttl

class CacheManager:
    """
    Unified cache manager with LRU eviction and TTL support.

    Replaces duplicate implementations in:
    - src/rag_engine.py (lines 55-77)
    - src/async_rag_engine.py (lines 34-55)
    - src/performance_optimizer.py (lines 16-79)
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """
        Initialize cache manager.

        Args:
            max_size: Maximum number of entries before LRU eviction
            default_ttl: Default time-to-live in seconds (1 hour)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value if found and not expired, None otherwise
        """
        if key not in self._cache:
            self._misses += 1
            return None

        entry = self._cache[key]

        # Check if expired
        if entry.is_expired():
            del self._cache[key]
            self._misses += 1
            logger.debug(f"Cache entry expired: {key}")
            return None

        # Move to end (LRU)
        self._cache.move_to_end(key)
        self._hits += 1
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache with optional TTL override.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Override default TTL in seconds
        """
        ttl = ttl or self.default_ttl
        self._cache[key] = CacheEntry(value=value, timestamp=time.time(), ttl=ttl)

        # Move to end (most recently used)
        self._cache.move_to_end(key)

        # Evict oldest entry if exceeds max size
        while len(self._cache) > self.max_size:
            removed_key, _ = self._cache.popitem(last=False)
            logger.debug(f"Cache evicted (LRU): {removed_key}")

    def clear_expired(self) -> int:
        """
        Remove all expired entries.

        Returns:
            Number of entries removed
        """
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.debug(f"Cleared {len(expired_keys)} expired cache entries")

        return len(expired_keys)

    def clear(self) -> None:
        """Clear entire cache"""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.debug("Cache cleared")

    def get_hit_rate(self) -> float:
        """
        Get cache hit rate percentage.

        Returns:
            Hit rate as percentage (0-100), or 0 if no accesses
        """
        total = self._hits + self._misses
        if total == 0:
            return 0.0
        return (self._hits / total) * 100

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with hit rate, size, max size
        """
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_percent": self.get_hit_rate(),
            "size": len(self._cache),
            "max_size": self.max_size,
        }

    def __len__(self) -> int:
        """Return current cache size"""
        return len(self._cache)

class QueryExpansionCache(CacheManager):
    """
    Specialized cache for query expansion variants (FASE 8: Feature 3).
    Uses LRU eviction with 1-hour TTL for query expansion results.
    Expected cache hit rate: 50%+ (typical user query patterns repeat)
    """

    def __init__(self, max_size: int = 500):
        """
        Initialize QueryExpansionCache.

        Args:
            max_size: Maximum number of query variants to cache (default: 500)
        """
        super().__init__(max_size=max_size, default_ttl=3600)  # 1 hour TTL
        logger.debug("Initialized QueryExpansionCache (1-hour TTL)")

class VisionProcessingCache(CacheManager):
    """
    Specialized cache for vision processing results (FASE 8: Feature 3).
    Uses image hash-based keys with 24-hour TTL for OCR and image analysis results.
    Expected cache hit rate: 70%+ (batch document ingestion repeats)
    """

    def __init__(self, max_size: int = 1000):
        """
        Initialize VisionProcessingCache.

        Args:
            max_size: Maximum number of processed images to cache (default: 1000)
        """
        super().__init__(max_size=max_size, default_ttl=86400)  # 24 hour TTL
        logger.debug("Initialized VisionProcessingCache (24-hour TTL)")

    def get_by_hash(self, image_hash: str) -> Optional[Any]:
        """Get cached result by image hash."""
        return self.get(f"image_{image_hash}")

    def set_by_hash(self, image_hash: str, result: Any) -> None:
        """Cache result by image hash."""
        self.set(f"image_{image_hash}", result, ttl=self.default_ttl)

# Global singletons for different cache purposes
_query_result_cache: Optional[CacheManager] = None
_embedding_cache: Optional[CacheManager] = None
_query_expansion_cache: Optional[QueryExpansionCache] = None
_vision_processing_cache: Optional[VisionProcessingCache] = None

def get_query_result_cache() -> CacheManager:
    """Get singleton query result cache (from PerformanceConfig)"""
    global _query_result_cache
    if _query_result_cache is None:
        _query_result_cache = CacheManager(
            max_size=config.performance.cache_max_size,
            default_ttl=config.performance.cache_ttl_seconds
        )
        logger.debug("Initialized query result cache")
    return _query_result_cache

def get_embedding_cache() -> CacheManager:
    """Get singleton embedding cache (24-hour TTL)"""
    global _embedding_cache
    if _embedding_cache is None:
        _embedding_cache = CacheManager(max_size=5000, default_ttl=86400)
        logger.debug("Initialized embedding cache")
    return _embedding_cache

def get_query_expansion_cache() -> QueryExpansionCache:
    """Get singleton query expansion cache (1-hour TTL, FASE 8)"""
    global _query_expansion_cache
    if _query_expansion_cache is None:
        _query_expansion_cache = QueryExpansionCache(max_size=500)
    return _query_expansion_cache

def get_vision_processing_cache() -> VisionProcessingCache:
    """Get singleton vision processing cache (24-hour TTL, FASE 8)"""
    global _vision_processing_cache
    if _vision_processing_cache is None:
        _vision_processing_cache = VisionProcessingCache(max_size=1000)
    return _vision_processing_cache

def clear_all_caches() -> None:
    """Clear all global caches (useful for shutdown/cleanup)"""
    if _query_result_cache:
        _query_result_cache.clear()
    if _embedding_cache:
        _embedding_cache.clear()
    if _query_expansion_cache:
        _query_expansion_cache.clear()
    if _vision_processing_cache:
        _vision_processing_cache.clear()
    logger.info("All caches cleared")
