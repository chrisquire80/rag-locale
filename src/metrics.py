"""
Performance metrics and monitoring system
Tracks ingestion, queries, and API calls
"""

import time
import logging
import json
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class IngestionMetrics:
    """Metrics for document ingestion"""
    file_name: str
    file_size_bytes: int
    chunks_created: int
    embeddings_generated: int
    start_time: float
    end_time: float
    duration_seconds: float
    success: bool
    error: Optional[str] = None

    @property
    def chunks_per_second(self) -> float:
        return self.chunks_created / self.duration_seconds if self.duration_seconds > 0 else 0

    @property
    def size_mb(self) -> float:
        return self.file_size_bytes / (1024 * 1024)


@dataclass
class QueryMetrics:
    """Metrics for RAG queries"""
    query_text: str
    documents_searched: int
    documents_found: int
    search_latency_ms: float
    llm_latency_ms: float
    cache_hit: bool
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def total_latency_ms(self) -> float:
        return self.search_latency_ms + self.llm_latency_ms


@dataclass
class APIMetrics:
    """Metrics for API calls"""
    endpoint: str
    method: str
    status_code: int
    latency_ms: float
    tokens_used: Optional[int] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class MetricsCollector:
    """Central metrics collection and reporting"""

    def __init__(self, metrics_file: Path = None):
        self.metrics_file = metrics_file or Path("logs/metrics.jsonl")
        self.ingestion_metrics: List[IngestionMetrics] = []
        self.query_metrics: List[QueryMetrics] = []
        self.api_metrics: List[APIMetrics] = []

        # Ensure logs directory exists
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

    def record_ingestion(self, metrics: IngestionMetrics):
        """Record ingestion metrics"""
        self.ingestion_metrics.append(metrics)
        self._log_metric("ingestion", metrics)

        if metrics.success:
            logger.info(
                f"[METRIC] Ingestion: {metrics.file_name} - "
                f"{metrics.chunks_created} chunks in {metrics.duration_seconds:.2f}s "
                f"({metrics.chunks_per_second:.1f} chunks/s) - {metrics.size_mb:.2f}MB"
            )
        else:
            logger.warning(
                f"[METRIC] Ingestion FAILED: {metrics.file_name} - {metrics.error}"
            )

    def record_query(self, metrics: QueryMetrics):
        """Record query metrics"""
        self.query_metrics.append(metrics)
        self._log_metric("query", metrics)

        cache_status = "HIT" if metrics.cache_hit else "MISS"
        logger.info(
            f"[METRIC] Query: Found {metrics.documents_found}/{metrics.documents_searched} docs - "
            f"Latency {metrics.total_latency_ms:.0f}ms "
            f"(Search: {metrics.search_latency_ms:.0f}ms, LLM: {metrics.llm_latency_ms:.0f}ms) [{cache_status}]"
        )

    def record_api_call(self, metrics: APIMetrics):
        """Record API call metrics"""
        self.api_metrics.append(metrics)
        self._log_metric("api", metrics)

        if metrics.status_code >= 400:
            logger.error(
                f"[METRIC] API Error: {metrics.method} {metrics.endpoint} - "
                f"Status {metrics.status_code} - {metrics.latency_ms:.0f}ms"
            )
        else:
            logger.debug(
                f"[METRIC] API: {metrics.method} {metrics.endpoint} - "
                f"Status {metrics.status_code} - {metrics.latency_ms:.0f}ms"
            )

    def _log_metric(self, metric_type: str, metric_data):
        """Log metric to file (JSONL format)"""
        try:
            with open(self.metrics_file, "a") as f:
                log_entry = {
                    "type": metric_type,
                    "timestamp": datetime.now().isoformat(),
                    "data": self._serialize_metric(metric_data)
                }
                f.write(json.dumps(log_entry, default=str) + "\n")
        except Exception as e:
            logger.warning(f"Failed to log metric: {e}")

    def _serialize_metric(self, metric_data) -> dict:
        """Convert metric to serializable dict"""
        if hasattr(metric_data, '__dataclass_fields__'):
            data = asdict(metric_data)
            # Convert datetime objects to ISO format
            for key, value in data.items():
                if isinstance(value, datetime):
                    data[key] = value.isoformat()
            return data
        return metric_data

    def get_summary(self) -> Dict:
        """Get summary statistics"""
        if not self.ingestion_metrics:
            return {"status": "No ingestion data"}

        total_files = len(self.ingestion_metrics)
        successful = sum(1 for m in self.ingestion_metrics if m.success)
        total_chunks = sum(m.chunks_created for m in self.ingestion_metrics)
        total_time = sum(m.duration_seconds for m in self.ingestion_metrics)
        total_size_mb = sum(m.size_mb for m in self.ingestion_metrics)

        return {
            "total_files": total_files,
            "successful_files": successful,
            "failed_files": total_files - successful,
            "total_chunks": total_chunks,
            "total_time_seconds": total_time,
            "total_size_mb": total_size_mb,
            "avg_chunks_per_second": total_chunks / total_time if total_time > 0 else 0,
            "avg_size_mb": total_size_mb / total_files if total_files > 0 else 0,
            "success_rate": successful / total_files if total_files > 0 else 0,
        }

    def get_query_stats(self) -> Dict:
        """Get query statistics"""
        if not self.query_metrics:
            return {"status": "No query data"}

        latencies = [m.total_latency_ms for m in self.query_metrics]
        cache_hits = sum(1 for m in self.query_metrics if m.cache_hit)

        return {
            "total_queries": len(self.query_metrics),
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
            "min_latency_ms": min(latencies) if latencies else 0,
            "max_latency_ms": max(latencies) if latencies else 0,
            "p95_latency_ms": sorted(latencies)[int(len(latencies)*0.95)] if latencies else 0,
            "cache_hit_rate": cache_hits / len(self.query_metrics) if self.query_metrics else 0,
            "avg_documents_found": sum(m.documents_found for m in self.query_metrics) / len(self.query_metrics) if self.query_metrics else 0,
        }

    def get_api_stats(self) -> Dict:
        """Get API statistics"""
        if not self.api_metrics:
            return {"status": "No API data"}

        errors = sum(1 for m in self.api_metrics if m.status_code >= 400)
        latencies = [m.latency_ms for m in self.api_metrics]

        return {
            "total_calls": len(self.api_metrics),
            "errors": errors,
            "success_rate": (len(self.api_metrics) - errors) / len(self.api_metrics) if self.api_metrics else 0,
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
            "p95_latency_ms": sorted(latencies)[int(len(latencies)*0.95)] if latencies else 0,
        }


# Global metrics collector
_metrics_collector = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create global metrics collector"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


if __name__ == "__main__":
    # Test metrics
    logging.basicConfig(level=logging.INFO)
    collector = get_metrics_collector()

    # Test ingestion metric
    metric1 = IngestionMetrics(
        file_name="test.pdf",
        file_size_bytes=1024000,
        chunks_created=10,
        embeddings_generated=10,
        start_time=time.time() - 5,
        end_time=time.time(),
        duration_seconds=5,
        success=True
    )
    collector.record_ingestion(metric1)

    # Test query metric
    metric2 = QueryMetrics(
        query_text="test query",
        documents_searched=5,
        documents_found=3,
        search_latency_ms=100,
        llm_latency_ms=5000,
        cache_hit=False
    )
    collector.record_query(metric2)

    # Print summary
    print("\nMetrics Summary:")
    print(f"Ingestion: {collector.get_summary()}")
    print(f"Queries: {collector.get_query_stats()}")
