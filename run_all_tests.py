"""
Comprehensive Test Suite - Esegui tutti i test di ottimizzazione in sequenza
"""

import logging
import sys
import subprocess
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test configuration
TESTS = [
    {
        "name": "Performance Profiler",
        "file": "src/performance_profiler.py",
        "description": "Test timing instrumentation e statistics"
    },
    {
        "name": "Hardware Optimization",
        "file": "src/hardware_optimization.py",
        "description": "Test HP ProBook detection e configuration"
    },
    {
        "name": "HNSW Vector Indexing",
        "file": "src/hnsw_indexing.py",
        "description": "Test approximate nearest neighbor search"
    },
    {
        "name": "Quantization",
        "file": "src/quantization.py",
        "description": "Test INT8 embedding quantization"
    },
    {
        "name": "Multi-threaded PDF Parser",
        "file": "src/multithread_pdf_parser.py",
        "description": "Test parallel PDF parsing"
    },
    {
        "name": "Async RAG Engine",
        "file": "src/async_rag_engine.py",
        "description": "Test async query processing"
    },
    {
        "name": "Scalability Testing",
        "file": "test_fase_scalability.py",
        "description": "Test 100+ document scalability"
    }
]


def run_test(test_config: dict) -> bool:
    """Esegui singolo test e ritorna risultato"""
    test_file = test_config["file"]
    test_name = test_config["name"]
    description = test_config["description"]

    logger.info(f"\n{'='*80}")
    logger.info(f"🧪 TEST: {test_name}")
    logger.info(f"   Descrizione: {description}")
    logger.info(f"   File: {test_file}")
    logger.info(f"{'='*80}")

    try:
        if test_file.endswith(".py"):
            # Esegui script Python
            result = subprocess.run(
                [sys.executable, test_file],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode == 0:
                logger.info(f"✅ PASSED: {test_name}")
                if result.stdout:
                    logger.info(result.stdout[:500])  # Print first 500 chars
                return True
            else:
                logger.error(f"❌ FAILED: {test_name}")
                logger.error(f"Error: {result.stderr[:500]}")
                return False

    except subprocess.TimeoutExpired:
        logger.error(f"❌ TIMEOUT: {test_name} (exceeded 120s)")
        return False
    except Exception as e:
        logger.error(f"❌ ERROR: {test_name} - {e}")
        return False


def generate_test_report(results: dict) -> str:
    """Genera report finale"""
    report = f"\n{'='*80}\n"
    report += "TEST SUMMARY REPORT\n"
    report += f"{'='*80}\n\n"

    report += f"Execution Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"

    passed = sum(1 for r in results.values() if r)
    failed = sum(1 for r in results.values() if not r)
    total = len(results)

    report += f"Results:\n"
    report += f"  ✅ Passed: {passed}/{total}\n"
    report += f"  ❌ Failed: {failed}/{total}\n"
    report += f"  Success Rate: {(passed/total*100):.1f}%\n\n"

    report += "Details:\n"
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        report += f"  {status}: {test_name}\n"

    report += "\n" + "="*80 + "\n"

    if failed == 0:
        report += "🎉 ALL TESTS PASSED!\n"
    else:
        report += f"⚠️  {failed} test(s) failed. Review logs above.\n"

    report += "="*80 + "\n"

    return report


def main():
    """Main test runner"""
    logger.info("\n" + "="*80)
    logger.info("🚀 COMPREHENSIVE TEST SUITE - Performance Optimization")
    logger.info("="*80)

    results = {}
    test_count = len(TESTS)

    for i, test in enumerate(TESTS, 1):
        logger.info(f"\n[{i}/{test_count}] Running {test['name']}...")
        passed = run_test(test)
        results[test["name"]] = passed

    # Generate final report
    report = generate_test_report(results)
    logger.info(report)

    # Save report
    report_path = Path(__file__).parent / "TEST_RESULTS.txt"
    try:
        report_path.write_text(report)
        logger.info(f"\n📄 Report saved to: {report_path}")
    except Exception as e:
        logger.error(f"Failed to save report: {e}")

    # Exit with appropriate code
    failed = sum(1 for r in results.values() if not r)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
