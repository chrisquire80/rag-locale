"""
End-to-end tests for complete RAG Locale workflows
Simulates real user scenarios with actual data flows
"""

import pytest
import json
import logging
from pathlib import Path
from datetime import datetime
import tempfile
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.metrics import MetricsCollector, IngestionMetrics, QueryMetrics
from src.metrics_dashboard import MetricsAnalyzer
from src.metrics_charts import MetricsCharts
from src.metrics_alerts import MetricsAlerts
from src.progress_callbacks import NullProgressCallback, LoggingProgressCallback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture
def metrics_system(tmp_path):
    """Create complete metrics system for testing"""
    metrics_file = tmp_path / "metrics.jsonl"
    return {
        "metrics_file": metrics_file,
        "collector": MetricsCollector(metrics_file),
        "tmp_path": tmp_path
    }


# ===== E2E TEST 1: Fresh Start to Full System =====
def test_fresh_start_to_full_system(metrics_system):
    """E2E: From fresh system to fully operational with metrics"""
    logger.info("\n" + "="*70)
    logger.info("[E2E TEST 1] Fresh Start to Full System")
    logger.info("="*70)

    collector = metrics_system["collector"]
    metrics_file = metrics_system["metrics_file"]

    # STEP 1: Ingest documents
    logger.info("[STEP 1] Ingesting 10 documents...")
    for i in range(10):
        metric = IngestionMetrics(
            file_name=f"document_{i:02d}.pdf",
            file_size_bytes=1024000 * (i + 1),
            chunks_created=10 * (i + 1),
            embeddings_generated=10 * (i + 1),
            start_time=time.time() - 10,
            end_time=time.time(),
            duration_seconds=5.0,
            success=True if i < 9 else False,  # Last one fails
            error=None if i < 9 else "Embedding API error"
        )
        collector.record_ingestion(metric)
    logger.info(f"[STEP 1] Ingested 10 documents, 9 succeeded, 1 failed")

    # STEP 2: Execute queries
    logger.info("[STEP 2] Executing 20 queries...")
    for i in range(20):
        metric = QueryMetrics(
            query_text=f"What is document_{i % 10:02d} about?",
            documents_searched=100,
            documents_found=5,
            search_latency_ms=50.0 + (i * 5),
            llm_latency_ms=4000.0 + (i * 100),
            cache_hit=i % 2 == 0
        )
        collector.record_query(metric)
    logger.info(f"[STEP 2] Executed 20 queries, {20//2} cache hits")

    # STEP 3: Analyze metrics
    logger.info("[STEP 3] Analyzing metrics...")
    analyzer = MetricsAnalyzer(metrics_file)
    ing_summary = analyzer.ingestion_summary()
    qry_summary = analyzer.query_summary()

    assert ing_summary['total_files'] == 10
    assert ing_summary['successful'] == 9
    assert qry_summary['total_queries'] == 20
    logger.info(f"[STEP 3] Analysis: {ing_summary['total_files']} files, {qry_summary['total_queries']} queries")

    # STEP 4: Generate charts
    logger.info("[STEP 4] Generating charts...")
    charts = MetricsCharts(metrics_file)
    charts.chart_ingestion_rate()
    charts.chart_query_latency()
    charts.chart_success_rate()
    logger.info("[STEP 4] Charts generated successfully")

    # STEP 5: Check alerts
    logger.info("[STEP 5] Checking system alerts...")
    alerts = MetricsAlerts(metrics_file)
    active_alerts = alerts.check_all()
    logger.info(f"[STEP 5] System health check: {len(active_alerts)} alerts detected")

    logger.info("[E2E TEST 1 PASS] System fully operational")


# ===== E2E TEST 2: Error Recovery and Retry =====
def test_error_recovery_and_retry(metrics_system):
    """E2E: Handle ingestion errors and recovery"""
    logger.info("\n" + "="*70)
    logger.info("[E2E TEST 2] Error Recovery and Retry")
    logger.info("="*70)

    collector = metrics_system["collector"]
    metrics_file = metrics_system["metrics_file"]

    # First attempt: failures
    logger.info("[ATTEMPT 1] First ingestion attempt with errors...")
    for i in range(5):
        success = i % 2 == 0  # Alternate success/failure
        metric = IngestionMetrics(
            file_name=f"doc_{i}.pdf",
            file_size_bytes=1024000,
            chunks_created=0 if not success else 10,
            embeddings_generated=0 if not success else 10,
            start_time=time.time() - 5,
            end_time=time.time(),
            duration_seconds=5.0,
            success=success,
            error=None if success else "Rate limited by API"
        )
        collector.record_ingestion(metric)

    summary1 = collector.get_summary()
    logger.info(f"[ATTEMPT 1] Success rate: {summary1['success_rate']*100:.1f}%")

    # Second attempt: recovery
    logger.info("[ATTEMPT 2] Retry after rate limit recovery...")
    for i in range(2, 5):  # Retry only failed ones
        metric = IngestionMetrics(
            file_name=f"doc_{i}.pdf",
            file_size_bytes=1024000,
            chunks_created=10,
            embeddings_generated=10,
            start_time=time.time() - 3,
            end_time=time.time(),
            duration_seconds=3.0,
            success=True,
            error=None
        )
        collector.record_ingestion(metric)

    summary2 = collector.get_summary()
    logger.info(f"[ATTEMPT 2] Final success rate: {summary2['success_rate']*100:.1f}%")
    assert summary2['successful_files'] > summary1['successful_files']

    logger.info("[E2E TEST 2 PASS] Error recovery works correctly")


# ===== E2E TEST 3: Long-Running Ingestion with Progress =====
def test_long_running_ingestion_with_progress(metrics_system):
    """E2E: Long ingestion with progress tracking"""
    logger.info("\n" + "="*70)
    logger.info("[E2E TEST 3] Long-Running Ingestion with Progress")
    logger.info("="*70)

    collector = metrics_system["collector"]

    # Track progress through multiple files
    progress_callback = LoggingProgressCallback()
    total_chunks = 0
    start_time = time.time()

    logger.info("[INGESTION] Processing 50 documents...")
    for file_num in range(50):
        # Simulate file processing
        progress_callback.on_file_start(f"doc_{file_num:03d}.pdf", file_num + 1, 50)

        chunks = 10 + (file_num % 5)  # Variable chunk counts
        for chunk_num in range(chunks):
            progress_callback.on_chunk_extracted(chunk_num + 1, chunks, f"doc_{file_num:03d}.pdf")
            total_chunks += 1

        progress_callback.on_embedding_start(chunks, f"doc_{file_num:03d}.pdf")

        metric = IngestionMetrics(
            file_name=f"doc_{file_num:03d}.pdf",
            file_size_bytes=1024000 + (file_num * 1000),
            chunks_created=chunks,
            embeddings_generated=chunks,
            start_time=time.time() - 2,
            end_time=time.time(),
            duration_seconds=2.0,
            success=True
        )
        collector.record_ingestion(metric)

        progress_callback.on_file_complete(
            f"doc_{file_num:03d}.pdf",
            chunks,
            True,
            None
        )

        if (file_num + 1) % 10 == 0:
            elapsed = time.time() - start_time
            rate = total_chunks / elapsed if elapsed > 0 else 0
            logger.info(f"  Progress: {file_num+1}/50 files, {total_chunks} chunks, {rate:.1f} chunks/s")

    elapsed = time.time() - start_time
    logger.info(f"[INGESTION COMPLETE] {total_chunks} chunks in {elapsed:.1f}s ({total_chunks/elapsed:.1f} chunks/s)")

    summary = collector.get_summary()
    assert summary['total_files'] == 50
    assert summary['total_chunks'] > 0
    logger.info("[E2E TEST 3 PASS] Long-running ingestion works")


# ===== E2E TEST 4: Query Latency Patterns =====
def test_query_latency_patterns(metrics_system):
    """E2E: Analyze query latency patterns"""
    logger.info("\n" + "="*70)
    logger.info("[E2E TEST 4] Query Latency Patterns")
    logger.info("="*70)

    collector = metrics_system["collector"]
    metrics_file = metrics_system["metrics_file"]

    # Simulate various query patterns
    logger.info("[QUERIES] Simulating 100 queries with varying latencies...")

    # Normal queries
    for i in range(80):
        metric = QueryMetrics(
            query_text=f"normal query {i}",
            documents_searched=100,
            documents_found=5,
            search_latency_ms=100.0,
            llm_latency_ms=4000.0,
            cache_hit=i % 3 == 0
        )
        collector.record_query(metric)

    # Slow queries (outliers)
    for i in range(15):
        metric = QueryMetrics(
            query_text=f"slow query {i}",
            documents_searched=100,
            documents_found=10,
            search_latency_ms=500.0,
            llm_latency_ms=15000.0,
            cache_hit=False
        )
        collector.record_query(metric)

    # Fast queries (cached)
    for i in range(5):
        metric = QueryMetrics(
            query_text=f"cached query {i}",
            documents_searched=100,
            documents_found=3,
            search_latency_ms=50.0,
            llm_latency_ms=1000.0,
            cache_hit=True
        )
        collector.record_query(metric)

    # Analyze patterns
    analyzer = MetricsAnalyzer(metrics_file)
    qry_summary = analyzer.query_summary()

    logger.info(f"[ANALYSIS] Query Statistics:")
    logger.info(f"  Total Queries: {qry_summary['total_queries']}")
    logger.info(f"  Average Latency: {qry_summary['avg_latency_ms']:.0f}ms")
    logger.info(f"  P95 Latency: {qry_summary['p95_latency_ms']:.0f}ms")
    logger.info(f"  Cache Hit Rate: {qry_summary['cache_hit_rate']*100:.1f}%")

    assert qry_summary['total_queries'] == 100
    assert qry_summary['cache_hit_rate'] > 0
    logger.info("[E2E TEST 4 PASS] Query latency analysis works")


# ===== E2E TEST 5: Complete Dashboard Flow =====
def test_complete_dashboard_flow(metrics_system):
    """E2E: Metrics collection to dashboard display"""
    logger.info("\n" + "="*70)
    logger.info("[E2E TEST 5] Complete Dashboard Flow")
    logger.info("="*70)

    collector = metrics_system["collector"]
    metrics_file = metrics_system["metrics_file"]

    # Collect representative data
    logger.info("[PHASE 1] Collecting metrics...")
    for i in range(20):
        ing = IngestionMetrics(
            file_name=f"doc_{i}.pdf",
            file_size_bytes=1024000,
            chunks_created=15,
            embeddings_generated=15,
            start_time=time.time() - 10,
            end_time=time.time(),
            duration_seconds=5.0,
            success=True
        )
        collector.record_ingestion(ing)

        for j in range(5):
            qry = QueryMetrics(
                query_text=f"query about doc_{i}",
                documents_searched=20,
                documents_found=3,
                search_latency_ms=80.0,
                llm_latency_ms=4500.0,
                cache_hit=j % 2 == 0
            )
            collector.record_query(qry)

    logger.info("[PHASE 1] Metrics collected")

    # Analyze
    logger.info("[PHASE 2] Analyzing for dashboard...")
    analyzer = MetricsAnalyzer(metrics_file)
    ing_sum = analyzer.ingestion_summary()
    qry_sum = analyzer.query_summary()
    logger.info(f"[PHASE 2] Ingestion: {ing_sum['total_files']} files")
    logger.info(f"[PHASE 2] Queries: {qry_sum['total_queries']} queries")

    # Generate visualizations
    logger.info("[PHASE 3] Generating visualizations...")
    charts = MetricsCharts(metrics_file)
    chart_ing = charts.chart_ingestion_rate()
    chart_qry = charts.chart_query_latency()
    chart_cache = charts.chart_cache_hit_rate()
    logger.info("[PHASE 3] Charts generated")

    # Check alerts
    logger.info("[PHASE 4] System health check...")
    alerts = MetricsAlerts(metrics_file)
    active_alerts = alerts.check_all()
    alert_summary = alerts.get_alert_summary()
    logger.info(f"[PHASE 4] Alerts: {alert_summary['total_alerts']} total")

    # Dashboard ready
    logger.info("[PHASE 5] Dashboard ready for display")
    dashboard_data = {
        "ingestion": ing_sum,
        "queries": qry_sum,
        "alerts": alert_summary,
        "charts": ["ingestion_rate", "query_latency", "cache_hit_rate"]
    }

    assert dashboard_data['ingestion']['total_files'] == 20
    assert dashboard_data['queries']['total_queries'] == 100
    logger.info("[E2E TEST 5 PASS] Dashboard flow complete")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
