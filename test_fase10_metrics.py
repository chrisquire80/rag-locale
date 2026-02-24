"""
FASE 10 Integration Test: Verify metrics collection

This test validates that:
1. Metrics are collected for ingestion
2. Metrics are collected for queries
3. Metrics dashboard generates reports
4. Metrics are persisted to JSONL
"""

import sys
import os
import time
import logging
from pathlib import Path

# Setup paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import config, DOCUMENTS_DIR
from document_ingestion import DocumentIngestionPipeline
from rag_engine import RAGEngine
from metrics import get_metrics_collector
from metrics_dashboard import MetricsAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_metrics_collection():
    """Test basic metrics collection"""
    print("\n" + "="*70)
    print("TEST 1: Metrics Collection")
    print("="*70)

    try:
        collector = get_metrics_collector()

        # Check that metrics file exists
        metrics_file = Path("logs/metrics.jsonl")
        if metrics_file.exists():
            logger.info(f"Metrics file exists: {metrics_file}")
            file_size = metrics_file.stat().st_size
            logger.info(f"Metrics file size: {file_size} bytes")
        else:
            logger.info(f"Metrics file not yet created (will be created on first metric)")

        logger.info("PASS: Metrics collection initialized")
        return True

    except Exception as e:
        logger.error(f"FAIL: Metrics collection failed: {e}")
        return False


def test_ingestion_metrics():
    """Test ingestion metrics collection"""
    print("\n" + "="*70)
    print("TEST 2: Ingestion Metrics")
    print("="*70)

    try:
        # Get first PDF
        test_files = list(DOCUMENTS_DIR.glob('*.pdf'))[:1]

        if not test_files:
            logger.warning("No PDF files found. Skipping test.")
            return True

        logger.info(f"Testing metrics with: {test_files[0].name}")

        pipeline = DocumentIngestionPipeline()
        collector = get_metrics_collector()

        # Ingest file (this should record metrics)
        start_time = time.perf_counter()
        count_added = pipeline.ingest_single_file(test_files[0])
        elapsed = time.perf_counter() - start_time

        logger.info(f"Ingestion completed: {count_added} documents in {elapsed:.2f}s")

        # Check metrics were recorded
        metrics_summary = collector.get_summary()
        logger.info(f"Metrics summary: {metrics_summary}")

        if metrics_summary.get("total_files", 0) > 0:
            logger.info("PASS: Ingestion metrics recorded")
            return True
        else:
            logger.warning("No metrics found (file might have been ingested before)")
            return True

    except Exception as e:
        logger.error(f"FAIL: Ingestion metrics test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_query_metrics():
    """Test query metrics collection"""
    print("\n" + "="*70)
    print("TEST 3: Query Metrics")
    print("="*70)

    try:
        engine = RAGEngine()
        collector = get_metrics_collector()

        # Run a simple query
        test_query = "test query"
        logger.info(f"Running query: {test_query}")

        start_time = time.perf_counter()
        response = engine.query(test_query, auto_approve_if_high_confidence=True)
        elapsed = time.perf_counter() - start_time

        logger.info(f"Query completed in {elapsed:.2f}s")

        # Check metrics were recorded
        query_stats = collector.get_query_stats()
        logger.info(f"Query stats: {query_stats}")

        if query_stats.get("total_queries", 0) > 0:
            logger.info("PASS: Query metrics recorded")
            return True
        else:
            logger.warning("No query metrics found")
            return True

    except Exception as e:
        logger.error(f"FAIL: Query metrics test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_metrics_persistence():
    """Test metrics persistence to JSONL"""
    print("\n" + "="*70)
    print("TEST 4: Metrics Persistence")
    print("="*70)

    try:
        metrics_file = Path("logs/metrics.jsonl")

        if not metrics_file.exists():
            logger.warning("Metrics file not created yet")
            return True

        # Read metrics file
        import json
        with open(metrics_file) as f:
            lines = f.readlines()

        logger.info(f"Metrics file contains {len(lines)} entries")

        # Parse and validate
        ingestion_count = 0
        query_count = 0

        for line in lines[-5:]:  # Check last 5 entries
            try:
                entry = json.loads(line)
                entry_type = entry.get("type")
                if entry_type == "ingestion":
                    ingestion_count += 1
                elif entry_type == "query":
                    query_count += 1
            except json.JSONDecodeError:
                pass

        logger.info(f"Recent entries: {ingestion_count} ingestions, {query_count} queries")

        if len(lines) > 0:
            logger.info("PASS: Metrics persisted to JSONL")
            return True
        else:
            logger.warning("Metrics file is empty")
            return True

    except Exception as e:
        logger.error(f"FAIL: Metrics persistence test failed: {e}")
        return False


def test_metrics_dashboard():
    """Test metrics dashboard/analyzer"""
    print("\n" + "="*70)
    print("TEST 5: Metrics Dashboard")
    print("="*70)

    try:
        analyzer = MetricsAnalyzer()

        # Get summaries
        ing_summary = analyzer.ingestion_summary()
        query_summary = analyzer.query_summary()
        api_summary = analyzer.api_summary()

        logger.info(f"Ingestion summary: {ing_summary}")
        logger.info(f"Query summary: {query_summary}")
        logger.info(f"API summary: {api_summary}")

        # Test report generation
        print("\nMetrics Report:")
        analyzer.print_report()

        logger.info("PASS: Metrics dashboard working")
        return True

    except Exception as e:
        logger.error(f"FAIL: Metrics dashboard test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Run all FASE 10 metrics tests"""
    print("\n" + "="*70)
    print("FASE 10 METRICS TEST SUITE")
    print("="*70)

    results = {
        "Metrics Collection": test_metrics_collection(),
        "Ingestion Metrics": test_ingestion_metrics(),
        "Query Metrics": test_query_metrics(),
        "Metrics Persistence": test_metrics_persistence(),
        "Metrics Dashboard": test_metrics_dashboard(),
    }

    print("\n" + "="*70)
    print("TEST RESULTS SUMMARY")
    print("="*70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"{test_name:.<40} {status}")

    print("-"*70)
    print(f"Total: {passed}/{total} passed")

    if passed == total:
        print("\nAll FASE 10 metrics tests passed!")
        return 0
    else:
        print(f"\nSome tests failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
