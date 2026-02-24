"""
FASE 13+14 Integration Test: Progress Callbacks + PDF Validator Integration

This test validates that:
1. Progress callbacks are properly integrated into ingest_single_file()
2. Progress callbacks are properly integrated into ingest_from_directory()
3. PDF validation works before processing
4. Corrupted PDFs are properly detected and blacklisted
5. Progress updates are reported correctly
"""

import sys
import os
import logging
import tempfile
from pathlib import Path
import time

# Setup paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import DOCUMENTS_DIR
from document_ingestion import DocumentIngestionPipeline
from progress_callbacks import (
    LoggingProgressCallback,
    PrintProgressCallback,
    NullProgressCallback
)
from pdf_validator import get_pdf_validator, PDFErrorType

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestProgressCallback:
    """Simple test callback to track events"""

    def __init__(self):
        self.events = []

    def on_file_start(self, filename: str, file_number: int, total_files: int):
        self.events.append(('file_start', filename, file_number, total_files))

    def on_chunk_extracted(self, chunk_number: int, total_chunks: int, filename: str):
        self.events.append(('chunk_extracted', chunk_number, total_chunks, filename))

    def on_embedding_start(self, chunk_count: int, filename: str):
        self.events.append(('embedding_start', chunk_count, filename))

    def on_embedding_progress(self, completed: int, total: int, filename: str):
        self.events.append(('embedding_progress', completed, total, filename))

    def on_file_complete(self, filename: str, chunks_added: int, success: bool, error=None):
        self.events.append(('file_complete', filename, chunks_added, success, error))

    def on_batch_complete(self, total_files: int, successful: int, failed: int, total_chunks: int, elapsed_seconds: float):
        self.events.append(('batch_complete', total_files, successful, failed, total_chunks, elapsed_seconds))


def test_pdf_validation_integration():
    """Test PDF validation before ingestion"""
    print("\n" + "="*70)
    print("TEST 1: PDF Validation Integration")
    print("="*70)

    try:
        validator = get_pdf_validator()

        # Test with corrupted PDF
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create corrupted PDF
            bad_pdf = Path(tmpdir) / "corrupted.pdf"
            bad_pdf.write_bytes(b"NOT A PDF FILE" + b"X" * 50)

            is_valid, error = validator.validate_strict(bad_pdf)

            if not is_valid:
                logger.info(f"✓ Corrupted PDF detected: {error.error_type.value}")
                logger.info(f"  Message: {error.message}")

                if validator.should_blacklist(error):
                    logger.info(f"✓ Error classified for blacklisting")
                    return True
                else:
                    logger.error(f"✗ Error should be blacklisted but isn't")
                    return False
            else:
                logger.error(f"✗ Corrupted PDF not detected")
                return False

    except Exception as e:
        logger.error(f"FAIL: Test failed with exception: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_progress_callback_single_file():
    """Test progress callbacks on single file ingestion"""
    print("\n" + "="*70)
    print("TEST 2: Progress Callback - Single File")
    print("="*70)

    try:
        pipeline = DocumentIngestionPipeline()
        test_callback = TestProgressCallback()

        # Create test file
        test_file = DOCUMENTS_DIR / "test_callback_single.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("""
TEST DOCUMENT FOR CALLBACK INTEGRATION

Section 1: Introduction
This is a test document for progress callback testing.
It contains multiple sections to generate chunks.

Section 2: Content
More content here for chunking purposes.
This helps test the progress tracking system.

Section 3: Conclusion
Final section with some test data.
""")

        # Ingest with callback
        chunks = pipeline.ingest_single_file(
            test_file,
            progress_callback=test_callback,
            file_number=1,
            total_files=1
        )

        logger.info(f"Ingested {chunks} chunks")
        logger.info(f"Callback events received: {len(test_callback.events)}")

        # Check events
        event_types = [e[0] for e in test_callback.events]

        required_events = ['file_start', 'file_complete']
        for event_type in required_events:
            if event_type in event_types:
                logger.info(f"✓ Event '{event_type}' received")
            else:
                logger.warning(f"⚠ Event '{event_type}' NOT received")

        # Check file_complete event
        complete_events = [e for e in test_callback.events if e[0] == 'file_complete']
        if complete_events:
            event = complete_events[0]
            filename, chunks_added, success, error = event[1:5]
            logger.info(f"✓ File complete: {filename}, {chunks_added} chunks, success={success}")
            if error:
                logger.info(f"  Error: {error}")

        # Cleanup
        test_file.unlink()

        return chunks > 0 and len(test_callback.events) > 0

    except Exception as e:
        logger.error(f"FAIL: Test failed with exception: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_progress_callback_multiple_files():
    """Test progress callbacks on multiple file ingestion"""
    print("\n" + "="*70)
    print("TEST 3: Progress Callback - Multiple Files (ingest_from_directory)")
    print("="*70)

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Create test files
            for i in range(3):
                test_file = tmpdir / f"test_file_{i}.txt"
                test_file.write_text(f"""
TEST DOCUMENT {i}

This is test file number {i}.
It contains some sample content for testing the progress callback system.

The callback should track progress across all {i} files.
Multiple callbacks should be triggered during ingestion.
""")

            pipeline = DocumentIngestionPipeline()
            test_callback = TestProgressCallback()

            # Ingest from directory with callback
            total_chunks = pipeline.ingest_from_directory(
                directory=tmpdir,
                progress_callback=test_callback
            )

            logger.info(f"Ingested {total_chunks} chunks from {tmpdir}")
            logger.info(f"Callback events received: {len(test_callback.events)}")

            # Check events
            event_types = [e[0] for e in test_callback.events]

            # Should have multiple file_start and file_complete events
            file_start_events = [e for e in test_callback.events if e[0] == 'file_start']
            file_complete_events = [e for e in test_callback.events if e[0] == 'file_complete']
            batch_complete_events = [e for e in test_callback.events if e[0] == 'batch_complete']

            logger.info(f"✓ file_start events: {len(file_start_events)}")
            logger.info(f"✓ file_complete events: {len(file_complete_events)}")
            logger.info(f"✓ batch_complete events: {len(batch_complete_events)}")

            # Batch complete should have been called
            if batch_complete_events:
                event = batch_complete_events[0]
                total_files, successful, failed, total_chunks_reported, elapsed = event[1:6]
                logger.info(f"✓ Batch complete: {successful}/{total_files} files, {total_chunks_reported} chunks, {elapsed:.2f}s")

            return total_chunks > 0 and len(file_complete_events) > 0

    except Exception as e:
        logger.error(f"FAIL: Test failed with exception: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def test_callback_with_blacklisted_pdf():
    """Test that corrupted PDFs are blacklisted before processing"""
    print("\n" + "="*70)
    print("TEST 4: Corrupted PDF Blacklisting")
    print("="*70)

    try:
        # Create corrupted PDF in documents dir
        test_pdf = DOCUMENTS_DIR / "corrupted_test.pdf"
        test_pdf.write_bytes(b"NOT A REAL PDF" + b"X" * 50)

        try:
            pipeline = DocumentIngestionPipeline()
            test_callback = TestProgressCallback()

            # Ingest with callback
            chunks = pipeline.ingest_single_file(
                test_pdf,
                progress_callback=test_callback,
                file_number=1,
                total_files=1
            )

            logger.info(f"Ingested {chunks} chunks from corrupted PDF")

            # Should have file_complete with error
            complete_events = [e for e in test_callback.events if e[0] == 'file_complete']
            if complete_events:
                event = complete_events[0]
                filename, chunks_added, success, error = event[1:5]
                logger.info(f"File complete: {filename}, success={success}")
                if error:
                    logger.info(f"✓ Error reported: {error}")

                if not success and error:
                    logger.info("✓ Corrupted PDF properly reported as failure")
                    return True

            return False

        finally:
            # Cleanup
            if test_pdf.exists():
                test_pdf.unlink()

    except Exception as e:
        logger.error(f"FAIL: Test failed with exception: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def main():
    """Run all FASE 13+14 integration tests"""
    print("\n" + "="*70)
    print("FASE 13+14 INTEGRATION TEST SUITE")
    print("Progress Callbacks + PDF Validator")
    print("="*70)

    results = {
        "PDF Validation": test_pdf_validation_integration(),
        "Progress Callback (Single File)": test_progress_callback_single_file(),
        "Progress Callback (Multiple Files)": test_progress_callback_multiple_files(),
        "Corrupted PDF Blacklisting": test_callback_with_blacklisted_pdf(),
    }

    print("\n" + "="*70)
    print("TEST RESULTS SUMMARY")
    print("="*70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "PASS" if result else "FAIL"
        print(f"{test_name:.<50} {status}")

    print("-"*70)
    print(f"Total: {passed}/{total} passed")

    if passed == total:
        print("\nAll FASE 13+14 integration tests passed!")
        return 0
    else:
        print(f"\n{total - passed} test(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
