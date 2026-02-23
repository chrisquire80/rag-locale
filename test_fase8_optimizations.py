"""
Tests for Phase 8 Feature 3: Performance Optimizations
Tests QueryExpansionCache, VisionProcessingCache, and cache integration
"""

import pytest
import logging
import hashlib
from src.cache import (
    QueryExpansionCache,
    VisionProcessingCache,
    get_query_expansion_cache,
    get_vision_processing_cache,
    clear_all_caches
)

logger = logging.getLogger(__name__)


class TestQueryExpansionCache:
    """Test suite for QueryExpansionCache"""

    @pytest.fixture
    def cache(self):
        """Create a fresh QueryExpansionCache instance"""
        cache = QueryExpansionCache(max_size=100)
        cache.clear()
        return cache

    def test_qe_cache_initialization(self, cache):
        """Test QueryExpansionCache initializes with correct defaults"""
        assert cache is not None
        assert cache.max_size == 100
        assert cache.default_ttl == 3600  # 1 hour
        logger.info("✓ QueryExpansionCache initialized correctly")

    def test_qe_cache_set_and_get(self, cache):
        """Test setting and getting values in cache"""
        test_key = "test_query"
        test_value = ["expanded", "variant1", "variant2"]

        cache.set(test_key, test_value)
        retrieved = cache.get(test_key)

        assert retrieved == test_value
        logger.info("✓ Set/get works correctly")

    def test_qe_cache_hit_rate(self, cache):
        """Test cache hit rate tracking"""
        # Add items
        cache.set("query1", ["exp1", "exp2"])
        cache.set("query2", ["exp3", "exp4"])

        # Generate hits
        cache.get("query1")  # Hit
        cache.get("query1")  # Hit
        cache.get("query1")  # Hit
        cache.get("query_missing")  # Miss

        stats = cache.get_stats()
        assert stats['hits'] == 3
        assert stats['misses'] == 1
        hit_rate = stats['hit_rate_percent']
        assert hit_rate == 75.0  # 3 hits / 4 total
        logger.info(f"✓ Hit rate: {hit_rate}%")

    def test_qe_cache_lru_eviction(self):
        """Test LRU eviction when cache exceeds max_size"""
        cache = QueryExpansionCache(max_size=3)
        cache.clear()

        # Fill cache
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        assert len(cache) == 3

        # Access key1 to make it recently used
        cache.get("key1")

        # Add new item, should evict key2 (least recently used)
        cache.set("key4", "value4")

        assert len(cache) == 3
        assert cache.get("key2") is None  # key2 was evicted
        assert cache.get("key1") is not None  # key1 still there (accessed recently)
        logger.info("✓ LRU eviction works correctly")

    def test_qe_cache_expiration(self):
        """Test TTL and cache expiration"""
        import time
        cache = QueryExpansionCache(max_size=100)
        cache.clear()

        # Set with very short TTL (0.001 seconds)
        cache.set("expiring", "value", ttl=0.001)

        # Wait for expiration
        time.sleep(0.01)

        # Should be expired
        result = cache.get("expiring")
        assert result is None
        logger.info("✓ Expiration works correctly")


class TestVisionProcessingCache:
    """Test suite for VisionProcessingCache"""

    @pytest.fixture
    def cache(self):
        """Create a fresh VisionProcessingCache instance"""
        cache = VisionProcessingCache(max_size=100)
        cache.clear()
        return cache

    def test_vp_cache_initialization(self, cache):
        """Test VisionProcessingCache initializes with correct defaults"""
        assert cache is not None
        assert cache.max_size == 100
        assert cache.default_ttl == 86400  # 24 hours
        logger.info("✓ VisionProcessingCache initialized correctly")

    def test_vp_cache_set_and_get(self, cache):
        """Test setting and getting values in cache"""
        test_key = "vision_result"
        test_value = {"description": "test image", "labels": ["cat", "animal"]}

        cache.set(test_key, test_value)
        retrieved = cache.get(test_key)

        assert retrieved == test_value
        logger.info("✓ Set/get works correctly")

    def test_vp_cache_hash_based_operations(self, cache):
        """Test hash-based set/get for images"""
        # Create a test image hash
        image_data = b"test image content"
        image_hash = hashlib.sha256(image_data).hexdigest()[:16]

        # Use hash-based cache
        result = {"description": "test", "type": "image"}
        cache.set_by_hash(image_hash, result)

        retrieved = cache.get_by_hash(image_hash)
        assert retrieved == result
        logger.info("✓ Hash-based operations work correctly")

    def test_vp_cache_size_tracking(self, cache):
        """Test cache size tracking"""
        cache.set("item1", {"data": "value1"})
        cache.set("item2", {"data": "value2"})

        stats = cache.get_stats()
        assert stats['size'] == 2
        assert stats['max_size'] == 100
        logger.info(f"✓ Size tracking: {stats['size']}/{stats['max_size']}")


class TestCacheSingletons:
    """Test suite for cache singleton functions"""

    def test_get_query_expansion_cache_singleton(self):
        """Test that get_query_expansion_cache returns same instance"""
        cache1 = get_query_expansion_cache()
        cache2 = get_query_expansion_cache()

        assert cache1 is cache2  # Same object
        logger.info("✓ QueryExpansionCache singleton works")

    def test_get_vision_processing_cache_singleton(self):
        """Test that get_vision_processing_cache returns same instance"""
        cache1 = get_vision_processing_cache()
        cache2 = get_vision_processing_cache()

        assert cache1 is cache2  # Same object
        logger.info("✓ VisionProcessingCache singleton works")

    def test_cache_independence(self):
        """Test that different caches are independent"""
        qe_cache = get_query_expansion_cache()
        vp_cache = get_vision_processing_cache()

        qe_cache.set("test_key", "qe_value")
        vp_cache.set("test_key", "vp_value")

        # Each cache should have its own value
        assert qe_cache.get("test_key") == "qe_value"
        assert vp_cache.get("test_key") == "vp_value"
        logger.info("✓ Caches are independent")

    def test_clear_all_caches(self):
        """Test that clear_all_caches clears all cache instances"""
        qe_cache = get_query_expansion_cache()
        vp_cache = get_vision_processing_cache()

        # Add some data
        qe_cache.set("key1", "value1")
        vp_cache.set("key2", "value2")

        # Clear all
        clear_all_caches()

        # Both should be empty
        assert qe_cache.get("key1") is None
        assert vp_cache.get("key2") is None
        logger.info("✓ Clear all caches works correctly")


class TestCachePerformance:
    """Performance and integration tests for caches"""

    def test_qe_cache_performance_typical_usage(self):
        """Test QueryExpansionCache with typical usage patterns"""
        cache = get_query_expansion_cache()
        cache.clear()

        # Simulate typical usage: repeated queries
        queries = [
            ("machine learning", ["ML", "artificial intelligence"]),
            ("deep learning", ["neural networks", "deep models"]),
            ("machine learning", ["ML", "artificial intelligence"]),  # Repeat
            ("deep learning", ["neural networks", "deep models"]),    # Repeat
            ("nlp", ["natural language", "text processing"]),
        ]

        for query, expansions in queries:
            # Use cache if exists
            cached = cache.get(query)
            if cached is None:
                cache.set(query, expansions)
            else:
                assert cached == expansions

        stats = cache.get_stats()
        # Should have 2 hits from repeated queries
        assert stats['hits'] >= 2
        logger.info(f"✓ Performance test: {stats['hit_rate_percent']:.0f}% hit rate")

    def test_vp_cache_performance_batch_processing(self):
        """Test VisionProcessingCache with batch image processing"""
        cache = get_vision_processing_cache()
        cache.clear()

        # Simulate batch processing with some repeats
        image_hashes = [
            "abc123def456",  # New
            "xyz789uvw012",  # New
            "abc123def456",  # Repeat
            "xyz789uvw012",  # Repeat
            "qrs345tup678",  # New
        ]

        results_processed = 0
        results_cached = 0

        for img_hash in image_hashes:
            cached = cache.get_by_hash(img_hash)
            if cached is None:
                # Simulate processing
                cache.set_by_hash(img_hash, {"description": f"Image {img_hash[:8]}"})
                results_processed += 1
            else:
                results_cached += 1

        assert results_processed == 3  # 3 new images
        assert results_cached == 2     # 2 cached hits
        logger.info(f"✓ Batch test: {results_cached} cache hits, {results_processed} new processed")
