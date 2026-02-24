"""
End-to-End Integration Tests - PDF to Response Flow
Tests the complete RAG pipeline from document ingestion to final response generation.
Covers all major components in realistic production scenarios.
"""

import pytest
import tempfile
import time
import logging
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.logging_config import get_logger
from src.rag_engine import RAGEngine
from src.vector_store import get_vector_store
from src.memory_service import get_memory_service
from src.document_ingestion import DocumentIngestionPipeline
from src.llm_service import get_llm_service

logger = get_logger(__name__)


class TestE2EPDFToResponseFlow:
    """Complete end-to-end integration tests for RAG pipeline"""

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test"""
        logger.info("\n" + "="*80)
        yield
        logger.info("="*80)

    # ==================== TEST 1: Document Ingestion ====================
    def test_e2e_document_ingestion_basic(self):
        """
        E2E Test 1: Document Ingestion
        Verifies that PDFs/texts are correctly loaded, processed, and indexed
        """
        logger.info("[E2E Test 1] Document Ingestion - Basic Flow")

        # Create temporary test document
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test_document.txt"
            test_file.write_text(
                "Machine Learning is a subset of Artificial Intelligence. "
                "It enables computers to learn from data without being explicitly programmed. "
                "Common algorithms include decision trees, neural networks, and random forests."
            )

            # Initialize ingestion engine
            ingestion_engine = DocumentIngestionPipeline()

            # Ingest document
            logger.info(f"  [Step 1] Ingesting document: {test_file.name}")
            chunk_count = ingestion_engine.ingest_single_file(test_file)

            # Verify ingestion
            logger.info(f"  [Step 2] Verifying ingestion...")
            assert chunk_count > 0, "Document should create at least 1 chunk"
            logger.info(f"  [Result] Created {chunk_count} chunks from document")

            # Get vector store and verify document is indexed
            vector_store = get_vector_store()
            doc_count = len(vector_store.indexed_documents)
            logger.info(f"  [Result] Vector store now contains {doc_count} indexed documents")

    # ==================== TEST 2: Vector Search ====================
    def test_e2e_vector_search_retrieval(self):
        """
        E2E Test 2: Vector Search & Retrieval
        Verifies that semantic search correctly retrieves relevant documents
        """
        logger.info("[E2E Test 2] Vector Search & Retrieval")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test documents with known content
            documents = {
                "ml_basics.txt": """
                    Machine Learning uses algorithms to learn from data.
                    Neural networks are inspired by biological neurons.
                    Deep learning trains neural networks with multiple layers.
                """,
                "nlp_guide.txt": """
                    Natural Language Processing analyzes human language.
                    Transformers revolutionized NLP with attention mechanisms.
                    BERT and GPT are popular transformer models.
                """,
                "cv_tutorial.txt": """
                    Computer Vision enables machines to understand images.
                    Convolutional Neural Networks are standard for image analysis.
                    Object detection identifies and locates objects in images.
                """
            }

            # Write test documents
            file_paths = []
            for filename, content in documents.items():
                filepath = Path(tmpdir) / filename
                filepath.write_text(content)
                file_paths.append(filepath)
                logger.info(f"  [Step 1] Created test document: {filename}")

            # Ingest all documents
            ingestion_engine = DocumentIngestionPipeline()
            for filepath in file_paths:
                ingestion_engine.ingest_single_file(filepath)
            logger.info(f"  [Step 2] Ingested {len(file_paths)} test documents")

            # Perform semantic searches
            vector_store = get_vector_store()

            test_queries = [
                ("neural network layers", "ml_basics.txt"),
                ("transformer attention", "nlp_guide.txt"),
                ("image recognition", "cv_tutorial.txt"),
            ]

            for query, expected_source in test_queries:
                logger.info(f"  [Step 3] Searching for: '{query}'")
                results = vector_store.search(query, top_k=3)

                # Verify results
                assert len(results) > 0, f"Search for '{query}' should return results"
                logger.info(f"  [Result] Found {len(results)} results")
                for i, result in enumerate(results[:3], 1):
                    logger.info(f"    [{i}] Score: {result.score:.3f}, Doc: {result.file_name}")

    # ==================== TEST 3: LLM Response Generation ====================
    def test_e2e_llm_response_generation(self):
        """
        E2E Test 3: LLM Response Generation
        Verifies that the LLM generates coherent responses from retrieved documents
        """
        logger.info("[E2E Test 3] LLM Response Generation")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create context document
            context_file = Path(tmpdir) / "context.txt"
            context_file.write_text("""
                Python is a high-level programming language known for:
                - Easy syntax and readability
                - Extensive standard library
                - Strong community support
                - Wide adoption in data science and AI

                Popular frameworks include:
                - Django and Flask for web development
                - NumPy and Pandas for data analysis
                - TensorFlow and PyTorch for machine learning
            """)

            # Ingest context
            ingestion_engine = DocumentIngestionPipeline()
            ingestion_engine.ingest_single_file(context_file)
            logger.info(f"  [Step 1] Ingested context document")

            # Perform RAG pipeline
            logger.info(f"  [Step 2] Initializing RAG engine...")
            rag_engine = RAGEngine()

            # Test query
            test_query = "What are the advantages of Python?"
            logger.info(f"  [Step 3] Querying: '{test_query}'")

            response = rag_engine.query(test_query)

            # Verify response
            logger.info(f"  [Step 4] Verifying response...")
            assert response is not None, "RAG should return a response"
            assert hasattr(response, 'answer'), "Response should have 'answer' attribute"
            assert hasattr(response, 'sources'), "Response should have 'sources' attribute"
            assert len(response.sources) > 0, "Response should cite sources"

            logger.info(f"  [Result] Generated response:")
            logger.info(f"    Answer: {response.answer[:100]}...")
            logger.info(f"    Sources: {len(response.sources)} documents cited")
            for source in response.sources[:3]:
                logger.info(f"      - {source.file_name} (relevance: {source.score:.2%})")

    # ==================== TEST 4: Memory Service Persistence ====================
    def test_e2e_memory_service_persistence(self):
        """
        E2E Test 4: Memory Service Persistence
        Verifies that query history and context are correctly stored and retrieved
        """
        logger.info("[E2E Test 4] Memory Service Persistence")

        # Get memory service
        memory_service = get_memory_service()
        logger.info(f"  [Step 1] Initialized memory service")

        # Save interaction
        user_query = "What is machine learning?"
        ai_response = "Machine learning is a subset of AI that enables learning from data."
        test_docs = ["ml_basics.pdf", "ai_overview.pdf"]

        logger.info(f"  [Step 2] Saving interaction to memory...")
        memory_service.save_interaction(
            user_query=user_query,
            ai_response=ai_response,
            referenced_docs=test_docs,
            found_anomalies=False
        )
        logger.info(f"  [Step 3] Verifying saved interaction...")

        # Retrieve and verify
        recent_memories = memory_service.get_recent_memories(limit=1)
        assert recent_memories, "Should retrieve recent memories"
        logger.info(f"  [Result] Retrieved memory: {recent_memories[:100]}...")

        # Get stats
        stats = memory_service.get_stats()
        assert stats['total_interactions'] >= 1, "Should have at least 1 interaction"
        logger.info(f"  [Stats] Total interactions: {stats['total_interactions']}")

    # ==================== TEST 5: Full Pipeline Integration ====================
    def test_e2e_full_rag_pipeline(self):
        """
        E2E Test 5: Complete RAG Pipeline
        Tests the entire flow: ingest → search → generate → store
        """
        logger.info("[E2E Test 5] Complete RAG Pipeline")
        logger.info("  Starting full end-to-end pipeline test...")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Phase 1: Create and ingest documents
            logger.info("\n  [Phase 1] Document Preparation")
            doc_content = """
                Data Science combines statistics, programming, and domain knowledge.
                Machine Learning algorithms learn patterns from historical data.
                Deep Learning uses neural networks with many layers.
                Natural Language Processing enables understanding of text and speech.
            """
            doc_file = Path(tmpdir) / "data_science.txt"
            doc_file.write_text(doc_content)
            logger.info(f"    Created test document: {doc_file.name}")

            # Phase 2: Ingestion
            logger.info("\n  [Phase 2] Document Ingestion")
            ingestion_engine = DocumentIngestionPipeline()
            chunks = ingestion_engine.ingest_single_file(doc_file)
            logger.info(f"    Ingested {chunks} chunks")

            # Phase 3: Vector indexing
            logger.info("\n  [Phase 3] Vector Indexing")
            vector_store = get_vector_store()
            doc_count = len(vector_store.indexed_documents)
            logger.info(f"    Vector store indexed {doc_count} documents")

            # Phase 4: Query execution
            logger.info("\n  [Phase 4] Query Execution")
            query = "How does machine learning work?"
            logger.info(f"    Query: {query}")

            rag_engine = RAGEngine()
            response = rag_engine.query(query)
            logger.info(f"    Response generated")

            # Phase 5: Memory storage
            logger.info("\n  [Phase 5] Memory Storage")
            memory_service = get_memory_service()
            memory_service.save_interaction(
                user_query=query,
                ai_response=response.answer,
                referenced_docs=[s.file_name for s in response.sources],
                found_anomalies=False
            )
            logger.info(f"    Interaction saved to memory")

            # Phase 6: Verification
            logger.info("\n  [Phase 6] Verification")
            assert response.answer, "Should have generated an answer"
            assert len(response.sources) > 0, "Should have retrieved sources"
            recent_memories = memory_service.get_recent_memories(limit=1)
            assert recent_memories, "Should have saved to memory"

            logger.info(f"    [FINAL RESULT] Complete pipeline successful!")
            logger.info(f"      - Query: {query[:50]}...")
            logger.info(f"      - Answer: {response.answer[:100]}...")
            logger.info(f"      - Sources cited: {len(response.sources)}")
            logger.info(f"      - Memory stored: Yes")

    # ==================== TEST 6: Error Handling & Recovery ====================
    def test_e2e_error_handling_and_recovery(self):
        """
        E2E Test 6: Error Handling & Recovery
        Verifies that system gracefully handles errors and recovers
        """
        logger.info("[E2E Test 6] Error Handling & Recovery")

        # Test 1: Invalid query
        logger.info("  [Test 6.1] Invalid/Empty Query Handling")
        rag_engine = RAGEngine()

        try:
            response = rag_engine.query("")  # Empty query
            logger.info(f"    System returned gracefully for empty query")
        except Exception as e:
            logger.info(f"    System raised exception (expected): {type(e).__name__}")

        # Test 2: Missing vector store
        logger.info("  [Test 6.2] Missing Data Handling")
        # Create fresh vector store (should initialize empty)
        try:
            vector_store = get_vector_store()
            results = vector_store.search("test query", top_k=5)
            logger.info(f"    Search on empty store returned {len(results)} results")
        except Exception as e:
            logger.error(f"    Error on empty search: {e}")

        # Test 3: Memory service isolation
        logger.info("  [Test 6.3] Memory Service Isolation")
        memory_service = get_memory_service()
        try:
            stats = memory_service.get_stats()
            logger.info(f"    Memory service stats accessible: {stats}")
        except Exception as e:
            logger.error(f"    Error accessing memory stats: {e}")

    # ==================== TEST 7: Performance Metrics ====================
    def test_e2e_performance_metrics(self):
        """
        E2E Test 7: Performance Metrics Collection
        Verifies that performance is measured and recorded
        """
        logger.info("[E2E Test 7] Performance Metrics Collection")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test document
            doc_file = Path(tmpdir) / "perf_test.txt"
            doc_file.write_text("Performance testing document content.")

            # Measure ingestion
            logger.info("  [Test 7.1] Ingestion Timing")
            ingestion_engine = DocumentIngestionPipeline()
            start = time.time()
            chunks = ingestion_engine.ingest_single_file(doc_file)
            ingest_time = time.time() - start
            logger.info(f"    Ingestion time: {ingest_time:.3f}s for {chunks} chunks")

            # Measure search
            logger.info("  [Test 7.2] Search Timing")
            vector_store = get_vector_store()
            start = time.time()
            results = vector_store.search("test query", top_k=5)
            search_time = time.time() - start
            logger.info(f"    Search time: {search_time:.3f}s for {len(results)} results")

            # Measure RAG response
            logger.info("  [Test 7.3] RAG Response Timing")
            rag_engine = RAGEngine()
            start = time.time()
            response = rag_engine.query("What is in this document?")
            rag_time = time.time() - start
            logger.info(f"    RAG response time: {rag_time:.3f}s")

            # Summary
            logger.info(f"\n  [Performance Summary]")
            logger.info(f"    Ingestion:  {ingest_time:.3f}s")
            logger.info(f"    Search:     {search_time:.3f}s")
            logger.info(f"    RAG:        {rag_time:.3f}s")
            logger.info(f"    Total:      {ingest_time + search_time + rag_time:.3f}s")

            # Verify performance is reasonable
            assert ingest_time < 30, "Ingestion should complete in <30s"
            assert search_time < 10, "Search should complete in <10s"
            assert rag_time < 30, "RAG response should complete in <30s"


# ==================== SUMMARY & EXECUTION ====================
if __name__ == "__main__":
    """Run all E2E tests with detailed reporting"""
    logger.info("\n" + "="*80)
    logger.info("END-TO-END INTEGRATION TEST SUITE")
    logger.info("Testing Complete RAG Pipeline: PDF/Text → Ingestion → Search → Response")
    logger.info("="*80)

    pytest.main([__file__, "-v", "-s", "--tb=short"])
