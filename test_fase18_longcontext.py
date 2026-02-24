"""
FASE 18 - Long-Context Strategy Tests
Tests token counting, context assembly, hierarchy, and long-context query processing
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from long_context_optimizer import (
    LongContextOptimizer,
    ContextChunk
)
from document_hierarchy import (
    DocumentHierarchy,
    HierarchyNode,
    HierarchyLevel
)
from rag_engine_longcontext import (
    LongContextRAGEngine,
    LongContextRAGResponse
)


class TestLongContextOptimizer:
    """Tests for LongContextOptimizer"""

    def setup_method(self):
        """Setup for each test"""
        self.optimizer = LongContextOptimizer()

    def test_token_count_estimation_empty_string(self):
        """Test token counting for empty string"""
        count = self.optimizer.estimate_token_count("")
        assert count == 0

    def test_token_count_estimation_single_word(self):
        """Test token counting for single word"""
        count = self.optimizer.estimate_token_count("hello")
        assert count >= 1
        assert count <= 3

    def test_token_count_estimation_paragraph(self):
        """Test token counting for paragraph"""
        text = "This is a sample paragraph. " * 20
        count = self.optimizer.estimate_token_count(text)
        assert count > 0
        assert count < 500  # Should be less than 500 tokens

    def test_token_count_consistency(self):
        """Test that token counting is consistent"""
        text = "The same text should always have the same token count."
        count1 = self.optimizer.estimate_token_count(text)
        count2 = self.optimizer.estimate_token_count(text)
        assert count1 == count2

    def test_chunk_by_semantics_respects_max_size(self):
        """Test that semantic chunking respects max size"""
        text = ("This is a sentence. " * 100)
        target_size = 500

        chunks = self.optimizer.chunk_by_semantics(text, target_chunk_size=target_size)

        assert len(chunks) > 0
        # Most chunks should be under target (some may exceed slightly)
        for chunk in chunks[:-1]:
            assert chunk.token_count <= target_size * 1.2

    def test_chunk_by_semantics_preserves_content(self):
        """Test that chunking preserves all content"""
        text = "First sentence. Second sentence. Third sentence."
        chunks = self.optimizer.chunk_by_semantics(text, target_chunk_size=50)

        combined = " ".join([chunk.text for chunk in chunks])
        assert "First" in combined
        assert "Second" in combined
        assert "Third" in combined

    def test_prioritize_chunks_keyword_matching(self):
        """Test that prioritization matches keywords"""
        chunks = [
            ContextChunk(text="The machine learning model performs well.", start_pos=0, end_pos=40),
            ContextChunk(text="Python is a programming language.", start_pos=40, end_pos=73),
            ContextChunk(text="Machine learning is a subset of AI.", start_pos=73, end_pos=108),
        ]

        query = "machine learning"
        prioritized = self.optimizer.prioritize_chunks(query, chunks)

        # First two should have machine learning
        assert any("machine learning" in c.text.lower() for c in prioritized[:2])

    def test_prioritize_chunks_order_matters(self):
        """Test that prioritization produces consistent ordering"""
        chunks = [
            ContextChunk(text=f"Content {i}", start_pos=i*10, end_pos=(i+1)*10)
            for i in range(10)
        ]
        chunks[3].text = "machine learning model parameters"

        query = "machine learning"
        prioritized = self.optimizer.prioritize_chunks(query, chunks, top_k=5)

        # High-relevance chunk should be in results
        assert any("machine learning" in c.text.lower() for c in prioritized)

    def test_assemble_long_context_single_doc(self):
        """Test assembling context from single document"""
        docs = ["This is document one. " * 50]
        context = self.optimizer.assemble_long_context(docs)

        assert "document" in context
        assert len(context) > 0

    def test_assemble_long_context_multiple_docs(self):
        """Test assembling context from multiple documents"""
        docs = [
            "Document one content. " * 30,
            "Document two content. " * 30,
            "Document three content. " * 30,
        ]
        context = self.optimizer.assemble_long_context(docs)

        assert "Document one" in context or "one" in context
        assert "Document" in context

    def test_assemble_long_context_respects_token_limit(self):
        """Test that context assembly respects token limit"""
        docs = ["Content " * 1000]  # Very large doc
        max_tokens = 5000

        context = self.optimizer.assemble_long_context(docs, max_tokens=max_tokens)

        token_count = self.optimizer.estimate_token_count(context)
        assert token_count <= max_tokens * 1.1  # Allow 10% overflow

    def test_estimate_optimal_chunk_size(self):
        """Test optimal chunk size estimation"""
        size = self.optimizer.estimate_optimal_chunk_size(avg_query_results=5)

        assert size > 0
        assert size < self.optimizer.max_context_tokens

    def test_create_context_window_pipeline(self):
        """Test complete context window creation pipeline"""
        docs = [
            "Machine learning models are used for classification. " * 20,
            "Neural networks are a type of machine learning. " * 20,
            "Deep learning is a subset of neural networks. " * 20,
        ]
        query = "machine learning"

        result = self.optimizer.create_context_window(query, docs, top_k=3)

        assert "context" in result
        assert result["context_tokens"] > 0
        assert result["selected_docs"] > 0
        assert result["coverage_pct"] > 0
        assert result["coverage_pct"] <= 100


class TestDocumentHierarchy:
    """Tests for DocumentHierarchy"""

    def setup_method(self):
        """Setup for each test"""
        self.hierarchy = DocumentHierarchy()

    def test_organize_empty_documents(self):
        """Test organizing empty document list"""
        roots = self.hierarchy.organize_by_structure([])
        assert len(roots) == 0

    def test_organize_single_document(self):
        """Test organizing single document"""
        docs = [{
            "id": "doc1",
            "text": "# Main Title\n## Section\nContent here",
            "metadata": {}
        }]

        roots = self.hierarchy.organize_by_structure(docs)

        assert len(roots) == 1
        assert "doc1" in roots

    def test_organize_identifies_hierarchy_levels(self):
        """Test that hierarchy identifies structure levels"""
        docs = [{
            "id": "doc1",
            "text": "# Chapter 1\n## Section 1.1\n### Subsection 1.1.1\nContent",
            "metadata": {}
        }]

        roots = self.hierarchy.organize_by_structure(docs)
        root = roots["doc1"]

        # Check hierarchy was created
        assert root is not None
        assert root.level == HierarchyLevel.CHAPTER

    def test_hierarchy_indexing(self):
        """Test that nodes are properly indexed"""
        docs = [{
            "id": "doc1",
            "text": "# Chapter\n## Section\nContent",
            "metadata": {}
        }]

        self.hierarchy.organize_by_structure(docs)

        # Should have indexed nodes
        assert len(self.hierarchy.node_map) > 0
        # All nodes should be reachable
        for node_id, node in self.hierarchy.node_map.items():
            assert node.node_id == node_id

    def test_get_context_window_returns_string(self):
        """Test that context window returns string"""
        docs = [{
            "id": "doc1",
            "text": "# Title\n## Section\nContent text",
            "metadata": {}
        }]

        self.hierarchy.organize_by_structure(docs)
        context = self.hierarchy.get_context_window("doc1")

        assert isinstance(context, str)

    def test_traverse_hierarchy_returns_list(self):
        """Test that hierarchy traversal returns list"""
        docs = [{
            "id": "doc1",
            "text": "# Machine Learning\n## Algorithms\nContent about algorithms",
            "metadata": {}
        }]

        self.hierarchy.organize_by_structure(docs)
        results = self.hierarchy.traverse_hierarchy("machine learning")

        assert isinstance(results, list)

    def test_get_statistics(self):
        """Test getting hierarchy statistics"""
        docs = [
            {
                "id": "doc1",
                "text": "# Doc1\n## Section\nContent",
                "metadata": {}
            },
            {
                "id": "doc2",
                "text": "# Doc2\nContent",
                "metadata": {}
            }
        ]

        self.hierarchy.organize_by_structure(docs)
        stats = self.hierarchy.get_statistics()

        assert stats["total_documents"] == 2
        assert stats["total_nodes"] > 0


class TestLongContextRAGEngine:
    """Tests for LongContextRAGEngine"""

    def setup_method(self):
        """Setup for each test"""
        self.engine = LongContextRAGEngine()

    def test_engine_initialization(self):
        """Test engine initializes properly"""
        assert self.engine is not None
        assert self.engine.context_optimizer is not None
        assert self.engine.doc_hierarchy is not None

    def test_query_with_long_context_returns_response(self):
        """Test that query returns LongContextRAGResponse"""
        response = self.engine.query_with_long_context("test query")

        assert isinstance(response, LongContextRAGResponse)
        assert hasattr(response, 'answer')
        assert hasattr(response, 'context_token_count')

    def test_long_context_response_has_timing_info(self):
        """Test that response includes timing information"""
        response = self.engine.query_with_long_context("test query")

        assert hasattr(response, 'context_assembly_time_ms')
        assert hasattr(response, 'latency_breakdown')

    def test_context_stats_available(self):
        """Test that context statistics are available"""
        stats = self.engine.get_context_stats()

        assert "max_context_tokens" in stats
        assert stats["max_context_tokens"] > 0

    def test_retrieve_candidates_handles_empty_results(self):
        """Test that retrieval handles empty results gracefully"""
        # This should not raise an exception
        results = self.engine._retrieve_candidates("nonexistent query", top_k=5)
        assert isinstance(results, list)

    def test_prioritize_documents_empty_input(self):
        """Test document prioritization with empty input"""
        prioritized = self.engine._prioritize_documents("query", [])
        assert isinstance(prioritized, list)
        assert len(prioritized) == 0

    def test_assemble_optimal_context_empty_chunks(self):
        """Test context assembly with empty chunks"""
        context = self.engine._assemble_optimal_context([])
        assert context == ""

    def test_context_optimizer_integration(self):
        """Test integration with context optimizer"""
        assert self.engine.context_optimizer is not None
        assert hasattr(self.engine.context_optimizer, 'estimate_token_count')

    def test_document_hierarchy_integration(self):
        """Test integration with document hierarchy"""
        assert self.engine.doc_hierarchy is not None
        assert hasattr(self.engine.doc_hierarchy, 'organize_by_structure')

    def test_long_context_with_disabled_hierarchy(self):
        """Test query without hierarchy organization"""
        response = self.engine.query_with_long_context(
            "test query",
            use_hierarchy=False
        )

        assert isinstance(response, LongContextRAGResponse)
        assert response.document_hierarchy_used == False


class TestLongContextIntegration:
    """Integration tests for long-context system"""

    def test_full_pipeline_token_counting(self):
        """Test token counting across full pipeline"""
        optimizer = LongContextOptimizer()
        text = "Machine learning is powerful. " * 50

        # Chunk
        chunks = optimizer.chunk_by_semantics(text)
        chunk_tokens = sum(c.token_count for c in chunks)

        # Estimate for full text
        full_tokens = optimizer.estimate_token_count(text)

        # Should be similar
        assert abs(chunk_tokens - full_tokens) / max(chunk_tokens, full_tokens) < 0.3

    def test_full_pipeline_hierarchy_to_context(self):
        """Test full pipeline from hierarchy to context assembly"""
        hierarchy = DocumentHierarchy()
        optimizer = LongContextOptimizer()

        docs = [{
            "id": "doc1",
            "text": "# ML Guide\n## Algorithms\nContent about algorithms",
            "metadata": {"title": "ML"}
        }]

        hierarchy.organize_by_structure(docs)
        results = hierarchy.traverse_hierarchy("algorithms")

        assert len(results) > 0

    def test_performance_benchmark_chunking(self):
        """Benchmark semantic chunking performance"""
        optimizer = LongContextOptimizer()
        large_text = "Sentence. " * 1000

        import time
        start = time.time()
        chunks = optimizer.chunk_by_semantics(large_text, target_chunk_size=500)
        elapsed = time.time() - start

        # Should complete in reasonable time
        assert elapsed < 10  # 10 seconds max
        assert len(chunks) > 0

    def test_performance_benchmark_prioritization(self):
        """Benchmark chunk prioritization performance"""
        optimizer = LongContextOptimizer()
        chunks = [
            ContextChunk(
                text=f"Content about topic {i}",
                start_pos=i*30,
                end_pos=(i+1)*30
            )
            for i in range(100)
        ]

        import time
        start = time.time()
        prioritized = optimizer.prioritize_chunks("topic", chunks)
        elapsed = time.time() - start

        # Should complete quickly even with many chunks
        assert elapsed < 5
        assert len(prioritized) == len(chunks)

    def test_context_window_size_validation(self):
        """Test context window size stays within limits"""
        optimizer = LongContextOptimizer()
        docs = ["Large document content. " * 100] * 10

        result = optimizer.create_context_window("query", docs, top_k=5)

        assert result["context_tokens"] <= optimizer.max_context_tokens
        assert result["coverage_pct"] <= 100


# Performance and edge case tests
class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_very_long_document(self):
        """Test handling of very long documents"""
        optimizer = LongContextOptimizer()
        # Create 1MB+ of text
        text = "Word " * 200000

        chunks = optimizer.chunk_by_semantics(text, target_chunk_size=10000)
        assert len(chunks) > 0

    def test_special_characters_in_content(self):
        """Test handling of special characters"""
        optimizer = LongContextOptimizer()
        text = "Testing: special@chars! #hashtags $prices %percents ^carets"

        count = optimizer.estimate_token_count(text)
        assert count > 0

    def test_multilingual_content(self):
        """Test handling multilingual content"""
        optimizer = LongContextOptimizer()
        text = "English content. Contenu français. Contenido español."

        count = optimizer.estimate_token_count(text)
        assert count > 0

    def test_deeply_nested_hierarchy(self):
        """Test deeply nested document hierarchy"""
        hierarchy = DocumentHierarchy()
        docs = [{
            "id": "doc1",
            "text": "# L1\n## L2\n### L3\n#### L4\n##### L5\nContent",
            "metadata": {}
        }]

        roots = hierarchy.organize_by_structure(docs)
        assert len(roots) > 0

    def test_context_assembly_memory_efficiency(self):
        """Test that context assembly doesn't cause memory issues"""
        optimizer = LongContextOptimizer()
        # Create many small documents
        docs = ["Small doc content. " * 10 for _ in range(100)]

        context = optimizer.assemble_long_context(docs)
        # Should complete without memory error
        assert len(context) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
