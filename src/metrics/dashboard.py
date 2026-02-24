"""
Metrics reporting and analytics
Analyzes metrics data from metrics.jsonl
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricsAnalyzer:
    """Analyze metrics data"""

    def __init__(self, metrics_file: Path = None):
        from ._loader import load_metrics
        self.metrics_file = metrics_file or Path("logs/metrics.jsonl")
        self.data = load_metrics(self.metrics_file)

    def get_last_n_hours(self, hours: int = 24) -> List[Dict]:
        """Get metrics from last N hours"""
        from ._loader import get_last_n_hours_metrics
        return get_last_n_hours_metrics(self.data, hours) if hours else self.data

    def _parse_timestamp(self, ts_str: str) -> datetime:
        """Parse ISO format timestamp"""
        from ._loader import parse_timestamp
        return parse_timestamp(ts_str)

    def ingestion_summary(self, hours: Optional[int] = None) -> Dict:
        """Summary of ingestion metrics"""
        data = self.get_last_n_hours(hours) if hours else self.data
        ingestions = [m for m in data if m.get('type') == 'ingestion']

        if not ingestions:
            return {"message": "No ingestion data", "count": 0}

        successful = sum(1 for m in ingestions if m.get('data', {}).get('success'))
        failed = len(ingestions) - successful
        total_chunks = sum(m.get('data', {}).get('chunks_created', 0) for m in ingestions)
        total_time = sum(m.get('data', {}).get('duration_seconds', 0) for m in ingestions)
        total_size_mb = sum(m.get('data', {}).get('file_size_bytes', 0) for m in ingestions) / (1024*1024)

        return {
            "total_files": len(ingestions),
            "successful": successful,
            "failed": failed,
            "total_chunks": total_chunks,
            "total_time_seconds": round(total_time, 2),
            "total_size_mb": round(total_size_mb, 2),
            "avg_chunks_per_second": round(total_chunks / total_time, 2) if total_time > 0 else 0,
            "success_rate": round(successful / len(ingestions), 4) if ingestions else 0,
        }

    def query_summary(self, hours: Optional[int] = None) -> Dict:
        """Summary of query metrics"""
        data = self.get_last_n_hours(hours) if hours else self.data
        queries = [m for m in data if m.get('type') == 'query']

        if not queries:
            return {"message": "No query data", "count": 0}

        latencies = [m.get('data', {}).get('total_latency_ms', 0) for m in queries]
        cache_hits = sum(1 for m in queries if m.get('data', {}).get('cache_hit'))
        search_latencies = [m.get('data', {}).get('search_latency_ms', 0) for m in queries]
        llm_latencies = [m.get('data', {}).get('llm_latency_ms', 0) for m in queries]

        return {
            "total_queries": len(queries),
            "avg_latency_ms": round(sum(latencies) / len(latencies), 0) if latencies else 0,
            "min_latency_ms": round(min(latencies), 0) if latencies else 0,
            "max_latency_ms": round(max(latencies), 0) if latencies else 0,
            "p95_latency_ms": round(sorted(latencies)[int(len(latencies)*0.95)], 0) if len(latencies) > 20 else None,
            "avg_search_latency_ms": round(sum(search_latencies) / len(search_latencies), 0) if search_latencies else 0,
            "avg_llm_latency_ms": round(sum(llm_latencies) / len(llm_latencies), 0) if llm_latencies else 0,
            "cache_hit_rate": round(cache_hits / len(queries), 4) if queries else 0,
        }

    def api_summary(self, hours: Optional[int] = None) -> Dict:
        """Summary of API call metrics"""
        data = self.get_last_n_hours(hours) if hours else self.data
        apis = [m for m in data if m.get('type') == 'api']

        if not apis:
            return {"message": "No API data", "count": 0}

        errors = sum(1 for m in apis if m.get('data', {}).get('status_code', 0) >= 400)
        latencies = [m.get('data', {}).get('latency_ms', 0) for m in apis]

        return {
            "total_calls": len(apis),
            "errors": errors,
            "success_rate": round((len(apis) - errors) / len(apis), 4) if apis else 0,
            "avg_latency_ms": round(sum(latencies) / len(latencies), 0) if latencies else 0,
            "p95_latency_ms": round(sorted(latencies)[int(len(latencies)*0.95)], 0) if len(latencies) > 20 else None,
        }

    def get_slowest_files(self, n: int = 5) -> List[Dict]:
        """Get slowest ingested files"""
        ingestions = [m for m in self.data if m.get('type') == 'ingestion']
        sorted_by_time = sorted(
            ingestions,
            key=lambda m: m.get('data', {}).get('duration_seconds', 0),
            reverse=True
        )
        return [
            {
                "file": m.get('data', {}).get('file_name'),
                "time_seconds": m.get('data', {}).get('duration_seconds'),
                "chunks": m.get('data', {}).get('chunks_created'),
            }
            for m in sorted_by_time[:n]
        ]

    def get_slowest_queries(self, n: int = 5) -> List[Dict]:
        """Get slowest queries"""
        queries = [m for m in self.data if m.get('type') == 'query']
        sorted_by_latency = sorted(
            queries,
            key=lambda m: m.get('data', {}).get('total_latency_ms', 0),
            reverse=True
        )
        return [
            {
                "query": m.get('data', {}).get('query_text', '')[:50],
                "latency_ms": m.get('data', {}).get('total_latency_ms'),
                "documents_found": m.get('data', {}).get('documents_found'),
            }
            for m in sorted_by_latency[:n]
        ]

    def print_report(self, hours: Optional[int] = None):
        """Print formatted report"""
        print("\n" + "="*70)
        print("SYSTEM METRICS REPORT")
        if hours:
            print(f"Time Range: Last {hours} hours")
        print("="*70)

        # Ingestion
        print("\nINGESTION METRICS:")
        ing = self.ingestion_summary(hours)
        for k, v in ing.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.2f}")
            else:
                print(f"  {k}: {v}")

        if ing.get("total_files", 0) > 0:
            print("\n  Slowest files:")
            for i, file_info in enumerate(self.get_slowest_files(3), 1):
                print(f"    {i}. {file_info['file']} - {file_info['time_seconds']:.1f}s ({file_info['chunks']} chunks)")

        # Queries
        print("\nQUERY METRICS:")
        qry = self.query_summary(hours)
        for k, v in qry.items():
            if isinstance(v, float):
                if "rate" in k:
                    print(f"  {k}: {v*100:.1f}%")
                else:
                    print(f"  {k}: {v:.0f}")
            elif v is not None and v != "No query data":
                print(f"  {k}: {v}")

        if qry.get("total_queries", 0) > 0:
            print("\n  Slowest queries:")
            for i, query_info in enumerate(self.get_slowest_queries(3), 1):
                print(f"    {i}. {query_info['query']}... - {query_info['latency_ms']:.0f}ms")

        # API
        print("\nAPI METRICS:")
        api = self.api_summary(hours)
        for k, v in api.items():
            if isinstance(v, float):
                if "rate" in k:
                    print(f"  {k}: {v*100:.1f}%")
                else:
                    print(f"  {k}: {v:.0f}")
            elif v is not None and v != "No API data":
                print(f"  {k}: {v}")

        print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    analyzer = MetricsAnalyzer()
    analyzer.print_report()
