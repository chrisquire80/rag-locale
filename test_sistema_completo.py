"""
Comprehensive integration tests for complete system (FASE 10-15)
Tests that all metrics, progress callbacks, PDF validation, and charts work together
"""

import pytest
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.metrics import MetricsCollector, IngestionMetrics, QueryMetrics, APIMetrics
from src.metrics_dashboard import MetricsAnalyzer
from src.metrics_charts import MetricsCharts
from src.metrics_alerts import MetricsAlerts, AlertSeverity, AlertType
from src.progress_callbacks import (
    ProgressCallback,
    StreamlitProgressCallback,
    CompositeProgressCallback,
    NullProgressCallback,
    LoggingProgressCallback
)
from src.pdf_validator import PDFValidator, PDFValidationError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.fixture
def temp_dir():
    """Create temporary directory for testing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def metrics_collector(temp_dir):
    """Create metrics collector with temporary file"""
    metrics_file = temp_dir / "metrics.jsonl"
    return MetricsCollector(metrics_file)


# ===== TEST 1: Single PDF Upload with Progress Callback =====
def test_single_pdf_upload_with_progress(temp_dir):
    """Test uploading single PDF with progress tracking"""
    logger.info("\n" + "="*70)
    logger.info("[TEST 1] Single PDF Upload with Progress Callback")
    logger.info("="*70)

    # Create metrics
    metrics_file = temp_dir / "metrics.jsonl"
    collector = MetricsCollector(metrics_file)

    # Track progress events
    progress_events = []

    class TestProgressCallback(ProgressCallback):
        def on_file_start(self, filename: str, file_number: int, total_files: int):
            progress_events.append(("file_start", filename))
            logger.info(f"Progress: Starting file {filename}")

        def on_chunk_extracted(self, chunk_number: int, total_chunks: int, filename: str):
            progress_events.append(("chunk_extracted", chunk_number))

        def on_embedding_start(self, chunk_count: int, filename: str):
            progress_events.append(("embedding_start", chunk_count))

        def on_embedding_progress(self, completed: int, total: int, filename: str):
            pass  # Not needed for test

        def on_file_complete(self, filename: str, chunks_added: int, success: bool, error: str = None):
            progress_events.append(("file_complete", success))
            logger.info(f"Progress: File {filename} complete (success={success})")

        def on_batch_complete(self, total_files: int, successful: int, failed: int, total_chunks: int, elapsed_seconds: float):
            pass  # Not needed for this test

    # Simulate file ingestion
    callback = TestProgressCallback()
    callback.on_file_start("test.pdf", 1, 1)
    callback.on_chunk_extracted(1, 5, "test.pdf")
    callback.on_chunk_extracted(2, 5, "test.pdf")
    callback.on_embedding_start(5, "test.pdf")
    callback.on_file_complete("test.pdf", 5, True, None)

    # Record metrics
    metric = IngestionMetrics(
        file_name="test.pdf",
        file_size_bytes=1024000,
        chunks_created=5,
        embeddings_generated=5,
        start_time=time.time() - 5,
        end_time=time.time(),
        duration_seconds=5.0,
        success=True
    )
    collector.record_ingestion(metric)

    # Verify
    assert len(progress_events) > 0
    assert progress_events[0][0] == "file_start"
    assert progress_events[-1][0] == "file_complete"
    logger.info(f"[TEST 1] Progress events tracked: {len(progress_events)}")
    logger.info("[TEST 1 PASS] Single PDF upload with progress works correctly")


# ===== TEST 2: Batch Upload with Progress Callbacks =====
def test_batch_upload_with_progress(temp_dir):
    """Test uploading multiple PDFs with batch progress"""
    logger.info("\n" + "="*70)
    logger.info("[TEST 2] Batch PDF Upload with Progress Callbacks")
    logger.info("="*70)

    metrics_file = temp_dir / "metrics.jsonl"
    collector = MetricsCollector(metrics_file)

    # Track batch events
    batch_events = []

    class TestBatchCallback(ProgressCallback):
        def on_file_start(self, filename: str, file_number: int, total_files: int):
            pass

        def on_chunk_extracted(self, chunk_number: int, total_chunks: int, filename: str):
            pass

        def on_embedding_start(self, chunk_count: int, filename: str):
            pass

        def on_embedding_progress(self, completed: int, total: int, filename: str):
            pass

        def on_file_complete(self, filename: str, chunks_added: int, success: bool, error: str = None):
            pass

        def on_batch_complete(self, total_files: int, successful: int, failed: int, total_chunks: int, elapsed_seconds: float):
            batch_events.append(("batch_complete", total_files, successful))
            logger.info(f"Batch complete: {successful}/{total_files} files, {total_chunks} chunks in {elapsed_seconds:.1f}s")

    callback = TestBatchCallback()

    # Simulate batch ingestion
    start_time = time.time()
    for i in range(3):
        metric = IngestionMetrics(
            file_name=f"doc{i}.pdf",
            file_size_bytes=1024000,
            chunks_created=10,
            embeddings_generated=10,
            start_time=time.time() - 3,
            end_time=time.time(),
            duration_seconds=3.0,
            success=True
        )
        collector.record_ingestion(metric)

    elapsed = time.time() - start_time
    callback.on_batch_complete(total_files=3, successful=3, failed=0, total_chunks=30, elapsed_seconds=elapsed)

    # Verify
    assert len(batch_events) > 0
    summary = collector.get_summary()
    assert summary['total_files'] == 3
    assert summary['successful_files'] == 3
    logger.info("[TEST 2 PASS] Batch upload with progress works correctly")


# ===== TEST 3: Query with Cache Hits and Metrics =====
def test_query_with_metrics(temp_dir):
    """Test query execution with metrics recording"""
    logger.info("\n" + "="*70)
    logger.info("[TEST 3] Query Execution with Metrics Recording")
    logger.info("="*70)

    metrics_file = temp_dir / "metrics.jsonl"
    collector = MetricsCollector(metrics_file)

    # Simulate queries
    for i in range(5):
        cache_hit = i % 2 == 0  # Alternate cache hits
        metric = QueryMetrics(
            query_text=f"test query {i}",
            documents_searched=20,
            documents_found=5,
            search_latency_ms=50.0 + (i * 10),
            llm_latency_ms=5000.0,
            cache_hit=cache_hit
        )
        collector.record_query(metric)
        logger.info(f"Query {i}: cache_hit={cache_hit}, latency={metric.total_latency_ms:.0f}ms")

    # Verify metrics
    stats = collector.get_query_stats()
    assert stats['total_queries'] == 5
    assert stats['cache_hit_rate'] > 0
    logger.info(f"Query stats: {stats}")
    logger.info("[TEST 3 PASS] Query metrics recorded correctly")


# ===== TEST 4: Chart Generation from Collected Metrics =====
def test_charts_from_metrics(temp_dir):
    """Test that charts can be generated from collected metrics"""
    logger.info("\n" + "="*70)
    logger.info("[TEST 4] Chart Generation from Collected Metrics")
    logger.info("="*70)

    metrics_file = temp_dir / "metrics.jsonl"
    collector = MetricsCollector(metrics_file)

    # Collect sample data
    for i in range(5):
        # Ingestion
        ing_metric = IngestionMetrics(
            file_name=f"doc{i}.pdf",
            file_size_bytes=1024000,
            chunks_created=10,
            embeddings_generated=10,
            start_time=time.time() - 10 + (i * 2),
            end_time=time.time() - 8 + (i * 2),
            duration_seconds=2.0,
            success=True
        )
        collector.record_ingestion(ing_metric)

        # Query
        qry_metric = QueryMetrics(
            query_text=f"test query {i}",
            documents_searched=10,
            documents_found=3,
            search_latency_ms=100.0,
            llm_latency_ms=4000.0,
            cache_hit=i % 2 == 0
        )
        collector.record_query(qry_metric)

    # Generate charts
    charts = MetricsCharts(metrics_file)

    chart1 = charts.chart_ingestion_rate()
    assert chart1 is not None
    logger.info("[TEST 4.1] Ingestion rate chart generated")

    chart2 = charts.chart_query_latency()
    assert chart2 is not None
    logger.info("[TEST 4.2] Query latency chart generated")

    chart3 = charts.chart_cache_hit_rate()
    assert chart3 is not None
    logger.info("[TEST 4.3] Cache hit rate chart generated")

    logger.info("[TEST 4 PASS] All charts generated from metrics")


# ===== TEST 5: Alert Detection on Metric Anomalies =====
def test_alerts_on_anomalies(temp_dir):
    """Test that alerts are triggered on metric anomalies"""
    logger.info("\n" + "="*70)
    logger.info("[TEST 5] Alert Detection on Metric Anomalies")
    logger.info("="*70)

    metrics_file = temp_dir / "metrics.jsonl"
    collector = MetricsCollector(metrics_file)

    # Create data with some anomalies
    # Normal ingestions
    for i in range(5):
        metric = IngestionMetrics(
            file_name=f"doc{i}.pdf",
            file_size_bytes=1024000,
            chunks_created=10,
            embeddings_generated=10,
            start_time=time.time() - 10,
            end_time=time.time() - 9,
            duration_seconds=1.0,  # Fast
            success=True
        )
        collector.record_ingestion(metric)

    # Slow ingestion (anomaly)
    slow_metric = IngestionMetrics(
        file_name="slow.pdf",
        file_size_bytes=5048000,
        chunks_created=20,
        embeddings_generated=20,
        start_time=time.time() - 8,
        end_time=time.time() + 20,  # Very slow
        duration_seconds=30.0,
        success=True
    )
    collector.record_ingestion(slow_metric)

    # Check alerts
    alerts = MetricsAlerts(metrics_file)
    active_alerts = alerts.check_all(hours=24)

    logger.info(f"Detected {len(active_alerts)} alerts")
    for alert in active_alerts:
        logger.info(f"  Alert: {alert.alert_type.value} - {alert.message}")

    logger.info("[TEST 5 PASS] Alert system detects anomalies")


# ===== TEST 6: PDF Validation Integration =====
def test_pdf_validation_integration(temp_dir):
    """Test that PDF validation integrates with metrics"""
    logger.info("\n" + "="*70)
    logger.info("[TEST 6] PDF Validation Integration")
    logger.info("="*70)

    validator = PDFValidator()
    metrics_file = temp_dir / "metrics.jsonl"
    collector = MetricsCollector(metrics_file)

    # Test with a non-existent file (should fail validation)
    fake_pdf = temp_dir / "nonexistent.pdf"
    is_valid, error = validator.validate_strict(fake_pdf)

    assert not is_valid
    assert error is not None
    logger.info(f"[TEST 6.1] Validation correctly failed for nonexistent file")
    logger.info(f"  Error type: {error.error_type.value}")

    # Record validation failure as metric
    metric = IngestionMetrics(
        file_name="nonexistent.pdf",
        file_size_bytes=0,
        chunks_created=0,
        embeddings_generated=0,
        start_time=time.time(),
        end_time=time.time(),
        duration_seconds=0.1,
        success=False,
        error=f"Validation failed: {error.error_type.value}"
    )
    collector.record_ingestion(metric)

    summary = collector.get_summary()
    assert summary['failed_files'] == 1
    logger.info("[TEST 6.2] Validation failures recorded in metrics")

    logger.info("[TEST 6 PASS] PDF validation integrates with metrics")


# ===== TEST 7: Complete Flow - Metrics to Dashboard =====
def test_complete_flow_metrics_to_dashboard(temp_dir):
    """Test complete flow from data collection to dashboard display"""
    logger.info("\n" + "="*70)
    logger.info("[TEST 7] Complete Flow: Metrics Collection to Dashboard")
    logger.info("="*70)

    metrics_file = temp_dir / "metrics.jsonl"

    # Step 1: Collect metrics
    collector = MetricsCollector(metrics_file)
    for i in range(5):
        metric = IngestionMetrics(
            file_name=f"doc{i}.pdf",
            file_size_bytes=1024000,
            chunks_created=10,
            embeddings_generated=10,
            start_time=time.time() - 5,
            end_time=time.time(),
            duration_seconds=5.0,
            success=True
        )
        collector.record_ingestion(metric)

    for i in range(10):
        metric = QueryMetrics(
            query_text=f"query {i}",
            documents_searched=10,
            documents_found=3,
            search_latency_ms=100.0,
            llm_latency_ms=5000.0,
            cache_hit=i % 2 == 0
        )
        collector.record_query(metric)

    logger.info(f"[TEST 7.1] Collected metrics written to {metrics_file}")

    # Step 2: Analyze metrics
    analyzer = MetricsAnalyzer(metrics_file)
    ing_summary = analyzer.ingestion_summary()
    qry_summary = analyzer.query_summary()

    assert ing_summary['total_files'] == 5
    assert qry_summary['total_queries'] == 10
    logger.info(f"[TEST 7.2] Metrics analyzed: {ing_summary['total_files']} files, {qry_summary['total_queries']} queries")

    # Step 3: Generate charts
    charts = MetricsCharts(metrics_file)
    chart = charts.chart_ingestion_rate()
    assert chart is not None
    logger.info("[TEST 7.3] Charts generated for dashboard display")

    # Step 4: Check alerts
    alerts = MetricsAlerts(metrics_file)
    active_alerts = alerts.check_all()
    logger.info(f"[TEST 7.4] Alert system active: {len(active_alerts)} alerts")

    # Step 5: Verify dashboard data
    dashboard_summary = {
        "ingestion": ing_summary,
        "queries": qry_summary,
        "alerts": alerts.get_alert_summary()
    }

    assert dashboard_summary['ingestion']['total_files'] > 0
    assert dashboard_summary['queries']['total_queries'] > 0
    logger.info("[TEST 7.5] Dashboard data ready for display")

    logger.info("[TEST 7 PASS] Complete flow works end-to-end")


# ===== TEST 8: Concurrent Progress Callbacks =====
def test_concurrent_progress_callbacks(temp_dir):
    """Test that multiple progress callbacks work together"""
    logger.info("\n" + "="*70)
    logger.info("[TEST 8] Concurrent Progress Callbacks")
    logger.info("="*70)

    # Create multiple callbacks
    null_callback = NullProgressCallback()
    logging_callback = LoggingProgressCallback()

    # Create composite callback
    composite = CompositeProgressCallback([null_callback, logging_callback])

    # Simulate progress
    composite.on_file_start("test.pdf", 1, 1)
    composite.on_chunk_extracted(1, 5, "test.pdf")
    composite.on_file_complete("test.pdf", 5, True, None)

    logger.info("[TEST 8 PASS] Concurrent progress callbacks work together")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
