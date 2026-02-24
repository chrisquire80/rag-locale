"""
Query Analytics Module
Analyzes query patterns, performance trends, and metrics aggregations
"""

import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from ._loader import load_metrics, parse_timestamp, get_last_n_hours_metrics

logger = logging.getLogger(__name__)


class QueryAnalyzer:
    """Analyze query metrics for performance and usage insights"""

    def __init__(self, metrics_file: Path = None):
        self.metrics_file = metrics_file or Path("logs/metrics.jsonl")
        self.data = load_metrics(self.metrics_file)
        self.queries = [m for m in self.data if m.get('type') == 'query']

    def get_query_volume_trend(self, hours: int = 24) -> Dict:
        """
        Get query volume aggregated by hour

        Returns:
            Dict with timestamps and query counts
            {
                'timestamps': ['2024-02-23 10:00', ...],
                'volumes': [5, 3, 8, ...]
            }
        """
        recent_queries = get_last_n_hours_metrics(self.queries, hours)

        # Aggregate by hour
        hourly_counts = defaultdict(int)
        for metric in recent_queries:
            ts = parse_timestamp(metric.get('timestamp'))
            hour_key = ts.replace(minute=0, second=0, microsecond=0).isoformat()
            hourly_counts[hour_key] += 1

        # Sort by timestamp
        sorted_times = sorted(hourly_counts.keys())

        return {
            'timestamps': sorted_times,
            'volumes': [hourly_counts[ts] for ts in sorted_times],
            'total_queries': len(recent_queries),
            'avg_per_hour': len(recent_queries) / hours if hours > 0 else 0,
        }

    def get_slowest_queries(self, top_n: int = 10, hours: int = 24) -> List[Dict]:
        """
        Get slowest queries with full details

        Returns:
            List of query dicts sorted by total latency (descending)
        """
        recent_queries = get_last_n_hours_metrics(self.queries, hours)

        # Extract slow queries
        slow_queries = []
        for metric in recent_queries:
            data = metric.get('data', {})
            query_text = data.get('query_text', 'Unknown')
            search_latency = data.get('search_latency_ms', 0)
            llm_latency = data.get('llm_latency_ms', 0)
            total_latency = search_latency + llm_latency
            timestamp = parse_timestamp(metric.get('timestamp'))

            slow_queries.append({
                'query': query_text,
                'total_ms': total_latency,
                'search_ms': search_latency,
                'llm_ms': llm_latency,
                'timestamp': timestamp.isoformat(),
            })

        # Sort by total latency
        slow_queries.sort(key=lambda x: x['total_ms'], reverse=True)

        return slow_queries[:top_n]

    def get_latency_breakdown(self, hours: int = 24) -> Dict:
        """
        Get performance breakdown: search latency vs LLM latency

        Returns:
            Dict with average and distribution metrics
        """
        recent_queries = get_last_n_hours_metrics(self.queries, hours)

        search_latencies = []
        llm_latencies = []

        for metric in recent_queries:
            data = metric.get('data', {})
            search = data.get('search_latency_ms', 0)
            llm = data.get('llm_latency_ms', 0)

            if search > 0:
                search_latencies.append(search)
            if llm > 0:
                llm_latencies.append(llm)

        def get_stats(values):
            if not values:
                return {'avg': 0, 'min': 0, 'max': 0, 'p95': 0}
            sorted_vals = sorted(values)
            return {
                'avg': sum(values) / len(values),
                'min': min(values),
                'max': max(values),
                'p95': sorted_vals[int(len(sorted_vals) * 0.95)],
            }

        return {
            'search': get_stats(search_latencies),
            'llm': get_stats(llm_latencies),
            'total_queries': len(recent_queries),
        }

    def get_cache_effectiveness(self, hours: int = 24) -> Dict:
        """
        Get cache hit rate by hour

        Returns:
            Dict with hourly cache hit rates
        """
        recent_queries = get_last_n_hours_metrics(self.queries, hours)

        # Aggregate by hour
        hourly_hits = defaultdict(lambda: {'hits': 0, 'total': 0})

        for metric in recent_queries:
            ts = parse_timestamp(metric.get('timestamp'))
            hour_key = ts.replace(minute=0, second=0, microsecond=0).isoformat()
            data = metric.get('data', {})

            hourly_hits[hour_key]['total'] += 1
            if data.get('cache_hit', False):
                hourly_hits[hour_key]['hits'] += 1

        # Calculate hit rates
        sorted_times = sorted(hourly_hits.keys())
        hit_rates = []
        for ts in sorted_times:
            total = hourly_hits[ts]['total']
            hits = hourly_hits[ts]['hits']
            rate = (hits / total * 100) if total > 0 else 0
            hit_rates.append(rate)

        # Overall stats
        total_hits = sum(h['hits'] for h in hourly_hits.values())
        total_queries = sum(h['total'] for h in hourly_hits.values())
        overall_rate = (total_hits / total_queries * 100) if total_queries > 0 else 0

        return {
            'timestamps': sorted_times,
            'hit_rates': hit_rates,
            'overall_hit_rate': overall_rate,
            'total_cache_hits': total_hits,
            'total_queries': total_queries,
        }

    def get_query_success_stats(self, hours: int = 24) -> Dict:
        """
        Get success rate: % of queries that found documents

        Returns:
            Dict with success metrics
        """
        recent_queries = get_last_n_hours_metrics(self.queries, hours)

        # Aggregate by hour
        hourly_stats = defaultdict(lambda: {'success': 0, 'total': 0})

        for metric in recent_queries:
            ts = parse_timestamp(metric.get('timestamp'))
            hour_key = ts.replace(minute=0, second=0, microsecond=0).isoformat()
            data = metric.get('data', {})

            hourly_stats[hour_key]['total'] += 1
            docs_found = data.get('documents_found', 0)
            if docs_found > 0:
                hourly_stats[hour_key]['success'] += 1

        # Calculate success rates
        sorted_times = sorted(hourly_stats.keys())
        success_rates = []
        for ts in sorted_times:
            total = hourly_stats[ts]['total']
            success = hourly_stats[ts]['success']
            rate = (success / total * 100) if total > 0 else 0
            success_rates.append(rate)

        # Overall stats
        total_success = sum(s['success'] for s in hourly_stats.values())
        total_queries = sum(s['total'] for s in hourly_stats.values())
        overall_rate = (total_success / total_queries * 100) if total_queries > 0 else 0

        return {
            'timestamps': sorted_times,
            'success_rates': success_rates,
            'overall_success_rate': overall_rate,
            'successful_queries': total_success,
            'failed_queries': total_queries - total_success,
            'total_queries': total_queries,
        }

    def get_query_summary(self, hours: int = 24) -> Dict:
        """
        Get overall query summary statistics

        Returns:
            Dict with key metrics
        """
        recent_queries = get_last_n_hours_metrics(self.queries, hours)

        if not recent_queries:
            return {'status': 'No query data', 'total_queries': 0}

        latencies = []
        cache_hits = 0
        docs_found_list = []

        for metric in recent_queries:
            data = metric.get('data', {})
            latency = data.get('search_latency_ms', 0) + data.get('llm_latency_ms', 0)
            latencies.append(latency)

            if data.get('cache_hit', False):
                cache_hits += 1

            docs = data.get('documents_found', 0)
            docs_found_list.append(docs)

        return {
            'total_queries': len(recent_queries),
            'avg_latency_ms': sum(latencies) / len(latencies) if latencies else 0,
            'p95_latency_ms': sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0,
            'cache_hit_rate': cache_hits / len(recent_queries) if recent_queries else 0,
            'avg_docs_found': sum(docs_found_list) / len(docs_found_list) if docs_found_list else 0,
        }
