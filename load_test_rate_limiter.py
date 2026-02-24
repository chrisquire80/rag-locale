#!/usr/bin/env python3
"""
Load Testing Script for Rate Limiter
Simulates concurrent API calls and measures rate limit behavior
"""

import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import List
import statistics

from src.rate_limiter import get_rate_limiter, rate_limit, RateLimitConfig


@dataclass
class TestResult:
    """Result of a single test call"""
    endpoint: str
    call_id: int
    success: bool
    wait_time: float
    error_msg: str = ""
    timestamp: float = 0.0


class LoadTester:
    """Load test the rate limiter"""

    def __init__(self, duration_seconds: int = 10):
        self.duration_seconds = duration_seconds
        self.results: List[TestResult] = []
        self.lock = threading.Lock()
        self.call_counter = 0
        self.start_time = None

    @rate_limit(endpoint_name="load_test_endpoint", tokens_cost=1.0)
    def simulated_api_call(self, endpoint: str) -> bool:
        """Simulate an API call that consumes 1 token"""
        time.sleep(0.01)  # Simulate 10ms API latency
        return True

    def run_call(self, endpoint: str, call_id: int) -> TestResult:
        """Execute a single test call"""
        try:
            start = time.time()
            self.simulated_api_call(endpoint)
            wait_time = time.time() - start

            result = TestResult(
                endpoint=endpoint,
                call_id=call_id,
                success=True,
                wait_time=wait_time,
                timestamp=start
            )
        except RuntimeError as e:
            if "Rate limit" in str(e):
                result = TestResult(
                    endpoint=endpoint,
                    call_id=call_id,
                    success=False,
                    wait_time=time.time() - start,
                    error_msg="Rate limited",
                    timestamp=start
                )
            else:
                result = TestResult(
                    endpoint=endpoint,
                    call_id=call_id,
                    success=False,
                    wait_time=time.time() - start,
                    error_msg=str(e),
                    timestamp=start
                )
        except Exception as e:
            result = TestResult(
                endpoint=endpoint,
                call_id=call_id,
                success=False,
                wait_time=time.time() - start,
                error_msg=f"Unexpected: {str(e)[:50]}",
                timestamp=start
            )

        with self.lock:
            self.results.append(result)

        return result

    def run_stress_test(self, num_workers: int = 10, requests_per_worker: int = 20):
        """Run load test with concurrent workers"""
        print(f"\n[Load Test] Starting stress test:")
        print(f"  Workers: {num_workers}")
        print(f"  Requests per worker: {requests_per_worker}")
        print(f"  Total requests: {num_workers * requests_per_worker}")
        print(f"  Rate limit: 10 tokens/sec (refill_rate from config)")
        print(f"  Expected rate-limited requests: ~{int((num_workers * requests_per_worker) * 0.3)}")
        print()

        self.start_time = time.time()
        call_id = 0

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []

            # Submit all requests
            for worker in range(num_workers):
                for req in range(requests_per_worker):
                    call_id += 1
                    future = executor.submit(
                        self.run_call,
                        f"endpoint_{worker}",
                        call_id
                    )
                    futures.append(future)

            # Wait for completion
            completed = 0
            for future in as_completed(futures):
                completed += 1
                if completed % (num_workers * 5) == 0:
                    limiter = get_rate_limiter()
                    print(f"  [{completed}/{len(futures)}] Completed - "
                          f"Tokens: {limiter.global_bucket.get_tokens():.1f} - "
                          f"Blocked: {limiter.blocked_requests}")

        print(f"\n[Load Test] Completed in {time.time() - self.start_time:.2f}s")

    def print_results(self):
        """Analyze and print test results"""
        print("\n" + "="*70)
        print("LOAD TEST RESULTS")
        print("="*70)

        total = len(self.results)
        successful = sum(1 for r in self.results if r.success)
        rate_limited = sum(1 for r in self.results if not r.success and "Rate limited" in r.error_msg)
        errors = sum(1 for r in self.results if not r.success and "Rate limited" not in r.error_msg)

        print(f"\nRequest Summary:")
        print(f"  Total requests: {total}")
        print(f"  Successful: {successful} ({100*successful/total:.1f}%)")
        print(f"  Rate limited: {rate_limited} ({100*rate_limited/total:.1f}%)")
        print(f"  Other errors: {errors} ({100*errors/total:.1f}%)")

        # Latency analysis
        if successful > 0:
            successful_times = [r.wait_time for r in self.results if r.success]
            print(f"\nLatency (successful requests):")
            print(f"  Min: {min(successful_times)*1000:.2f}ms")
            print(f"  Max: {max(successful_times)*1000:.2f}ms")
            print(f"  Avg: {statistics.mean(successful_times)*1000:.2f}ms")
            print(f"  P99: {sorted(successful_times)[int(len(successful_times)*0.99)]*1000:.2f}ms")

        # Rate limiting effectiveness
        limiter = get_rate_limiter()
        stats = limiter.get_stats()

        print(f"\nRate Limiter Stats:")
        print(f"  Total requests checked: {stats.get('total_requests', 0)}")
        print(f"  Blocked requests: {stats.get('blocked_requests', 0)}")
        print(f"  Blocking rate: {100*stats.get('blocked_requests', 0)/max(1, stats.get('total_requests', 1)):.1f}%")
        print(f"  Refill rate: {stats.get('refill_rate', 0):.1f} tokens/sec")
        print(f"  Bucket capacity: {stats.get('bucket_capacity', 0)}")

        # Time-series analysis
        if self.results:
            time_buckets = {}
            start = min(r.timestamp for r in self.results)
            for result in self.results:
                bucket = int((result.timestamp - start) * 10) // 1  # 100ms buckets
                if bucket not in time_buckets:
                    time_buckets[bucket] = {'success': 0, 'blocked': 0, 'error': 0}

                if result.success:
                    time_buckets[bucket]['success'] += 1
                elif "Rate limited" in result.error_msg:
                    time_buckets[bucket]['blocked'] += 1
                else:
                    time_buckets[bucket]['error'] += 1

            print(f"\nThroughput Timeline (100ms buckets):")
            for bucket in sorted(time_buckets.keys())[:10]:
                data = time_buckets[bucket]
                total_in_bucket = sum(data.values())
                print(f"  [{bucket:2d}] Success: {data['success']:2d}  Blocked: {data['blocked']:2d}  "
                      f"Errors: {data['error']:2d}  Total: {total_in_bucket:2d}")

        print("\n" + "="*70)


def main():
    """Run the load test"""
    print("\n" + "="*70)
    print("RATE LIMITER LOAD TEST")
    print("="*70)

    # Test 1: Light load
    print("\n[Test 1] Light Load (5 workers, 10 requests each)")
    tester = LoadTester()
    tester.run_stress_test(num_workers=5, requests_per_worker=10)
    tester.print_results()

    time.sleep(2)  # Reset between tests

    # Test 2: Medium load
    print("\n[Test 2] Medium Load (10 workers, 20 requests each)")
    tester = LoadTester()
    tester.run_stress_test(num_workers=10, requests_per_worker=20)
    tester.print_results()

    time.sleep(2)

    # Test 3: Heavy load (stress test)
    print("\n[Test 3] Heavy Load (20 workers, 30 requests each)")
    tester = LoadTester()
    tester.run_stress_test(num_workers=20, requests_per_worker=30)
    tester.print_results()

    print("\n[Summary] Load testing complete!")
    print("If rate limiting is working correctly:")
    print("  - Light load should have ~0% blocked")
    print("  - Medium load should have ~10-20% blocked")
    print("  - Heavy load should have ~40-50% blocked")


if __name__ == '__main__':
    main()
