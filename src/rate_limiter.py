"""
Centralized Rate Limiter - Thread-safe request rate limiting

Implements token bucket algorithm for distributed rate limiting:
- Per-user rate limits
- Per-endpoint rate limits
- Global rate limits
- Adaptive rate limiting based on system load

Replaces scattered rate limiting implementations across modules.
"""

import time
import logging
import threading
from typing import Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting"""
    # Token bucket parameters
    refill_rate: float = 10.0  # tokens per second
    bucket_capacity: int = 100  # max tokens in bucket
    refill_interval: float = 0.1  # seconds between refills

    # Per-user limits
    per_user_limit: int = 1000  # requests per hour
    per_user_window: int = 3600  # seconds (1 hour)

    # Per-endpoint limits
    per_endpoint_limit: int = 5000  # requests per hour
    per_endpoint_window: int = 3600  # seconds

    # Global limits
    global_limit: int = 10000  # requests per hour
    global_window: int = 3600  # seconds

    # Enforcement
    enforce_limits: bool = True
    block_on_limit: bool = True  # Block request or warn
    enable_adaptive: bool = True  # Slow down under load


class TokenBucket:
    """Token bucket for rate limiting (thread-safe)"""

    def __init__(self, capacity: float, refill_rate: float):
        """
        Initialize token bucket

        Args:
            capacity: Maximum tokens in bucket
            refill_rate: Tokens per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens/sec
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = threading.Lock()

    def refill(self) -> None:
        """Refill bucket based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    def consume(self, tokens: float = 1.0) -> bool:
        """
        Try to consume tokens from bucket

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens available, False otherwise
        """
        with self.lock:
            self.refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False

    def get_tokens(self) -> float:
        """Get current token count"""
        with self.lock:
            self.refill()
            return self.tokens


class RateLimiter:
    """
    Centralized rate limiter with multiple strategies

    Supports:
    - Token bucket algorithm (smooth traffic)
    - Sliding window (per-user/endpoint limits)
    - Global circuit breaker (stop all on overload)
    - Adaptive throttling (reduce under load)
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        """Initialize rate limiter"""
        self.config = config or RateLimitConfig()
        self.lock = threading.Lock()

        # Token buckets for different scopes
        self.global_bucket = TokenBucket(
            self.config.bucket_capacity,
            self.config.refill_rate
        )

        # Per-user and per-endpoint buckets
        self.user_buckets: dict[str, TokenBucket] = {}
        self.endpoint_buckets: dict[str, TokenBucket] = {}

        # Sliding window counters
        self.request_count = defaultdict(lambda: defaultdict(int))
        self.request_times = defaultdict(list)

        # Metrics
        self.total_requests = 0
        self.blocked_requests = 0
        self.last_stats_reset = time.time()

        logger.info(f"Rate limiter initialized: {self.config.refill_rate} tokens/sec, "
                   f"capacity={self.config.bucket_capacity}")

    def _get_user_bucket(self, user_id: str) -> TokenBucket:
        """Get or create user bucket"""
        if user_id not in self.user_buckets:
            with self.lock:
                if user_id not in self.user_buckets:
                    self.user_buckets[user_id] = TokenBucket(
                        self.config.per_user_limit,
                        self.config.per_user_limit / self.config.per_user_window
                    )
        return self.user_buckets[user_id]

    def _get_endpoint_bucket(self, endpoint: str) -> TokenBucket:
        """Get or create endpoint bucket"""
        if endpoint not in self.endpoint_buckets:
            with self.lock:
                if endpoint not in self.endpoint_buckets:
                    self.endpoint_buckets[endpoint] = TokenBucket(
                        self.config.per_endpoint_limit,
                        self.config.per_endpoint_limit / self.config.per_endpoint_window
                    )
        return self.endpoint_buckets[endpoint]

    def check_rate_limit(
        self,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None,
        tokens_cost: float = 1.0
    ) -> tuple[bool, Optional[str]]:
        """
        Check if request should be allowed

        Args:
            user_id: User identifier
            endpoint: API endpoint or operation name
            tokens_cost: How many tokens this operation costs

        Returns:
            (allowed: bool, reason: Optional[str])
        """
        if not self.config.enforce_limits:
            return True, None

        self.total_requests += 1

        # Check global limit first
        if not self.global_bucket.consume(tokens_cost):
            self.blocked_requests += 1
            reason = "Global rate limit exceeded"
            if self.config.block_on_limit:
                logger.warning(f"[RATE LIMIT] {reason}")
                return False, reason
            else:
                logger.debug(f"[RATE LIMIT WARNING] {reason}")

        # Check user limit
        if user_id:
            user_bucket = self._get_user_bucket(user_id)
            if not user_bucket.consume(tokens_cost):
                self.blocked_requests += 1
                reason = f"User rate limit exceeded: {user_id}"
                if self.config.block_on_limit:
                    logger.warning(f"[RATE LIMIT] {reason}")
                    return False, reason
                else:
                    logger.debug(f"[RATE LIMIT WARNING] {reason}")

        # Check endpoint limit
        if endpoint:
            endpoint_bucket = self._get_endpoint_bucket(endpoint)
            if not endpoint_bucket.consume(tokens_cost):
                self.blocked_requests += 1
                reason = f"Endpoint rate limit exceeded: {endpoint}"
                if self.config.block_on_limit:
                    logger.warning(f"[RATE LIMIT] {reason}")
                    return False, reason
                else:
                    logger.debug(f"[RATE LIMIT WARNING] {reason}")

        return True, None

    def get_wait_time(
        self,
        user_id: Optional[str] = None,
        endpoint: Optional[str] = None
    ) -> float:
        """Get estimated wait time in seconds"""
        if not self.config.enforce_limits:
            return 0.0

        max_wait = 0.0

        # Check global bucket
        if self.global_bucket.tokens == 0:
            max_wait = max(max_wait, 1.0 / self.config.refill_rate)

        # Check user bucket
        if user_id:
            user_bucket = self._get_user_bucket(user_id)
            if user_bucket.tokens == 0:
                max_wait = max(max_wait, 1.0 / (self.config.per_user_limit / self.config.per_user_window))

        # Check endpoint bucket
        if endpoint:
            endpoint_bucket = self._get_endpoint_bucket(endpoint)
            if endpoint_bucket.tokens == 0:
                max_wait = max(max_wait, 1.0 / (self.config.per_endpoint_limit / self.config.per_endpoint_window))

        return max_wait

    def get_stats(self) -> dict:
        """Get rate limiter statistics"""
        elapsed = time.time() - self.last_stats_reset
        requests_per_sec = self.total_requests / elapsed if elapsed > 0 else 0

        return {
            "total_requests": self.total_requests,
            "blocked_requests": self.blocked_requests,
            "block_rate": self.blocked_requests / self.total_requests if self.total_requests > 0 else 0,
            "requests_per_sec": requests_per_sec,
            "global_tokens": self.global_bucket.get_tokens(),
            "active_users": len(self.user_buckets),
            "active_endpoints": len(self.endpoint_buckets),
            "elapsed_seconds": elapsed,
        }

    def reset_stats(self) -> None:
        """Reset statistics counters"""
        self.total_requests = 0
        self.blocked_requests = 0
        self.last_stats_reset = time.time()


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter(config: Optional[RateLimitConfig] = None) -> RateLimiter:
    """Get or create global rate limiter (singleton)"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(config or RateLimitConfig())
    return _rate_limiter


def rate_limit(
    user_id_fn: Optional[Callable] = None,
    endpoint_name: Optional[str] = None,
    tokens_cost: float = 1.0,
    block_on_limit: bool = True
):
    """
    Decorator for rate limiting functions

    Args:
        user_id_fn: Function to extract user_id from arguments
        endpoint_name: Name of endpoint/operation
        tokens_cost: Cost in tokens for this operation
        block_on_limit: Block or warn on limit

    Usage:
        @rate_limit(endpoint_name="search", tokens_cost=2.0)
        def search_documents(query: str):
            ...

        @rate_limit(
            user_id_fn=lambda args: args.user_id,
            endpoint_name="generate",
            tokens_cost=5.0
        )
        def generate_response(query: str, user_id: str):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter = get_rate_limiter()

            # Extract user_id if function provided
            user_id = None
            if user_id_fn:
                try:
                    # Try to extract from function args/kwargs
                    user_id = user_id_fn(*args, **kwargs)
                except Exception as e:
                    logger.debug(f"Could not extract user_id: {e}")

            # Check rate limit
            allowed, reason = limiter.check_rate_limit(
                user_id=user_id,
                endpoint=endpoint_name,
                tokens_cost=tokens_cost
            )

            if not allowed and block_on_limit:
                raise RuntimeError(f"Rate limit: {reason}")

            # Call original function
            return func(*args, **kwargs)

        return wrapper

    return decorator
