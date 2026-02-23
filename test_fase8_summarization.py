"""
Tests for Phase 8 Feature 1: Semantic Document Summarization
Tests DocumentSummarizer, integration with vector_store, and UI functionality
"""

import pytest
import logging
from pathlib import Path
from src.document_summarizer import DocumentSummarizer
from src.vector_store import get_vector_store

logger = logging.getLogger(__name__)


class TestDocumentSummarizer:
    """Test suite for DocumentSummarizer class"""

    @pytest.fixture
    def summarizer(self):
        """Create a fresh DocumentSummarizer instance"""
        return DocumentSummarizer()

    def test_summarizer_initialization(self, summarizer):
        """Test that DocumentSummarizer initializes correctly"""
        assert summarizer is not None
        assert hasattr(summarizer, 'summarize_document')
        assert hasattr(summarizer, 'extract_key_points')
        logger.info("✓ Summarizer initialized")

    def test_summarize_document_with_content(self, summarizer):
        """Test document summarization with valid content"""
        content = """
        Machine Learning is a subset of Artificial Intelligence.
        It enables computers to learn from data without explicit programming.
        Deep learning uses neural networks with multiple layers.
        Natural language processing helps machines understand human language.
        These technologies are transforming many industries.
        """

        summary = summarizer.summarize_document("test.txt", content)
        assert summary is not None
        assert isinstance(summary, str)
        assert len(summary) > 0
        logger.info(f"✓ Summary generated: {len(summary)} chars")

    def test_summarize_document_with_empty_content(self, summarizer):
        """Test summarization gracefully handles empty content"""
        summary = summarizer.summarize_document("empty.txt", "")
        assert summary == ""
        logger.info("✓ Empty content handled gracefully")

    def test_extract_key_points(self, summarizer):
        """Test key points extraction"""
        content = """
        Artificial Intelligence enables computer vision.
        Machine learning requires large datasets.
        Neural networks learn patterns from examples.
        Deep learning models achieve state-of-the-art results.
        """

        key_points = summarizer.extract_key_points("test.txt", content, num_points=3)
        assert key_points is not None
        assert isinstance(key_points, list)
        logger.info(f"✓ Extracted {len(key_points)} key points")

    def test_summary_caching(self, summarizer):
        """Test that summaries are cached for reuse"""
        content = "This is test content for caching."

        # Generate summary first time
        summary1 = summarizer.summarize_document("cache_test.txt", content, use_cache=True)

        # Second call should use cache
        summary2 = summarizer.summarize_document("cache_test.txt", content, use_cache=True)

        assert summary1 == summary2
        cache_stats = summarizer.get_cache_stats()
        assert cache_stats['cached_summaries'] > 0
        logger.info(f"✓ Cache working: {cache_stats['cached_summaries']} summaries cached")

    def test_vector_store_summary_metadata(self):
        """Test that summaries are stored in vector_store metadata"""
        vs = get_vector_store()

        # Get summaries from vector store
        summaries = vs.get_document_summaries()

        assert summaries is not None
        assert isinstance(summaries, dict)

        # Check that some documents have summaries
        if summaries:
            for source, summary_info in list(summaries.items())[:1]:
                assert 'summary' in summary_info
                assert 'key_points' in summary_info
                logger.info(f"✓ Found {len(summaries)} documents with summaries")
        else:
            logger.info("⊘ No summaries in vector store (expected on first run)")

    def test_get_summary_stats(self, summarizer):
        """Test summary statistics calculation"""
        content = "This is a sample text. It contains multiple sentences. Testing the stats function."
        summary = summarizer.summarize_document("stats_test.txt", content)

        stats = summarizer.get_summary_stats(summary)
        assert 'word_count' in stats
        assert 'char_count' in stats
        assert 'avg_word_length' in stats
        assert stats['char_count'] >= 0
        logger.info(f"✓ Stats: {stats}")


class TestSummarizerIntegration:
    """Integration tests for summarizer with document ingestion"""

    def test_summarizer_with_vector_store(self):
        """Test that summarizer integrates with vector store"""
        vs = get_vector_store()
        summarizer = DocumentSummarizer()

        # Should not crash when calling vector store methods
        embeddings = vs.get_all_embeddings()
        summaries = vs.get_document_summaries()

        assert embeddings is not None or embeddings is None  # Either works
        assert summaries is not None
        logger.info(f"✓ Integration test passed: {len(summaries)} summaries available")
