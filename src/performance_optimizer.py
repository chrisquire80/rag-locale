"""
Performance Optimizer for RAG LOCALE Quality Improvements
Implements caching, batch processing, and performance tuning
"""

import time
from typing import Dict, List, Optional, Any, Tuple
from functools import lru_cache, wraps
from datetime import datetime, timedelta
import threading
import importlib

from src.logging_config import get_logger

logger = get_logger(__name__)

class CacheManager:
    """Manages caching for expensive operations"""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        """
        Initialize cache manager

        Args:
            max_size: Maximum cache entries
            ttl_seconds: Time-to-live for cache entries
        """
        self.cache = {}
        self.timestamps = {}
        self.max_size = max_size
        self.ttl = timedelta(seconds=ttl_seconds)
        self.lock = threading.Lock()
        logger.info(f"Cache initialized: max_size={max_size}, ttl={ttl_seconds}s")

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        with self.lock:
            if key not in self.cache:
                return None

            # Check expiration
            if datetime.now() - self.timestamps[key] > self.ttl:
                del self.cache[key]
                del self.timestamps[key]
                return None

            return self.cache[key]

    def set(self, key: str, value: Any) -> None:
        """Set value in cache with timestamp"""
        with self.lock:
            # Evict old entry if max size reached
            if len(self.cache) >= self.max_size:
                oldest_key = min(self.timestamps, key=self.timestamps.get)
                del self.cache[oldest_key]
                del self.timestamps[oldest_key]
                logger.debug(f"Evicted cache entry: {oldest_key}")

            self.cache[key] = value
            self.timestamps[key] = datetime.now()

    def clear(self) -> None:
        """Clear all cache"""
        with self.lock:
            self.cache.clear()
            self.timestamps.clear()
            logger.info("Cache cleared")

    def size(self) -> int:
        """Get current cache size"""
        return len(self.cache)

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl.total_seconds(),
            "entries": list(self.cache.keys())[:10]  # Show first 10 keys
        }

class BatchProcessor:
    """Process items in batches for better performance"""

    def __init__(self, batch_size: int = 10, timeout_seconds: float = 5.0):
        """
        Initialize batch processor

        Args:
            batch_size: Items per batch
            timeout_seconds: Timeout before processing partial batch
        """
        self.batch_size = batch_size
        self.timeout = timeout_seconds
        self.batch = []
        self.timestamps = []
        self.lock = threading.Lock()
        logger.info(f"Batch processor initialized: batch_size={batch_size}")

    def add(self, item: Any) -> Optional[List[Any]]:
        """
        Add item to batch, return full batch if ready

        Args:
            item: Item to add

        Returns:
            Batch if full/timeout, None otherwise
        """
        with self.lock:
            self.batch.append(item)
            self.timestamps.append(datetime.now())

            # Check if batch is full
            if len(self.batch) >= self.batch_size:
                result = self.batch.copy()
                self.batch = []
                self.timestamps = []
                logger.debug(f"Batch full: {len(result)} items")
                return result

            # Check if timeout reached
            if len(self.batch) > 0:
                age = (datetime.now() - self.timestamps[0]).total_seconds()
                if age >= self.timeout:
                    result = self.batch.copy()
                    self.batch = []
                    self.timestamps = []
                    logger.debug(f"Batch timeout: {len(result)} items after {age:.1f}s")
                    return result

            return None

    def flush(self) -> Optional[List[Any]]:
        """Flush remaining items in batch"""
        with self.lock:
            if not self.batch:
                return None
            result = self.batch.copy()
            self.batch = []
            self.timestamps = []
            logger.debug(f"Batch flushed: {len(result)} items")
            return result

class PerformanceMonitor:
    """Monitor and report performance metrics"""

    def __init__(self):
        """Initialize performance monitor"""
        self.metrics = {}
        self.lock = threading.Lock()
        logger.info("Performance monitor initialized")

    def record_operation(self, operation: str, duration_ms: float, success: bool = True) -> None:
        """
        Record operation performance

        Args:
            operation: Operation name
            duration_ms: Duration in milliseconds
            success: Whether operation succeeded
        """
        with self.lock:
            if operation not in self.metrics:
                self.metrics[operation] = {
                    "count": 0,
                    "total_ms": 0,
                    "min_ms": float('inf'),
                    "max_ms": 0,
                    "errors": 0
                }

            m = self.metrics[operation]
            m["count"] += 1
            m["total_ms"] += duration_ms
            m["min_ms"] = min(m["min_ms"], duration_ms)
            m["max_ms"] = max(m["max_ms"], duration_ms)
            if not success:
                m["errors"] += 1

    def get_stats(self, operation: Optional[str] = None) -> Dict[str, Any]:
        """
        Get performance statistics

        Args:
            operation: Specific operation or None for all

        Returns:
            Performance statistics
        """
        with self.lock:
            if operation:
                if operation not in self.metrics:
                    return {"error": f"No metrics for {operation}"}
                m = self.metrics[operation]
                return {
                    "operation": operation,
                    "count": m["count"],
                    "avg_ms": m["total_ms"] / m["count"] if m["count"] > 0 else 0,
                    "min_ms": m["min_ms"],
                    "max_ms": m["max_ms"],
                    "errors": m["errors"]
                }
            else:
                # Return all
                result = {}
                for op, m in self.metrics.items():
                    result[op] = {
                        "count": m["count"],
                        "avg_ms": m["total_ms"] / m["count"] if m["count"] > 0 else 0,
                        "min_ms": m["min_ms"],
                        "max_ms": m["max_ms"],
                        "errors": m["errors"]
                    }
                return result

    def clear(self) -> None:
        """Clear all metrics"""
        with self.lock:
            self.metrics.clear()
            logger.info("Performance metrics cleared")

class PerformanceDecorator:
    """Decorator for automatic performance monitoring"""

    def __init__(self, monitor: PerformanceMonitor):
        """Initialize with monitor"""
        self.monitor = monitor

    def track(self, operation_name: str):
        """
        Decorator to track operation performance

        Usage:
            @track_performance("query_expansion")
            def my_function():
                pass
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    self.monitor.record_operation(operation_name, elapsed_ms, success=True)
                    return result
                except Exception as e:
                    elapsed_ms = (time.perf_counter() - start) * 1000
                    self.monitor.record_operation(operation_name, elapsed_ms, success=False)
                    raise
            return wrapper
        return decorator

class LazyLoader:
    """Lazy load expensive modules only when needed"""

    def __init__(self):
        """Initialize lazy loader"""
        self.modules = {}
        self.lock = threading.Lock()
        logger.info("Lazy loader initialized")

    def get_module(self, module_path: str, module_name: str):
        """
        Lazy load module

        Args:
            module_path: Import path
            module_name: Module name

        Returns:
            Loaded module
        """
        with self.lock:
            if module_name not in self.modules:
                try:
                    module = importlib.import_module(module_path)
                    self.modules[module_name] = module
                except (ImportError, AttributeError) as e:
                    logger.error(f"Failed to lazy load {module_name}: {e}")
                    return None

            return self.modules[module_name]

# Global instances
_cache_manager = None
_batch_processor = None
_performance_monitor = None
_lazy_loader = None

def get_cache_manager(max_size: int = 1000, ttl_seconds: int = 3600) -> CacheManager:
    """Get or create global cache manager"""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager(max_size=max_size, ttl_seconds=ttl_seconds)
    return _cache_manager

def get_batch_processor(batch_size: int = 10, timeout_seconds: float = 5.0) -> BatchProcessor:
    """Get or create global batch processor"""
    global _batch_processor
    if _batch_processor is None:
        _batch_processor = BatchProcessor(batch_size=batch_size, timeout_seconds=timeout_seconds)
    return _batch_processor

def get_performance_monitor() -> PerformanceMonitor:
    """Get or create global performance monitor"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor

def get_lazy_loader() -> LazyLoader:
    """Get or create global lazy loader"""
    global _lazy_loader
    if _lazy_loader is None:
        _lazy_loader = LazyLoader()
    return _lazy_loader

def cached_operation(ttl_seconds: int = 3600):
    """
    Decorator for caching function results

    Usage:
        @cached_operation(ttl_seconds=3600)
        def expensive_function(query):
            return result
    """
    def decorator(func):
        cache = get_cache_manager(ttl_seconds=ttl_seconds)

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

            # Try to get from cache
            result = cache.get(cache_key)
            if result is not None:
                logger.debug(f"Cache hit: {func.__name__}")
                return result

            # Execute function
            result = func(*args, **kwargs)

            # Store in cache
            cache.set(cache_key, result)
            logger.debug(f"Cache miss, stored: {func.__name__}")
            return result

        return wrapper
    return decorator

if __name__ == "__main__":

    # Test cache manager
    print("\n=== Cache Manager Test ===")
    cache = get_cache_manager(max_size=100, ttl_seconds=60)
    cache.set("key1", "value1")
    print(f"Retrieved: {cache.get('key1')}")
    print(f"Stats: {cache.stats()}")

    # Test batch processor
    print("\n=== Batch Processor Test ===")
    batch = get_batch_processor(batch_size=5, timeout_seconds=1.0)
    for i in range(3):
        result = batch.add(f"item_{i}")
        if result:
            print(f"Batch ready: {result}")
    result = batch.flush()
    print(f"Flushed: {result}")

    # Test performance monitor
    print("\n=== Performance Monitor Test ===")
    monitor = get_performance_monitor()
    monitor.record_operation("query", 150.5)
    monitor.record_operation("query", 200.0)
    monitor.record_operation("rerank", 500.0, success=False)
    print(f"Query stats: {monitor.get_stats('query')}")
    print(f"All stats: {monitor.get_stats()}")
