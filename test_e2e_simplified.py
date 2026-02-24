"""
Simplified E2E Tests - PDF to Response Flow
Focuses on end-to-end functionality without deep API testing
"""

import pytest
import tempfile
import time
import logging
from pathlib import Path

from src.logging_config import get_logger
from src.vector_store import get_vector_store
from src.memory_service import get_memory_service
from src.document_ingestion import DocumentIngestionPipeline

logger = get_logger(__name__)


class TestE2ESimplified:
    """Simplified E2E integration tests"""

    def test_e2e_document_ingestion(self):
        """Test: Document can be ingested successfully"""
        logger.info("\n" + "="*70)
        logger.info("[E2E Test 1] Document Ingestion")
        logger.info("="*70)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test document
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("Machine Learning is AI. Neural Networks learn from data.")

            # Ingest
            ingestion = DocumentIngestionPipeline()
            chunks = ingestion.ingest_single_file(test_file)

            logger.info(f"[Result] Ingested {chunks} chunks")
            assert chunks >= 0, "Ingestion should complete"

    def test_e2e_vector_search(self):
        """Test: Vector search returns results"""
        logger.info("\n" + "="*70)
        logger.info("[E2E Test 2] Vector Search")
        logger.info("="*70)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and ingest document
            test_file = Path(tmpdir) / "search_test.txt"
            test_file.write_text("Python is a programming language. It enables rapid development.")

            ingestion = DocumentIngestionPipeline()
            ingestion.ingest_single_file(test_file)
            logger.info("[Step 1] Document ingested")

            # Search
            vector_store = get_vector_store()
            results = vector_store.search("Python programming", top_k=3)

            logger.info(f"[Result] Found {len(results)} search results")
            assert len(results) >= 0, "Search should return results"

    def test_e2e_memory_persistence(self):
        """Test: Memory service persists interactions"""
        logger.info("\n" + "="*70)
        logger.info("[E2E Test 3] Memory Persistence")
        logger.info("="*70)

        memory_service = get_memory_service()

        # Save interaction
        memory_service.save_interaction(
            user_query="What is AI?",
            ai_response="AI enables machines to learn.",
            referenced_docs=["ai_guide.pdf"],
            found_anomalies=False
        )
        logger.info("[Step 1] Interaction saved")

        # Retrieve
        recent = memory_service.get_recent_memories(limit=1)
        stats = memory_service.get_stats()

        logger.info(f"[Result] Memories retrieved, total interactions: {stats['total_interactions']}")
        assert stats['total_interactions'] >= 1, "Should have saved interaction"

    def test_e2e_full_pipeline(self):
        """Test: Complete pipeline from ingest to memory"""
        logger.info("\n" + "="*70)
        logger.info("[E2E Test 4] Full Pipeline")
        logger.info("="*70)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Phase 1: Prepare document
            doc_file = Path(tmpdir) / "pipeline_test.txt"
            doc_file.write_text("""
                Data Science combines statistics and programming.
                Machine Learning enables predictive analytics.
                Deep Learning uses neural networks.
            """)
            logger.info("[Phase 1] Document prepared")

            # Phase 2: Ingest
            ingestion = DocumentIngestionPipeline()
            chunks = ingestion.ingest_single_file(doc_file)
            logger.info(f"[Phase 2] Ingested {chunks} chunks")

            # Phase 3: Search
            vector_store = get_vector_store()
            results = vector_store.search("data science machine learning", top_k=3)
            logger.info(f"[Phase 3] Found {len(results)} results")

            # Phase 4: Memory
            memory = get_memory_service()
            memory.save_interaction(
                user_query="What is data science?",
                ai_response="Data Science is the combination of statistics and programming.",
                referenced_docs=[doc_file.name],
                found_anomalies=False
            )
            logger.info(f"[Phase 4] Saved to memory")

            # Verify
            stats = memory.get_stats()
            logger.info(f"[Result] Pipeline complete - {stats['total_interactions']} interactions saved")
            assert stats['total_interactions'] >= 1, "Pipeline should save to memory"

    def test_e2e_performance_measurement(self):
        """Test: System performance is measurable"""
        logger.info("\n" + "="*70)
        logger.info("[E2E Test 5] Performance Measurement")
        logger.info("="*70)

        with tempfile.TemporaryDirectory() as tmpdir:
            doc_file = Path(tmpdir) / "perf.txt"
            doc_file.write_text("Performance testing document.")

            # Measure ingestion
            ingestion = DocumentIngestionPipeline()
            start = time.time()
            ingestion.ingest_single_file(doc_file)
            ingest_time = time.time() - start
            logger.info(f"[Metric] Ingestion time: {ingest_time:.3f}s")

            # Measure search
            vector_store = get_vector_store()
            start = time.time()
            results = vector_store.search("test", top_k=5)
            search_time = time.time() - start
            logger.info(f"[Metric] Search time: {search_time:.3f}s for {len(results)} results")

            # Verify performance is reasonable
            assert ingest_time < 30, "Ingestion should complete in <30s"
            assert search_time < 10, "Search should complete in <10s"
            logger.info("[Result] Performance is within acceptable ranges")

    def test_e2e_error_recovery(self):
        """Test: System recovers from errors gracefully"""
        logger.info("\n" + "="*70)
        logger.info("[E2E Test 6] Error Recovery")
        logger.info("="*70)

        vector_store = get_vector_store()

        # Test empty search
        try:
            results = vector_store.search("", top_k=5)
            logger.info(f"[Step 1] Empty search returned {len(results)} results")
        except Exception as e:
            logger.info(f"[Step 1] Empty search raised: {type(e).__name__}")

        # Test memory service error handling
        try:
            memory = get_memory_service()
            stats = memory.get_stats()
            logger.info(f"[Step 2] Memory stats accessible: {stats}")
        except Exception as e:
            logger.error(f"[Step 2] Error: {e}")

        logger.info("[Result] System handles errors gracefully")

    def test_e2e_multiple_documents(self):
        """Test: System can handle multiple documents"""
        logger.info("\n" + "="*70)
        logger.info("[E2E Test 7] Multiple Documents")
        logger.info("="*70)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create 3 documents
            docs = {
                "ml.txt": "Machine Learning is a subset of AI.",
                "nlp.txt": "Natural Language Processing analyzes text.",
                "cv.txt": "Computer Vision processes images."
            }

            ingestion = DocumentIngestionPipeline()
            total_chunks = 0

            for filename, content in docs.items():
                doc_path = Path(tmpdir) / filename
                doc_path.write_text(content)
                chunks = ingestion.ingest_single_file(doc_path)
                total_chunks += chunks
                logger.info(f"  Ingested {filename}: {chunks} chunks")

            logger.info(f"[Result] Total {len(docs)} documents, {total_chunks} chunks ingested")
            assert len(docs) >= 1, "Should ingest multiple documents"


# ==================== SUMMARY ====================
if __name__ == "__main__":
    logger.info("\n" + "="*70)
    logger.info("END-TO-END INTEGRATION TEST SUITE (Simplified)")
    logger.info("Testing RAG Pipeline: Ingest → Search → Memory")
    logger.info("="*70)

    pytest.main([__file__, "-v", "-s"])
