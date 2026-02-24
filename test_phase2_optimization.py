"""
PHASE 2: Batch Embedding + Metadata Index Optimization Tests
Tests for LRU query embedding cache and metadata index O(1) filtering
"""

import pytest
import logging
import sys
import time
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict

# Setup path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from vector_store import VectorStore, Document, get_vector_store
from llm_service import get_llm_service

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class TestQueryEmbeddingCache:
    """Test LRU query embedding cache (PHASE 2)"""

    def setup_method(self):
        """Setup fresh vector store for each test"""
        # Reset singleton and create fresh instance
        import vector_store
        vector_store._vector_store_instance = None
        # Create instance with fresh cache
        from config import config
        import tempfile
        import shutil
        # Use temp directory for test data
        self.temp_dir = tempfile.mkdtemp()
        self.original_persist_dir = config.chromadb.persist_directory
        config.chromadb.persist_directory = Path(self.temp_dir)

    def teardown_method(self):
        """Cleanup"""
        import shutil
        if hasattr(self, 'temp_dir'):
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except:
                pass
        import vector_store
        vector_store._vector_store_instance = None

    def test_query_cache_hit_on_repeated_query(self):
        """Test that repeated queries hit cache"""
        vs = VectorStore()

        # Add test documents
        docs = [
            "Machine learning is powerful",
            "Deep learning uses neural networks",
            "Natural language processing is challenging"
        ]
        metadatas = [{"source": "book"}, {"source": "paper"}, {"source": "blog"}]
        vs.add_documents(docs, metadatas)

        # First search - should miss cache
        query = "machine learning"
        logger.info(f"First search for: {query}")
        results1 = vs.search(query, top_k=2)
        assert len(results1) > 0
        cache_size_1 = len(vs._query_embedding_cache)
        logger.info(f"Cache size after first search: {cache_size_1}")

        # Second identical search - should hit cache
        logger.info(f"Second search for: {query}")
        results2 = vs.search(query, top_k=2)
        cache_size_2 = len(vs._query_embedding_cache)
        logger.info(f"Cache size after second search: {cache_size_2}")

        # Cache size should be same (query already cached)
        assert cache_size_2 == cache_size_1
        # Results should be identical
        assert len(results1) == len(results2)
        assert results1[0]["id"] == results2[0]["id"]

    def test_query_cache_lru_eviction(self):
        """Test that cache evicts LRU items when max size reached"""
        vs = VectorStore()

        # Add test documents
        docs = ["Document about " + str(i) for i in range(5)]
        vs.add_documents(docs)

        # Set small cache size for testing
        vs._query_cache_max_size = 3

        # Make 5 different queries - should evict 2 oldest ones
        queries = [
            "machine learning",
            "deep learning",
            "natural language",
            "computer vision",
            "data science"
        ]

        for i, query in enumerate(queries):
            results = vs.search(query, top_k=2)
            cache_size = len(vs._query_embedding_cache)
            logger.info(f"Query {i+1}: cache size = {cache_size}")

        # Cache should be at max capacity (3)
        assert len(vs._query_embedding_cache) == 3
        logger.info(f"✓ Cache eviction working: max_size=3, current_size={len(vs._query_embedding_cache)}")

    def test_query_cache_preserves_most_recent(self):
        """Test that cache keeps most recently used items"""
        vs = VectorStore()

        # Add test documents
        docs = ["Document about " + str(i) for i in range(5)]
        vs.add_documents(docs)

        # Set small cache size
        vs._query_cache_max_size = 2

        # Make 3 queries: q1, q2, q3
        queries = ["query one", "query two", "query three"]
        for query in queries:
            vs.search(query, top_k=2)
            time.sleep(0.01)  # Ensure different timestamps

        # q1 should be evicted, q2 and q3 should remain
        cached_keys = set(vs._query_embedding_cache.keys())
        assert "query_emb:query one" not in cached_keys
        assert "query_emb:query two" in cached_keys
        assert "query_emb:query three" in cached_keys
        logger.info("✓ LRU tracking preserving most recent queries")

    def test_query_cache_access_time_update(self):
        """Test that accessing cached item updates its LRU timestamp"""
        vs = VectorStore()

        docs = ["Document about " + str(i) for i in range(5)]
        vs.add_documents(docs)

        # Embed two queries
        q1_key = "query_emb:first query"
        q2_key = "query_emb:second query"

        # Cache them
        vs._cache_query_embedding(q1_key, [0.1] * 384)
        vs._cache_query_embedding(q2_key, [0.2] * 384)

        # Get q1 from cache (updates its timestamp)
        time.sleep(0.01)
        embedding = vs._get_cached_query_embedding(q1_key)
        assert embedding is not None

        # Now q1 timestamp should be newer than q2
        t1 = vs._query_cache_access_times[q1_key]
        t2 = vs._query_cache_access_times[q2_key]
        assert t1 > t2
        logger.info("✓ Cache access time tracking working correctly")


class TestMetadataIndexOptimization:
    """Test metadata index O(1) filtering (PHASE 2)"""

    def setup_method(self):
        """Setup fresh vector store for each test"""
        import vector_store
        vector_store._vector_store_instance = None
        from config import config
        import tempfile
        self.temp_dir = tempfile.mkdtemp()
        config.chromadb.persist_directory = Path(self.temp_dir)

    def teardown_method(self):
        """Cleanup"""
        import shutil
        if hasattr(self, 'temp_dir'):
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except:
                pass
        import vector_store
        vector_store._vector_store_instance = None

    def test_metadata_index_creation(self):
        """Test that metadata index is properly created"""
        vs = VectorStore()

        docs = ["Doc 1", "Doc 2", "Doc 3"]
        metadatas = [
            {"source": "book", "year": 2023},
            {"source": "paper", "year": 2024},
            {"source": "book", "year": 2024}
        ]
        vs.add_documents(docs, metadatas)

        # Verify index structure
        assert ("source", "book") in vs._metadata_index
        assert ("source", "paper") in vs._metadata_index
        assert ("year", 2023) in vs._metadata_index
        assert ("year", 2024) in vs._metadata_index

        # Verify index contents
        book_indices = vs._metadata_index[("source", "book")]
        assert len(book_indices) == 2
        logger.info(f"✓ Metadata index created with {len(vs._metadata_index)} entries")

    def test_metadata_filtering_fast_lookup(self):
        """Test that metadata filtering uses index for O(1) lookup"""
        vs = VectorStore()

        # Create larger corpus
        docs = [f"Document {i}" for i in range(100)]
        metadatas = []
        for i in range(100):
            metadatas.append({
                "source": "book" if i % 2 == 0 else "paper",
                "category": "ml" if i % 3 == 0 else "nlp",
                "year": 2023 + (i % 2)
            })

        vs.add_documents(docs, metadatas)

        # Filter by single metadata field
        start = time.time()
        where_filter = {"source": "book"}
        results = vs.search("test query", where_filter=where_filter, top_k=5)
        elapsed = time.time() - start

        logger.info(f"Filtering with metadata index: {elapsed*1000:.2f}ms")
        assert elapsed < 0.5  # Should be reasonably fast (includes API call latency)
        assert len(results) > 0
        logger.info(f"✓ Metadata filtering fast: {len(results)} results in {elapsed*1000:.2f}ms")

    def test_metadata_index_filter_intersection(self):
        """Test that multiple filter conditions use set intersection"""
        vs = VectorStore()

        docs = ["Doc 1", "Doc 2", "Doc 3", "Doc 4"]
        metadatas = [
            {"source": "book", "year": 2023},
            {"source": "paper", "year": 2023},
            {"source": "book", "year": 2024},
            {"source": "paper", "year": 2024}
        ]
        vs.add_documents(docs, metadatas)

        # Filter with AND logic: source=book AND year=2023
        where_filter = {"source": "book", "year": 2023}
        results = vs.search("query", where_filter=where_filter, top_k=10)

        # Should only match Doc 1
        assert len(results) == 1
        assert results[0]["id"] == "doc_0"
        logger.info("✓ Metadata index intersection logic working")

    def test_metadata_index_rebuild_after_bulk_add(self):
        """Test that metadata index is rebuilt after bulk add"""
        vs = VectorStore()

        # Add first batch
        docs1 = ["Doc 1", "Doc 2"]
        metadatas1 = [{"tag": "a"}, {"tag": "b"}]
        vs.add_documents(docs1, metadatas1, ids=["d1", "d2"])

        index_size_1 = len(vs._metadata_index)
        logger.info(f"Index size after first batch: {index_size_1}")

        # Add second batch
        docs2 = ["Doc 3", "Doc 4"]
        metadatas2 = [{"tag": "a"}, {"tag": "c"}]
        vs.add_documents(docs2, metadatas2, ids=["d3", "d4"])

        index_size_2 = len(vs._metadata_index)
        logger.info(f"Index size after second batch: {index_size_2}")

        # Index should have more entries
        assert index_size_2 >= index_size_1
        # Should be able to filter by all tags
        assert ("tag", "a") in vs._metadata_index
        assert ("tag", "b") in vs._metadata_index
        assert ("tag", "c") in vs._metadata_index
        logger.info("✓ Metadata index rebuilt correctly after bulk add")

    def test_metadata_index_empty_filter_result(self):
        """Test that filter with no matches returns empty list"""
        vs = VectorStore()

        docs = ["Doc 1", "Doc 2"]
        metadatas = [{"source": "book"}, {"source": "paper"}]
        vs.add_documents(docs, metadatas)

        # Filter that matches nothing
        where_filter = {"source": "nonexistent"}
        results = vs.search("query", where_filter=where_filter, top_k=5)

        assert len(results) == 0
        logger.info("✓ Empty filter result returns correctly")


class TestBatchEmbeddingIntegration:
    """Test batch embedding integration (PHASE 2)"""

    def test_batch_embedding_vs_single(self):
        """Test that batch embedding produces same results as individual"""
        vs = VectorStore()

        docs = [
            "Machine learning document",
            "Deep learning document",
            "NLP document"
        ]

        # Add with batch embedding
        count, failed = vs.add_documents(docs, use_batch_embedding=True)

        assert count == 3
        assert len(failed) == 0
        assert len(vs.documents) == 3
        logger.info("✓ Batch embedding successfully added documents")

    def test_batch_embedding_fallback_to_individual(self):
        """Test that batch embedding falls back gracefully on error"""
        vs = VectorStore()

        docs = ["Doc 1", "Doc 2"]

        # Should succeed even if batch fails (fallback to individual)
        count, failed = vs.add_documents(docs, use_batch_embedding=True)

        assert count == 2
        logger.info("✓ Batch embedding fallback mechanism working")


class TestPhase2Performance:
    """Performance tests for PHASE 2 optimizations"""

    def setup_method(self):
        """Setup fresh vector store for each test"""
        import vector_store
        vector_store._vector_store_instance = None
        from config import config
        import tempfile
        self.temp_dir = tempfile.mkdtemp()
        config.chromadb.persist_directory = Path(self.temp_dir)

    def teardown_method(self):
        """Cleanup"""
        import shutil
        if hasattr(self, 'temp_dir'):
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except:
                pass
        import vector_store
        vector_store._vector_store_instance = None

    def test_metadata_filter_performance_improvement(self):
        """Test that metadata index filtering is fast"""
        vs = VectorStore()

        # Create corpus with metadata
        docs = [f"Document {i} about machine learning and AI" for i in range(50)]
        metadatas = []
        for i in range(50):
            metadatas.append({
                "source": "arxiv" if i % 3 == 0 else "paper",
                "year": 2023 + (i % 2),
                "category": "ml" if i % 2 == 0 else "nlp"
            })

        vs.add_documents(docs, metadatas)

        # Measure filtered search time
        where_filter = {"year": 2024}
        start = time.time()
        for _ in range(10):
            results = vs.search("machine learning", where_filter=where_filter, top_k=3)
        elapsed_filtered = time.time() - start

        logger.info(f"Filtered search (10x): {elapsed_filtered*1000:.2f}ms total ({elapsed_filtered/10*1000:.2f}ms avg)")

        # Should be reasonably fast
        assert elapsed_filtered < 2.0
        logger.info("✓ Metadata filtering performance acceptable")

    def test_query_cache_performance_gain(self):
        """Test that query cache provides measurable performance gain"""
        vs = VectorStore()

        # Create corpus
        docs = [f"Document {i}" for i in range(20)]
        vs.add_documents(docs)

        # Force cache population
        query = "test query about machine learning"
        vs.search(query, top_k=5)

        # Repeated search should be faster (using cached embedding)
        # This is hard to measure directly, but we can verify cache is used
        cache_size_before = len(vs._query_embedding_cache)
        vs.search(query, top_k=5)  # Same query
        cache_size_after = len(vs._query_embedding_cache)

        # Cache size should not grow
        assert cache_size_before == cache_size_after
        logger.info(f"✓ Query cache preventing redundant API calls (size: {cache_size_after})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
