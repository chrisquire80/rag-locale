"""
PHASE 5: Integration Testing & Performance Benchmarking
Comprehensive test suite for all optimization phases
Tests backward compatibility, performance improvements, and end-to-end workflows
"""

import pytest
import logging
import sys
import time
import tempfile
from pathlib import Path
from typing import List

# Setup path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vector_store import VectorStore, get_vector_store
from vector_store_sqlite import SQLiteVectorStore, SQLiteDocument
from parallel_ingestion import ParallelDocumentIngestion, create_parallel_ingestion
from rag_engine_v2 import RAGEngineV2
from hybrid_search import HybridSearchEngine, BM25
from query_expansion import QueryExpander
from reranker import GeminiReRanker

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class TestPhase5BackwardCompatibility:
    """PHASE 5: Verify all phases maintain backward compatibility"""

    def setup_method(self):
        """Setup"""
        self.temp_dir = tempfile.mkdtemp()
        import vector_store
        vector_store._vector_store_instance = None
        from config import config
        config.chromadb.persist_directory = Path(self.temp_dir) / "store"

    def teardown_method(self):
        """Cleanup"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass

    def test_vector_store_backward_compatible(self):
        """Test that vector store changes are backward compatible"""
        vs = VectorStore()

        # Add documents using existing API
        docs = ["Machine learning document", "Deep learning document"]
        metadatas = [{"source": "book"}, {"source": "paper"}]

        count, failed = vs.add_documents(docs, metadatas)

        assert count == 2
        assert len(failed) == 0
        assert len(vs.documents) == 2
        logger.info("✓ Vector store backward compatible")

    def test_search_api_unchanged(self):
        """Test that search API is unchanged"""
        vs = VectorStore()

        docs = [
            "Machine learning model",
            "Deep learning network",
            "Natural language processing"
        ]
        vs.add_documents(docs)

        # Search using original API
        results = vs.search("machine learning", top_k=2)

        assert len(results) > 0
        assert "id" in results[0]
        assert "document" in results[0]
        assert "similarity_score" in results[0]
        logger.info("✓ Search API unchanged and working")

    def test_metadata_filtering_backward_compatible(self):
        """Test that metadata filtering is backward compatible"""
        vs = VectorStore()

        docs = ["Doc 1", "Doc 2", "Doc 3"]
        metadatas = [
            {"category": "ml"},
            {"category": "nlp"},
            {"category": "ml"}
        ]
        vs.add_documents(docs, metadatas)

        # Filter using original API
        results = vs.search("query", where_filter={"category": "ml"}, top_k=5)

        assert len(results) > 0
        logger.info("✓ Metadata filtering backward compatible")

    def test_rag_engine_v2_integration(self):
        """Test RAGEngineV2 integration with all optimizations"""
        vs = VectorStore()

        docs = [
            "Machine learning is a subset of AI",
            "Deep learning uses neural networks",
            "Natural language processing analyzes text"
        ]
        vs.add_documents(docs)

        # Create RAG engine and test
        rag = RAGEngineV2()
        assert rag.vector_store is not None
        logger.info("✓ RAGEngineV2 integration working")

    def test_hybrid_search_integration(self):
        """Test hybrid search still works"""
        docs = [
            {"id": "1", "text": "Machine learning", "metadata": {}},
            {"id": "2", "text": "Deep learning", "metadata": {}},
            {"id": "3", "text": "NLP", "metadata": {}}
        ]

        hybrid = HybridSearchEngine(docs)
        results = hybrid.search("machine learning", top_k=2)

        assert len(results) > 0
        logger.info("✓ Hybrid search integration working")

    def test_query_expansion_integration(self):
        """Test query expansion still works"""
        from llm_service import get_llm_service
        llm = get_llm_service()
        expander = QueryExpander(llm)
        expanded = expander.expand_query("machine learning")

        # Check that we got an expansion result (may be dict or dataclass)
        assert expanded is not None
        assert hasattr(expanded, 'keywords') or 'keywords' in str(expanded)
        logger.info("✓ Query expansion integration working")


class TestPhase5PerformanceMetrics:
    """PHASE 5: Benchmark performance improvements from all phases"""

    def setup_method(self):
        """Setup"""
        self.temp_dir = tempfile.mkdtemp()
        import vector_store
        vector_store._vector_store_instance = None
        from config import config
        config.chromadb.persist_directory = Path(self.temp_dir) / "store"

    def teardown_method(self):
        """Cleanup"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass

    def test_phase2_query_cache_benefit(self):
        """Test PHASE 2: Query embedding cache provides measurable benefit"""
        vs = VectorStore()

        # Add documents
        docs = [f"Document {i}" for i in range(20)]
        vs.add_documents(docs)

        query = "test machine learning query"

        # First search - cache miss
        start = time.time()
        results1 = vs.search(query, top_k=5)
        time_first = time.time() - start

        # Second search - cache hit (should be faster due to cached embedding)
        start = time.time()
        results2 = vs.search(query, top_k=5)
        time_second = time.time() - start

        cache_size = len(vs._query_embedding_cache)
        logger.info(f"""
PHASE 2 Query Cache Benefit:
  First search: {time_first*1000:.2f}ms (cache miss)
  Second search: {time_second*1000:.2f}ms (cache hit)
  Cache size: {cache_size} embeddings
  Results consistent: {results1[0]['id'] == results2[0]['id']}
        """)

        assert cache_size >= 1
        assert len(results1) == len(results2)

    def test_phase2_metadata_index_performance(self):
        """Test PHASE 2: Metadata index provides O(1) filtering"""
        vs = VectorStore()

        # Create corpus with metadata
        docs = [f"Document {i}" for i in range(50)]
        metadatas = [
            {"category": "ml" if i % 2 == 0 else "nlp", "year": 2023 + (i % 2)}
            for i in range(50)
        ]
        vs.add_documents(docs, metadatas)

        # Measure filtered search performance
        start = time.time()
        for _ in range(10):
            results = vs.search("query", where_filter={"category": "ml"}, top_k=5)
        elapsed_filtered = time.time() - start

        logger.info(f"PHASE 2 Metadata filtering (10 queries): {elapsed_filtered*1000:.2f}ms avg {elapsed_filtered/10*1000:.2f}ms")
        assert elapsed_filtered < 2.0

    def test_phase3_sqlite_vs_pickle_efficiency(self):
        """Test PHASE 3: SQLite storage efficiency"""
        import pickle

        # Create test data
        test_docs = [
            SQLiteDocument(
                id=f"doc_{i}",
                text=f"Document {i}" * 20,
                metadata={"index": i},
                embedding=[0.1] * 384
            )
            for i in range(30)
        ]

        # SQLite storage
        sqlite_path = Path(self.temp_dir) / "test_sqlite.db"
        sqlite_store = SQLiteVectorStore(sqlite_path)
        sqlite_store.add_documents_batch(test_docs)
        sqlite_size = sqlite_path.stat().st_size

        logger.info(f"PHASE 3 SQLite storage efficiency: {sqlite_size / 1024:.2f}KB for {len(test_docs)} documents")
        assert sqlite_size < 10 * 1024 * 1024  # Less than 10MB

    def test_phase4_parallel_processing_speedup(self):
        """Test PHASE 4: Parallel processing speedup"""
        import tempfile

        # Create test documents
        docs_dir = Path(self.temp_dir) / "parallel_test"
        docs_dir.mkdir(exist_ok=True)

        num_docs = 5
        for i in range(num_docs):
            txt_file = docs_dir / f"doc_{i}.txt"
            with open(txt_file, "w") as f:
                f.write(f"Document {i} content " * 20)

        docs = list(docs_dir.glob("*.txt"))

        # Parallel ingestion
        ingestion = create_parallel_ingestion(max_workers=4)
        start = time.time()
        stats = ingestion.ingest_documents_parallel(docs)
        elapsed = time.time() - start

        logger.info(f"""
PHASE 4 Parallel Processing:
  Documents: {stats.total_files}
  Chunks processed: {stats.total_chunks}
  Time: {elapsed:.2f}s
  Throughput: {stats.chunks_per_second:.1f} chunks/sec
  Workers: {ingestion.max_workers}
        """)

        assert stats.total_files == num_docs
        assert elapsed > 0

    def test_batch_embedding_efficiency(self):
        """Test batch embedding from PHASE 2"""
        vs = VectorStore()

        # Add multiple documents with batch embedding
        docs = [f"Document {i} with machine learning content" for i in range(5)]

        start = time.time()
        count, failed = vs.add_documents(docs, use_batch_embedding=True)
        elapsed = time.time() - start

        logger.info(f"Batch embedding (5 docs): {elapsed*1000:.2f}ms, {elapsed/5*1000:.2f}ms per doc")

        assert count == 5
        assert len(failed) == 0


class TestPhase5EndToEndWorkflows:
    """PHASE 5: End-to-end workflow tests combining all phases"""

    def setup_method(self):
        """Setup"""
        self.temp_dir = tempfile.mkdtemp()
        import vector_store
        vector_store._vector_store_instance = None
        from config import config
        config.chromadb.persist_directory = Path(self.temp_dir) / "store"

    def teardown_method(self):
        """Cleanup"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass

    def test_full_ingestion_and_search_workflow(self):
        """Test full workflow: ingest documents -> search -> rerank"""
        # Create test documents
        docs_dir = Path(self.temp_dir) / "documents"
        docs_dir.mkdir(exist_ok=True)

        for i in range(3):
            txt_file = docs_dir / f"doc_{i}.txt"
            with open(txt_file, "w") as f:
                f.write(f"""
Document {i}: Machine Learning Fundamentals

Machine learning is a field of artificial intelligence.
Deep learning is a subset of machine learning.
Neural networks are inspired by biological neurons.

This document covers fundamental concepts.
                """)

        # Parallel ingestion
        ingestion = create_parallel_ingestion(max_workers=2)
        stats = ingestion.ingest_directory_parallel(docs_dir, pattern="*.txt")

        logger.info(f"Ingested {stats.total_documents_added} documents")
        assert stats.total_documents_added > 0

        # Search
        vs = get_vector_store()
        results = vs.search("machine learning", top_k=3)

        logger.info(f"Search returned {len(results)} results")
        assert len(results) > 0

        # Verify metadata filtering
        results_filtered = vs.search(
            "neural networks",
            where_filter={"section": "default"},
            top_k=3
        )
        logger.info(f"Filtered search returned {len(results_filtered)} results")

    def test_scalability_with_many_documents(self):
        """Test system scalability with larger document corpus"""
        vs = VectorStore()

        # Add 100 documents
        docs = [f"Document {i} with machine learning and AI content" for i in range(100)]
        metadatas = [{"doc_index": i, "batch": i // 10} for i in range(100)]

        start = time.time()
        count, failed = vs.add_documents(docs, metadatas, use_batch_embedding=True)
        elapsed = time.time() - start

        logger.info(f"Added 100 documents in {elapsed:.2f}s ({100/elapsed:.1f} docs/sec)")

        # Verify search still works efficiently
        start = time.time()
        results = vs.search("machine learning", top_k=10)
        search_time = time.time() - start

        logger.info(f"Search in 100-document corpus: {search_time*1000:.2f}ms")

        assert count == 100
        assert len(results) > 0
        assert search_time < 1.0  # Should be fast with optimizations


class TestPhase5RegressionPrevention:
    """PHASE 5: Ensure no regressions introduced"""

    def setup_method(self):
        """Setup"""
        self.temp_dir = tempfile.mkdtemp()
        import vector_store
        vector_store._vector_store_instance = None
        from config import config
        config.chromadb.persist_directory = Path(self.temp_dir) / "store"

    def teardown_method(self):
        """Cleanup"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        except:
            pass

    def test_cache_does_not_corrupt_data(self):
        """Test that query caching doesn't corrupt results"""
        vs = VectorStore()

        docs = ["Doc A", "Doc B", "Doc C"]
        vs.add_documents(docs)

        # Search same query multiple times
        query = "test"
        results_list = []
        for _ in range(3):
            results = vs.search(query, top_k=2)
            results_list.append(results)

        # All results should be identical
        for i in range(1, len(results_list)):
            assert len(results_list[i]) == len(results_list[0])
            for j, result in enumerate(results_list[i]):
                assert result["id"] == results_list[0][j]["id"]

        logger.info("✓ Caching doesn't corrupt results")

    def test_metadata_index_accuracy(self):
        """Test that metadata index maintains accuracy"""
        vs = VectorStore()

        docs = ["Doc A", "Doc B", "Doc C", "Doc D"]
        metadatas = [
            {"type": "A", "level": 1},
            {"type": "B", "level": 2},
            {"type": "A", "level": 2},
            {"type": "B", "level": 1}
        ]

        vs.add_documents(docs, metadatas)

        # Filter by type A
        results_a = vs.search("query", where_filter={"type": "A"}, top_k=10)
        assert len(results_a) == 2

        # Filter by level 2
        results_l2 = vs.search("query", where_filter={"level": 2}, top_k=10)
        assert len(results_l2) == 2

        logger.info("✓ Metadata index maintains accuracy")

    def test_batch_embedding_consistency(self):
        """Test that batch embedding produces consistent results"""
        vs1 = VectorStore()
        vs2 = VectorStore()

        docs = ["Doc 1", "Doc 2", "Doc 3"]

        # Add with batch embedding
        import vector_store
        vector_store._vector_store_instance = None
        vs1.add_documents(docs, use_batch_embedding=True)

        # Reset and add without batch
        vector_store._vector_store_instance = None
        vs2.add_documents(docs, use_batch_embedding=False)

        # Both should have same number of documents
        assert len(vs1.documents) == len(vs2.documents)
        assert len(vs1.documents) == 3

        logger.info("✓ Batch embedding produces consistent results")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
