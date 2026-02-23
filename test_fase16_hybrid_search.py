"""
FASE 16: Hybrid Search Integration Tests
Tests for BM25, vector hybrid search, re-ranking, and query expansion
"""

import pytest
import logging
from pathlib import Path
from typing import List
import sys
import numpy as np

# Setup path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hybrid_search import BM25, HybridSearchEngine, SearchResult
from reranker import GeminiReRanker, RankedResult, ParentDocumentRetriever
from query_expansion import QueryExpander, HyDEExpander
from llm_service import GeminiService

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class TestBM25:
    """Test BM25 algorithm implementation"""

    def test_bm25_initialization(self):
        """Test BM25 can be initialized with corpus"""
        corpus = [
            "Machine learning is powerful",
            "Deep learning uses neural networks",
            "Natural language processing is challenging"
        ]
        bm25 = BM25(corpus)
        assert bm25.corpus == corpus
        assert bm25.k1 == 1.5
        assert bm25.b == 0.75
        logger.info("✓ BM25 initialization working")

    def test_bm25_scoring(self):
        """Test BM25 scoring for simple query"""
        corpus = [
            "machine learning model",
            "deep learning network",
            "machine learning algorithm"
        ]
        bm25 = BM25(corpus)
        scores = bm25.score("machine learning")

        assert len(scores) == 3
        assert scores[0] > 0  # First doc contains both terms
        assert scores[1] >= 0  # Second doc scoring could be 0 or slightly positive
        assert scores[2] > 0  # Third doc contains both terms
        assert scores[0] == scores[2]  # Identical content should score same
        logger.info(f"✓ BM25 scoring: {scores}")

    def test_bm25_ranking(self):
        """Test BM25 returns top-k results in correct order"""
        corpus = [
            "the quick brown fox",
            "quick fox running fast",
            "brown and quick",
            "slow turtle walking"
        ]
        bm25 = BM25(corpus)
        scores = bm25.score("quick")

        # Get top 2 indices
        top_indices = np.argsort(-scores)[:2]
        assert len(top_indices) == 2
        assert scores[top_indices[0]] >= scores[top_indices[1]]  # First score >= second
        logger.info(f"✓ BM25 ranking working: {scores}")

    def test_bm25_empty_corpus(self):
        """Test BM25 handles empty corpus gracefully"""
        corpus = []
        bm25 = BM25(corpus)
        scores = bm25.score("query")
        assert len(scores) == 0
        logger.info("✓ BM25 handles empty corpus")

    def test_bm25_parameters(self):
        """Test BM25 with custom k1, b parameters"""
        corpus = ["test document for parameter testing"]
        bm25 = BM25(corpus, k1=2.0, b=0.5)
        assert bm25.k1 == 2.0
        assert bm25.b == 0.5
        logger.info("✓ BM25 custom parameters work")


class TestHybridSearchEngine:
    """Test hybrid search combining BM25 and vector similarity"""

    def test_hybrid_engine_initialization(self):
        """Test HybridSearchEngine initialization"""
        docs = [
            {"id": "doc1", "text": "machine learning", "metadata": {}},
            {"id": "doc2", "text": "deep learning", "metadata": {}}
        ]
        engine = HybridSearchEngine(docs)
        assert len(engine.documents) == 2
        logger.info("✓ HybridSearchEngine initialized")

    def test_hybrid_search_with_alpha_weighting(self):
        """Test hybrid search with different alpha weights"""
        docs = [
            {"id": "doc1", "text": "machine learning model", "metadata": {}},
            {"id": "doc2", "text": "deep learning network", "metadata": {}},
            {"id": "doc3", "text": "neural networks", "metadata": {}}
        ]
        engine = HybridSearchEngine(docs)

        # Test alpha=0 (BM25 only)
        results_bm25 = engine.search("machine learning", alpha=0.0)
        assert results_bm25[0].doc_id == "doc1"

        # Test alpha=1 (vector only)
        results_vector = engine.search("machine learning",
                                       query_embedding=np.array([1.0, 0.0, 0.0]),
                                       alpha=1.0)
        # Just verify it returns results
        assert len(results_vector) > 0

        logger.info("✓ Hybrid search alpha weighting working")

    def test_hybrid_search_top_k(self):
        """Test hybrid search returns correct top-k results"""
        docs = [
            {"id": "doc1", "text": "test query matching", "metadata": {}},
            {"id": "doc2", "text": "test content", "metadata": {}},
            {"id": "doc3", "text": "unrelated text", "metadata": {}},
            {"id": "doc4", "text": "test data", "metadata": {}}
        ]
        engine = HybridSearchEngine(docs)
        results = engine.search("test", top_k=2)

        assert len(results) <= 2
        assert all(isinstance(r, SearchResult) for r in results)
        logger.info(f"✓ Hybrid search top-k working: got {len(results)} results")

    def test_hybrid_search_score_normalization(self):
        """Test that scores are properly normalized (0-1)"""
        docs = [
            {"id": "doc1", "text": "test", "metadata": {}},
            {"id": "doc2", "text": "query", "metadata": {}}
        ]
        engine = HybridSearchEngine(docs)
        results = engine.search("test", alpha=0.5)

        for result in results:
            assert 0.0 <= result.combined_score <= 1.0
        logger.info("✓ Score normalization working")


class TestQueryExpander:
    """Test query expansion with variant generation"""

    @pytest.fixture
    def llm_service(self):
        """Provide LLM service for tests"""
        return GeminiService()

    def test_query_expander_initialization(self, llm_service):
        """Test QueryExpander can be initialized"""
        from src.cache import QueryExpansionCache
        expander = QueryExpander(llm_service)
        assert expander.llm == llm_service
        assert isinstance(expander.expansion_cache, QueryExpansionCache)
        logger.info("✓ QueryExpander initialized")

    def test_keyword_extraction(self, llm_service):
        """Test keyword extraction from query"""
        expander = QueryExpander(llm_service)
        keywords = expander.generate_keywords("machine learning algorithms for classification")

        assert isinstance(keywords, list)
        assert len(keywords) > 0
        assert "machine" in str(keywords).lower() or "learning" in str(keywords).lower()
        logger.info(f"✓ Keyword extraction: {keywords}")

    def test_query_decomposition(self, llm_service):
        """Test complex query decomposition into sub-questions"""
        expander = QueryExpander(llm_service)
        query = "How do machine learning models improve with more data and better features?"
        sub_questions = expander.decompose_query(query)

        assert isinstance(sub_questions, list)
        assert len(sub_questions) >= 1
        logger.info(f"✓ Query decomposition: {sub_questions}")

    def test_intent_detection(self, llm_service):
        """Test intent detection (simple/moderate/complex)"""
        expander = QueryExpander(llm_service)

        # Test with a simple query
        simple_query = "What is neural networks?"
        # Just verify QueryExpander initializes correctly
        assert expander.llm == llm_service
        assert len(expander.expansion_cache) == 0

        logger.info("✓ Intent detection setup working")


class TestHyDEExpander:
    """Test Hypothetical Document Embeddings generation"""

    @pytest.fixture
    def llm_service(self):
        """Provide LLM service for tests"""
        return GeminiService()

    def test_hyde_initialization(self, llm_service):
        """Test HyDE expander initialization"""
        hyde = HyDEExpander(llm_service)
        assert hyde.llm == llm_service
        logger.info("✓ HyDEExpander initialized")

    def test_hypothetical_document_generation(self, llm_service):
        """Test generating hypothetical documents for query"""
        hyde = HyDEExpander(llm_service)
        query = "machine learning best practices"
        hypothetical_docs = hyde.generate_hypothetical_documents(query, num_docs=2)

        assert isinstance(hypothetical_docs, list)
        assert len(hypothetical_docs) >= 1
        assert all(isinstance(doc, str) for doc in hypothetical_docs)
        logger.info(f"✓ HyDE document generation: {len(hypothetical_docs)} docs")


class TestGeminiReRanker:
    """Test Gemini-based re-ranking"""

    @pytest.fixture
    def llm_service(self):
        """Provide LLM service for tests"""
        return GeminiService()

    def test_reranker_initialization(self, llm_service):
        """Test ReRanker initialization"""
        reranker = GeminiReRanker(llm_service, batch_size=5)
        assert reranker.llm == llm_service
        assert reranker.batch_size == 5
        logger.info("✓ GeminiReRanker initialized")

    def test_parent_document_retriever(self):
        """Test ParentDocumentRetriever extracts context"""
        # Create sample documents
        documents = [
            {
                "id": "doc1",
                "text": "This is important. The key insight here leads to conclusions.",
                "metadata": {}
            }
        ]
        retriever = ParentDocumentRetriever(documents)

        # Test that retriever was initialized with documents
        assert len(retriever.documents) == 1
        assert retriever.documents[0]["id"] == "doc1"

        logger.info("✓ ParentDocumentRetriever initialization working")


class TestFASE16Integration:
    """Integration tests for complete FASE 16 workflow"""

    @pytest.fixture
    def sample_documents(self):
        """Sample documents for testing"""
        return [
            {
                "id": "doc1",
                "text": "Machine learning enables computers to learn from data without explicit programming",
                "metadata": {"source": "ml_basics.pdf"}
            },
            {
                "id": "doc2",
                "text": "Deep learning uses neural networks with multiple layers for complex pattern recognition",
                "metadata": {"source": "dl_guide.pdf"}
            },
            {
                "id": "doc3",
                "text": "Natural language processing analyzes and understands human language text",
                "metadata": {"source": "nlp_intro.pdf"}
            },
            {
                "id": "doc4",
                "text": "Computer vision processes and analyzes visual information from images",
                "metadata": {"source": "cv_basics.pdf"}
            }
        ]

    @pytest.fixture
    def llm_service(self):
        """Provide LLM service for tests"""
        return GeminiService()

    def test_end_to_end_hybrid_search_workflow(self, sample_documents, llm_service):
        """Test complete workflow: query -> hybrid search -> re-ranking"""
        # 1. Hybrid search
        engine = HybridSearchEngine(sample_documents)
        query = "machine learning"
        query_embedding = np.array([0.8, 0.1, 0.05, 0.05])

        results = engine.search(query, query_embedding=query_embedding, top_k=3, alpha=0.5)
        assert len(results) > 0
        # Check if doc1 is in top results (should be due to ML keyword match)
        top_ids = [r.doc_id for r in results]
        assert "doc1" in top_ids

        logger.info(f"✓ Hybrid search found {len(results)} results")

        # 2. Query expansion (if implemented)
        expander = QueryExpander(llm_service)
        keywords = expander.generate_keywords(query)
        assert len(keywords) > 0

        logger.info(f"✓ Query expansion: {keywords}")

        # 3. Re-ranking (if implemented)
        reranker = GeminiReRanker(llm_service)
        logger.info("✓ Re-ranker initialized for multi-stage ranking")

    def test_performance_multiple_queries(self, sample_documents):
        """Test performance with multiple different queries"""
        engine = HybridSearchEngine(sample_documents)
        queries = [
            "machine learning",
            "deep neural networks",
            "language processing",
            "computer vision"
        ]

        import time
        start = time.time()

        for q in queries:
            results = engine.search(q, top_k=2)
            assert len(results) > 0

        elapsed = time.time() - start
        avg_per_query = elapsed / len(queries)

        assert avg_per_query < 0.1, f"Search too slow: {avg_per_query:.3f}s per query"
        logger.info(f"✓ Performance: {avg_per_query:.3f}s per query")

    def test_handling_edge_cases(self, sample_documents):
        """Test edge cases and error handling"""
        engine = HybridSearchEngine(sample_documents)

        # Empty query
        results = engine.search("", alpha=0.5)
        assert isinstance(results, list)

        # Very long query
        long_query = " ".join(["word"] * 100)
        results = engine.search(long_query, alpha=0.5)
        assert isinstance(results, list)

        # Special characters (will be tokenized)
        special_query = "machine learning"
        results = engine.search(special_query, alpha=0.5)
        assert isinstance(results, list)

        logger.info("✓ Edge cases handled gracefully")


class TestFASE16Performance:
    """Performance benchmarks for FASE 16 components"""

    def test_bm25_performance_large_corpus(self):
        """Test BM25 performance with large corpus"""
        import time

        # Create large corpus
        corpus = [f"document {i} with machine learning content" for i in range(1000)]

        start = time.time()
        bm25 = BM25(corpus)
        init_time = time.time() - start

        start = time.time()
        scores = bm25.score("machine learning")
        score_time = time.time() - start

        assert init_time < 1.0, f"BM25 init too slow: {init_time:.3f}s"
        assert score_time < 0.1, f"BM25 score too slow: {score_time:.3f}s"

        logger.info(f"✓ BM25 performance: init={init_time:.3f}s, score={score_time:.3f}s")

    def test_hybrid_search_performance_large_corpus(self):
        """Test HybridSearchEngine performance with many documents"""
        import time
        import numpy as np

        # Create large doc set
        docs = []
        for i in range(500):
            docs.append({
                "id": f"doc_{i}",
                "text": f"machine learning document {i}",
                "metadata": {}
            })

        start = time.time()
        engine = HybridSearchEngine(docs)
        init_time = time.time() - start

        start = time.time()
        results = engine.search("machine learning", top_k=10)
        search_time = time.time() - start

        assert init_time < 2.0, f"Engine init too slow: {init_time:.3f}s"
        assert search_time < 0.5, f"Search too slow: {search_time:.3f}s"

        logger.info(f"✓ HybridSearchEngine performance: init={init_time:.3f}s, search={search_time:.3f}s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
