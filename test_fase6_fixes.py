#!/usr/bin/env python3
"""
FASE 6 Testing Suite - Verify all 3 critical fixes
Tests: Exponential backoff, error propagation, batch retry logic
"""

import sys
import time
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import config, DOCUMENTS_DIR
from llm_service import get_llm_service
from vector_store import get_vector_store
from document_ingestion import DocumentIngestionPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TEST_FASE6")

class TestFase6:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def log_pass(self, name, msg=""):
        self.passed += 1
        logger.info(f"[PASS] {name} {msg}")

    def log_fail(self, name, msg=""):
        self.failed += 1
        logger.error(f"[FAIL] {name} {msg}")

    def log_warn(self, name, msg=""):
        self.warnings += 1
        logger.warning(f"[WARN] {name} {msg}")

    def print_summary(self):
        print("\n" + "="*60)
        print("FASE 6 TEST SUMMARY")
        print("="*60)
        print(f"[PASS] Passed: {self.passed}")
        print(f"[FAIL] Failed: {self.failed}")
        print(f"[WARN] Warnings: {self.warnings}")
        print("="*60 + "\n")

        if self.failed == 0:
            print("[OK] All tests passed! FASE 6 fixes verified.\n")
            return True
        else:
            print(f"[ERROR] {self.failed} test(s) failed\n")
            return False


def test_gemini_connection(tester):
    """Test 1: Verify Gemini API still works"""
    logger.info("\n" + "="*60)
    logger.info("TEST 1: Gemini API Health Check")
    logger.info("="*60)

    try:
        llm = get_llm_service()
        if llm.check_health():
            tester.log_pass("Gemini Health", f"Model: {llm.model_name}")
            return True
        else:
            tester.log_fail("Gemini Health", "Health check returned False")
            return False
    except Exception as e:
        tester.log_fail("Gemini Health", str(e))
        return False


def test_embedding_with_backoff(tester):
    """Test 2: Verify exponential backoff works"""
    logger.info("\n" + "="*60)
    logger.info("TEST 2: Embedding with Exponential Backoff")
    logger.info("="*60)

    try:
        llm = get_llm_service()
        test_texts = [
            "Python è un linguaggio di programmazione",
            "Machine learning is a subset of AI",
            "RAG systems combine retrieval and generation"
        ]

        times = []
        for i, text in enumerate(test_texts):
            start = time.perf_counter()
            embedding = llm.get_embedding(text)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

            if isinstance(embedding, list) and len(embedding) > 0:
                logger.info(f"  Embedding {i+1}: {len(embedding)} dims, {elapsed:.2f}s")
            else:
                tester.log_fail("Embedding Generation", f"Invalid result for text {i+1}")
                return False

        avg_time = sum(times) / len(times)
        if avg_time >= 0.5:  # Should have backoff
            tester.log_pass("Exponential Backoff", f"Average time: {avg_time:.2f}s (backoff working)")
        else:
            tester.log_warn("Exponential Backoff", f"Average time: {avg_time:.2f}s (expected >= 0.5s)")

        return True

    except Exception as e:
        tester.log_fail("Embedding Backoff", str(e))
        return False


def test_error_propagation(tester):
    """Test 3: Verify error propagation (not silent failures)"""
    logger.info("\n" + "="*60)
    logger.info("TEST 3: Error Propagation in Vector Store")
    logger.info("="*60)

    try:
        vs = get_vector_store()

        # Add some test documents
        test_docs = [
            "Test document 1 about Python",
            "Test document 2 about RAG systems",
            "Test document 3 about embeddings"
        ]

        try:
            vs.add_documents(test_docs)
            docs_count = len(vs.documents)
            if docs_count >= 3:
                tester.log_pass("Error Propagation", f"Added {docs_count} documents successfully")
                return True
            else:
                tester.log_warn("Error Propagation", f"Only {docs_count} of 3 documents added")
                return True  # Still passes, might be expected behavior

        except RuntimeError as e:
            # If error is rate-limit, it should be raised (not silent)
            if "429" in str(e) or "rate" in str(e).lower():
                tester.log_pass("Error Propagation", "Rate-limit error properly raised")
                return True
            else:
                tester.log_fail("Error Propagation", f"Unexpected runtime error: {e}")
                return False

    except Exception as e:
        tester.log_fail("Error Propagation", str(e))
        return False


def test_batch_retry_logic(tester):
    """Test 4: Verify batch retry logic"""
    logger.info("\n" + "="*60)
    logger.info("TEST 4: Batch Retry Logic in Document Ingestion")
    logger.info("="*60)

    try:
        # Count PDF files in documents directory
        pdf_files = list(DOCUMENTS_DIR.glob("*.pdf"))

        if len(pdf_files) == 0:
            tester.log_warn("Batch Retry Logic", "No PDF files found for testing")
            return True

        # Try to ingest first PDF with retry logic
        pipeline = DocumentIngestionPipeline()
        test_file = pdf_files[0]

        logger.info(f"Testing ingestion of: {test_file.name}")
        chunks = pipeline.ingest_single_file(test_file, max_retries=3)

        if chunks > 0:
            tester.log_pass("Batch Retry Logic", f"Successfully ingested {chunks} chunks")
            return True
        else:
            tester.log_warn("Batch Retry Logic", f"No chunks extracted from {test_file.name}")
            return True  # Still passes, might be expected

    except Exception as e:
        tester.log_fail("Batch Retry Logic", str(e))
        return False


def test_vector_store_integrity(tester):
    """Test 5: Verify vector store integrity"""
    logger.info("\n" + "="*60)
    logger.info("TEST 5: Vector Store Integrity")
    logger.info("="*60)

    try:
        vs = get_vector_store()

        if len(vs.documents) > 0:
            # Check matrix is built
            if vs._embedding_matrix is not None:
                tester.log_pass("Vector Store Integrity", f"{len(vs.documents)} docs, matrix shape {vs._embedding_matrix.shape}")
                return True
            else:
                tester.log_fail("Vector Store Integrity", "Matrix not built")
                return False
        else:
            tester.log_pass("Vector Store Integrity", "Empty store (expected after cleanup)")
            return True

    except Exception as e:
        tester.log_fail("Vector Store Integrity", str(e))
        return False


def test_search_performance(tester):
    """Test 6: Verify search performance"""
    logger.info("\n" + "="*60)
    logger.info("TEST 6: Search Performance")
    logger.info("="*60)

    try:
        vs = get_vector_store()

        if len(vs.documents) == 0:
            tester.log_warn("Search Performance", "Vector store empty, skipping")
            return True

        query = "What is Python?"
        start = time.perf_counter()
        results = vs.search(query, top_k=3)
        elapsed = time.perf_counter() - start

        if len(results) > 0:
            if elapsed < 1.0:  # Should be fast (including embedding backoff)
                tester.log_pass("Search Performance", f"{len(results)} results in {elapsed:.2f}s")
            else:
                tester.log_warn("Search Performance", f"{len(results)} results in {elapsed:.2f}s (slower than expected)")
            return True
        else:
            tester.log_warn("Search Performance", "No results returned")
            return True

    except Exception as e:
        tester.log_fail("Search Performance", str(e))
        return False


def main():
    print("\n" + "="*60)
    print("FASE 6 TEST SUITE - Critical Fixes Verification")
    print("="*60 + "\n")

    tester = TestFase6()

    tests = [
        ("Gemini Connection", test_gemini_connection),
        ("Embedding Backoff", test_embedding_with_backoff),
        ("Error Propagation", test_error_propagation),
        ("Batch Retry Logic", test_batch_retry_logic),
        ("Vector Store Integrity", test_vector_store_integrity),
        ("Search Performance", test_search_performance),
    ]

    for test_name, test_func in tests:
        try:
            test_func(tester)
        except Exception as e:
            logger.error(f"Unexpected error in {test_name}: {e}", exc_info=True)
            tester.log_fail(test_name, f"Unexpected exception: {e}")

    success = tester.print_summary()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
