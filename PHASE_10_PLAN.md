# FASE 10: MONITORING & OBSERVABILITY - PLAN

**Status**: Planning
**Objective**: Add performance metrics, monitoring, and observability to the system
**Estimated Time**: 2-3 hours
**Target**: Track ingestion performance, API usage, query latency

---

## Overview

FASE 10 adds comprehensive monitoring to track:
1. **Ingestion Metrics** - Documents processed, time, chunks created
2. **API Metrics** - Embedding calls, rate limits, costs
3. **Query Metrics** - Search latency, cache hit rate
4. **System Metrics** - Memory, CPU, disk usage

---

## 10.1: Create Metrics Module

**File**: `src/metrics.py` (NEW)

```python
"""Performance metrics and monitoring"""

import time
import logging
from dataclasses import dataclass, asdict
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
    timestamp: datetime

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
    timestamp: datetime = None

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

        logger.info(
            f"Ingestion: {metrics.file_name} - "
            f"{metrics.chunks_created} chunks in {metrics.duration_seconds:.2f}s "
            f"({metrics.chunks_per_second:.1f} chunks/s)"
        )

    def record_query(self, metrics: QueryMetrics):
        """Record query metrics"""
        self.query_metrics.append(metrics)
        self._log_metric("query", metrics)

        cache_status = "HIT" if metrics.cache_hit else "MISS"
        logger.info(
            f"Query: {metrics.query_text[:50]}... - "
            f"Found {metrics.documents_found}/{metrics.documents_searched} docs - "
            f"Latency {metrics.total_latency_ms:.0f}ms (Search: {metrics.search_latency_ms:.0f}ms, LLM: {metrics.llm_latency_ms:.0f}ms) [{cache_status}]"
        )

    def record_api_call(self, metrics: APIMetrics):
        """Record API call metrics"""
        self.api_metrics.append(metrics)
        self._log_metric("api", metrics)

        if metrics.status_code >= 400:
            logger.error(
                f"API Error: {metrics.method} {metrics.endpoint} - "
                f"Status {metrics.status_code} - {metrics.latency_ms:.0f}ms"
            )
        else:
            logger.debug(
                f"API: {metrics.method} {metrics.endpoint} - "
                f"Status {metrics.status_code} - {metrics.latency_ms:.0f}ms"
            )

    def _log_metric(self, metric_type: str, metric_data):
        """Log metric to file (JSONL format)"""
        import json
        try:
            with open(self.metrics_file, "a") as f:
                log_entry = {
                    "type": metric_type,
                    "timestamp": datetime.now().isoformat(),
                    "data": asdict(metric_data) if hasattr(metric_data, '__dataclass_fields__') else metric_data
                }
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.warning(f"Failed to log metric: {e}")

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
        }

# Global metrics collector
_metrics_collector = None

def get_metrics_collector() -> MetricsCollector:
    """Get or create global metrics collector"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector
```

---

## 10.2: Integrate with Document Ingestion

**File**: `src/document_ingestion.py`

Add metrics collection to `ingest_single_file()`:

```python
def ingest_single_file(self, file_path: Path) -> int:
    """Ingest single file with metrics"""
    from metrics import get_metrics_collector
    import time

    metrics_collector = get_metrics_collector()
    start_time = time.perf_counter()

    try:
        file_size = file_path.stat().st_size

        # ... existing ingestion code ...

        chunks_created = count_added  # from add_documents return

        end_time = time.perf_counter()
        duration = end_time - start_time

        # Record success metrics
        from metrics import IngestionMetrics
        metrics = IngestionMetrics(
            file_name=file_path.name,
            file_size_bytes=file_size,
            chunks_created=chunks_created,
            embeddings_generated=chunks_created,  # 1:1 for now
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            success=True
        )
        metrics_collector.record_ingestion(metrics)

        return chunks_created

    except Exception as e:
        end_time = time.perf_counter()
        duration = end_time - start_time

        # Record failure metrics
        from metrics import IngestionMetrics
        metrics = IngestionMetrics(
            file_name=file_path.name,
            file_size_bytes=file_path.stat().st_size if file_path.exists() else 0,
            chunks_created=0,
            embeddings_generated=0,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            success=False,
            error=str(e)
        )
        metrics_collector.record_ingestion(metrics)
        raise
```

---

## 10.3: Integrate with RAG Engine

**File**: `src/rag_engine.py`

Add metrics to query path:

```python
def query(self, user_query: str, ...) -> RAGResponse:
    """Query with metrics"""
    import time
    from metrics import get_metrics_collector, QueryMetrics

    metrics_collector = get_metrics_collector()
    start_time = time.perf_counter()

    # Check if cache hit
    cache_key = self._get_cache_key(user_query, metadata_filter)
    cached = cache_key in self._query_cache

    search_start = time.perf_counter()
    retrieval_results = self._retrieve(...)
    search_end = time.perf_counter()

    llm_start = time.perf_counter()
    answer = self._generate_response(...)
    llm_end = time.perf_counter()

    # Record query metrics
    metrics = QueryMetrics(
        query_text=user_query,
        documents_searched=self.top_k,
        documents_found=len(retrieval_results),
        search_latency_ms=(search_end - search_start) * 1000,
        llm_latency_ms=(llm_end - llm_start) * 1000,
        cache_hit=cached,
        timestamp=datetime.now()
    )
    metrics_collector.record_query(metrics)

    return response
```

---

## 10.4: Metrics Dashboard/Report

**File**: `src/metrics_dashboard.py` (NEW)

```python
"""Metrics reporting and analytics"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List

class MetricsAnalyzer:
    """Analyze metrics data"""

    def __init__(self, metrics_file: Path):
        self.metrics_file = metrics_file
        self.data = self._load_metrics()

    def _load_metrics(self) -> List[Dict]:
        """Load metrics from JSONL file"""
        data = []
        if self.metrics_file.exists():
            with open(self.metrics_file) as f:
                for line in f:
                    try:
                        data.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return data

    def get_last_n_hours(self, hours: int = 24) -> List[Dict]:
        """Get metrics from last N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [
            m for m in self.data
            if datetime.fromisoformat(m['timestamp']) > cutoff
        ]

    def ingestion_summary(self) -> Dict:
        """Summary of ingestion metrics"""
        ingestions = [m for m in self.data if m['type'] == 'ingestion']

        if not ingestions:
            return {"message": "No ingestion data"}

        successful = sum(1 for m in ingestions if m['data'].get('success'))
        failed = len(ingestions) - successful
        total_chunks = sum(m['data'].get('chunks_created', 0) for m in ingestions)
        total_time = sum(m['data'].get('duration_seconds', 0) for m in ingestions)

        return {
            "total_files": len(ingestions),
            "successful": successful,
            "failed": failed,
            "total_chunks": total_chunks,
            "total_time_seconds": total_time,
            "avg_chunks_per_second": total_chunks / total_time if total_time > 0 else 0,
        }

    def query_summary(self) -> Dict:
        """Summary of query metrics"""
        queries = [m for m in self.data if m['type'] == 'query']

        if not queries:
            return {"message": "No query data"}

        latencies = [m['data'].get('total_latency_ms', 0) for m in queries]
        cache_hits = sum(1 for m in queries if m['data'].get('cache_hit'))

        return {
            "total_queries": len(queries),
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
            "min_latency_ms": min(latencies) if latencies else 0,
            "max_latency_ms": max(latencies) if latencies else 0,
            "cache_hit_rate": cache_hits / len(queries) if queries else 0,
        }

    def api_summary(self) -> Dict:
        """Summary of API call metrics"""
        apis = [m for m in self.data if m['type'] == 'api']

        if not apis:
            return {"message": "No API data"}

        errors = sum(1 for m in apis if m['data'].get('status_code', 0) >= 400)
        latencies = [m['data'].get('latency_ms', 0) for m in apis]

        return {
            "total_calls": len(apis),
            "errors": errors,
            "success_rate": (len(apis) - errors) / len(apis) if apis else 0,
            "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
        }

    def print_report(self):
        """Print formatted report"""
        print("\n" + "="*70)
        print("SYSTEM METRICS REPORT")
        print("="*70)

        print("\nINGESTION METRICS:")
        ing = self.ingestion_summary()
        for k, v in ing.items():
            print(f"  {k}: {v}")

        print("\nQUERY METRICS:")
        qry = self.query_summary()
        for k, v in qry.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.2f}")
            else:
                print(f"  {k}: {v}")

        print("\nAPI METRICS:")
        api = self.api_summary()
        for k, v in api.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.2f}")
            else:
                print(f"  {k}: {v}")

        print("\n" + "="*70)
```

---

## 10.5: Streamlit Metrics Dashboard

**File**: `src/metrics_ui.py` (NEW)

```python
"""Streamlit UI for metrics"""

import streamlit as st
from pathlib import Path
from metrics_dashboard import MetricsAnalyzer

def show_metrics_dashboard():
    """Display metrics in Streamlit"""
    st.sidebar.header("Metrics & Monitoring")

    metrics_file = Path("logs/metrics.jsonl")

    if not metrics_file.exists():
        st.sidebar.warning("No metrics data yet")
        return

    analyzer = MetricsAnalyzer(metrics_file)

    # Selector for time range
    time_range = st.sidebar.selectbox(
        "Time Range",
        ["Last 24h", "Last 7d", "All"]
    )

    # Display summaries
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("Ingestion")
        ing = analyzer.ingestion_summary()
        st.metric("Files Processed", ing.get("total_files", 0))
        st.metric("Success Rate", f"{ing.get('successful', 0)}/{ing.get('total_files', 0)}")

    with col2:
        st.subheader("Queries")
        qry = analyzer.query_summary()
        st.metric("Avg Latency", f"{qry.get('avg_latency_ms', 0):.0f}ms")
        st.metric("Cache Hit Rate", f"{qry.get('cache_hit_rate', 0)*100:.1f}%")

    with col3:
        st.subheader("API")
        api = analyzer.api_summary()
        st.metric("API Success Rate", f"{api.get('success_rate', 0)*100:.1f}%")
        st.metric("Errors", api.get("errors", 0))

    # Show full report
    if st.sidebar.button("Show Detailed Report"):
        analyzer.print_report()
        st.sidebar.success("Report printed to console")
```

---

## Implementation Sequence

1. **Create metrics.py** - Core metrics collection
2. **Create metrics_dashboard.py** - Analytics
3. **Create metrics_ui.py** - Streamlit dashboard
4. **Update document_ingestion.py** - Record ingestion metrics
5. **Update rag_engine.py** - Record query metrics
6. **Update llm_service.py** - Record API metrics (optional)
7. **Test** - Verify metrics collection and reporting

---

## Success Criteria

- ✅ Ingestion metrics recorded (file, chunks, time)
- ✅ Query metrics recorded (latency, cache hit)
- ✅ API metrics recorded (calls, status)
- ✅ Metrics persisted to logs/metrics.jsonl
- ✅ Metrics dashboard shows in Streamlit sidebar
- ✅ Report can be generated on demand
- ✅ No performance degradation (<5% overhead)
- ✅ Metrics queryable by time range

---

## Files to Create/Modify

| File | Type | Action |
|------|------|--------|
| `src/metrics.py` | Code | CREATE |
| `src/metrics_dashboard.py` | Code | CREATE |
| `src/metrics_ui.py` | Code | CREATE |
| `src/document_ingestion.py` | Code | MODIFY (add metrics) |
| `src/rag_engine.py` | Code | MODIFY (add metrics) |

---

This is the FASE 10 plan. Ready to implement step by step.
