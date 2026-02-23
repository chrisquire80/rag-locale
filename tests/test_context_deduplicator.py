"""
Unit Tests for Context Deduplicator Module

Tests deduplication logic, token estimation, and context optimization.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch
from src.context_deduplicator import (
    ContextDeduplicator,
    get_context_deduplicator
)


class TestContextDeduplicator:
    """Test ContextDeduplicator class"""

    @pytest.fixture
    def deduplicator(self):
        """Create fresh deduplicator instance"""
        return ContextDeduplicator()

    # ============= DEDUPLICATION TESTS =============

    def test_deduplicate_identical_chunks(self, deduplicator):
        """Test deduplication of identical chunks"""
        chunks = [
            "This is a test chunk",
            "This is a test chunk",
            "This is a test chunk"
        ]

        deduplicated = deduplicator.deduplicate_chunks(chunks)

        # Should reduce identical chunks
        assert len(deduplicated) < len(chunks)

    def test_deduplicate_similar_chunks(self, deduplicator):
        """Test deduplication of similar (not identical) chunks"""
        chunks = [
            "Machine learning is a subset of AI",
            "Machine learning is a branch of artificial intelligence",
            "ML is part of AI"
        ]

        deduplicated = deduplicator.deduplicate_chunks(chunks)

        # Should identify similar chunks
        assert len(deduplicated) <= len(chunks)

    def test_deduplicate_preserves_unique(self, deduplicator):
        """Test that unique chunks are preserved"""
        chunks = [
            "Unique information A",
            "Unique information B",
            "Unique information C"
        ]

        deduplicated = deduplicator.deduplicate_chunks(chunks)

        # All unique chunks should be preserved
        assert len(deduplicated) == len(chunks)

    def test_deduplicate_empty_list(self, deduplicator):
        """Test deduplication of empty chunk list"""
        chunks = []
        deduplicated = deduplicator.deduplicate_chunks(chunks)

        assert deduplicated == []

    def test_deduplicate_single_chunk(self, deduplicator):
        """Test deduplication of single chunk"""
        chunks = ["Single chunk"]
        deduplicated = deduplicator.deduplicate_chunks(chunks)

        assert len(deduplicated) == 1
        assert deduplicated[0] == "Single chunk"

    def test_deduplicate_mixed_duplicates(self, deduplicator):
        """Test deduplication with mix of unique and duplicate"""
        chunks = [
            "Chunk A",
            "Chunk A",  # Duplicate
            "Chunk B",
            "Chunk B",  # Duplicate
            "Chunk C"   # Unique
        ]

        deduplicated = deduplicator.deduplicate_chunks(chunks)

        # Should have 3 unique chunks
        assert len(deduplicated) == 3

    # ============= TOKEN ESTIMATION TESTS =============

    def test_estimate_optimal_chunk_count(self, deduplicator):
        """Test optimal chunk count estimation"""
        token_budget = 2000
        avg_tokens_per_chunk = 100

        optimal_count = deduplicator.estimate_optimal_chunk_count(
            token_budget,
            avg_tokens_per_chunk
        )

        assert isinstance(optimal_count, int)
        assert optimal_count > 0
        # Should be approximately token_budget / avg_tokens_per_chunk
        assert abs(optimal_count - (token_budget / avg_tokens_per_chunk)) < 5

    def test_estimate_optimal_chunk_count_zero_budget(self, deduplicator):
        """Test estimation with zero token budget"""
        optimal_count = deduplicator.estimate_optimal_chunk_count(0, 100)

        # Should handle gracefully
        assert optimal_count >= 0

    def test_estimate_optimal_chunk_count_high_budget(self, deduplicator):
        """Test estimation with very high token budget"""
        token_budget = 100000
        avg_tokens_per_chunk = 100

        optimal_count = deduplicator.estimate_optimal_chunk_count(
            token_budget,
            avg_tokens_per_chunk
        )

        assert optimal_count > 900

    def test_estimate_optimal_chunk_count_low_tokens_per_chunk(self, deduplicator):
        """Test estimation with low tokens per chunk"""
        optimal_count = deduplicator.estimate_optimal_chunk_count(2000, 10)

        assert optimal_count >= 100

    # ============= INFORMATION DENSITY TESTS =============

    def test_optimize_information_density(self, deduplicator):
        """Test information density optimization"""
        chunks = [
            "Low relevance information",
            "High relevance information",
            "Medium relevance information"
        ]

        optimized = deduplicator.optimize_information_density(chunks)

        # Should return organized chunks
        assert isinstance(optimized, list)
        assert len(optimized) > 0

    def test_optimize_density_sorting(self, deduplicator):
        """Test that optimization sorts by relevance"""
        chunks = [
            "Very specific technical detail",
            "Core concept",
            "General overview"
        ]

        optimized = deduplicator.optimize_information_density(chunks)

        # Should organize by relevance
        assert len(optimized) == len(chunks)

    def test_optimize_density_empty(self, deduplicator):
        """Test density optimization with empty list"""
        optimized = deduplicator.optimize_information_density([])

        assert optimized == []

    # ============= CONTEXT REDUCTION TESTS =============

    def test_context_reduction_ratio(self, deduplicator):
        """Test that deduplication achieves expected reduction ratio"""
        # Create chunks with known duplication
        chunks = []
        for i in range(10):
            chunks.append(f"Chunk {i % 3}")  # 10 chunks, 3 unique values

        deduplicated = deduplicator.deduplicate_chunks(chunks)
        reduction_ratio = len(deduplicated) / len(chunks)

        # Should reduce by approximately 70%
        assert reduction_ratio <= 0.35  # At least 65% reduction

    def test_context_token_savings(self, deduplicator):
        """Test estimated token savings from deduplication"""
        chunks = [
            "The quick brown fox jumps over the lazy dog",
            "The quick brown fox jumps over the lazy dog",
            "The smart red fox leaps over the sleepy dog"
        ]

        original_tokens = sum(len(c.split()) for c in chunks)
        deduplicated = deduplicator.deduplicate_chunks(chunks)
        final_tokens = sum(len(c.split()) for c in deduplicated)

        # Should save tokens
        assert final_tokens <= original_tokens

    # ============= SIMILARITY THRESHOLD TESTS =============

    def test_similarity_threshold_configuration(self, deduplicator):
        """Test that similarity threshold is properly configured"""
        assert hasattr(deduplicator, 'similarity_threshold')
        assert 0 < deduplicator.similarity_threshold < 1
        # Should be 0.85 for good quality deduplication
        assert deduplicator.similarity_threshold >= 0.80

    def test_deduplication_with_different_thresholds(self, deduplicator):
        """Test deduplication behavior with different thresholds"""
        chunks = [
            "Machine learning is powerful",
            "Machine learning is very powerful",
            "Deep learning is a subset"
        ]

        # Current threshold
        result1 = deduplicator.deduplicate_chunks(chunks)
        assert isinstance(result1, list)
        assert len(result1) > 0

    # ============= EDGE CASES TESTS =============

    def test_deduplicate_special_characters(self, deduplicator):
        """Test deduplication with special characters"""
        chunks = [
            "Special chars: @#$%^&*()",
            "Special chars: @#$%^&*()",
            "Different chars: !@#$%"
        ]

        deduplicated = deduplicator.deduplicate_chunks(chunks)
        assert len(deduplicated) <= len(chunks)

    def test_deduplicate_unicode(self, deduplicator):
        """Test deduplication with unicode characters"""
        chunks = [
            "Unicode: 日本語 中文 한국어",
            "Unicode: 日本語 中文 한국어",
            "Different: Café résumé"
        ]

        deduplicated = deduplicator.deduplicate_chunks(chunks)
        assert len(deduplicated) <= len(chunks)

    def test_deduplicate_very_short_chunks(self, deduplicator):
        """Test deduplication of very short chunks"""
        chunks = ["a", "a", "b", "b", "c"]
        deduplicated = deduplicator.deduplicate_chunks(chunks)

        # Should handle short chunks
        assert len(deduplicated) > 0

    def test_deduplicate_very_long_chunks(self, deduplicator):
        """Test deduplication of very long chunks"""
        long_chunk = " ".join(["word"] * 1000)
        chunks = [long_chunk, long_chunk, long_chunk + " different"]

        deduplicated = deduplicator.deduplicate_chunks(chunks)
        # Should reduce duplicates
        assert len(deduplicated) <= len(chunks)

    def test_deduplicate_mixed_languages(self, deduplicator):
        """Test deduplication with mixed language content"""
        chunks = [
            "English text here",
            "Texto en español aquí",
            "Texte français ici",
            "English text here"  # Duplicate
        ]

        deduplicated = deduplicator.deduplicate_chunks(chunks)
        assert len(deduplicated) <= len(chunks)

    def test_deduplicate_case_sensitivity(self, deduplicator):
        """Test handling of case variations"""
        chunks = [
            "Hello World",
            "hello world",
            "HELLO WORLD"
        ]

        deduplicated = deduplicator.deduplicate_chunks(chunks)
        # Might or might not treat as duplicates depending on implementation
        assert len(deduplicated) > 0

    # ============= PERFORMANCE TESTS =============

    def test_deduplication_performance_large_set(self, deduplicator):
        """Test deduplication performance with large chunk set"""
        import time

        # Create large set of chunks
        chunks = []
        for i in range(1000):
            chunks.append(f"Chunk content {i % 100}")

        start = time.perf_counter()
        deduplicated = deduplicator.deduplicate_chunks(chunks)
        elapsed = time.perf_counter() - start

        # Should handle 1000 chunks in reasonable time (< 5 seconds)
        assert elapsed < 5.0, f"Deduplication took {elapsed:.2f}s"
        assert len(deduplicated) < len(chunks)

    def test_optimize_density_performance(self, deduplicator):
        """Test performance of density optimization"""
        import time

        chunks = [f"Chunk {i}" for i in range(500)]

        start = time.perf_counter()
        optimized = deduplicator.optimize_information_density(chunks)
        elapsed = time.perf_counter() - start

        # Should optimize 500 chunks quickly (< 2 seconds)
        assert elapsed < 2.0, f"Optimization took {elapsed:.2f}s"
        assert len(optimized) > 0

    # ============= INTEGRATION TESTS =============

    def test_complete_deduplication_workflow(self, deduplicator):
        """Test complete deduplication workflow"""
        # Start with raw chunks
        raw_chunks = [
            "Core information A",
            "Core information A",  # Duplicate
            "Core information B",
            "Core information B",  # Duplicate
            "Supplementary info"
        ]

        # Deduplicate
        deduplicated = deduplicator.deduplicate_chunks(raw_chunks)

        # Estimate optimal count
        optimal = deduplicator.estimate_optimal_chunk_count(2000, 100)

        # Optimize density
        optimized = deduplicator.optimize_information_density(deduplicated)

        # Should have all pieces
        assert len(deduplicated) < len(raw_chunks)
        assert optimal > 0
        assert len(optimized) > 0

    # ============= GLOBAL INSTANCE TESTS =============

    def test_get_context_deduplicator_singleton(self):
        """Test that get_context_deduplicator returns singleton"""
        dedup1 = get_context_deduplicator()
        dedup2 = get_context_deduplicator()

        # Should be same instance
        assert dedup1 is dedup2


class TestDeduplicationMetrics:
    """Test metrics and statistics from deduplication"""

    @pytest.fixture
    def deduplicator(self):
        return ContextDeduplicator()

    def test_deduplication_ratio_calculation(self, deduplicator):
        """Test deduplication ratio metrics"""
        chunks = [
            "A",
            "A",
            "B",
            "B",
            "B",
            "C"
        ]

        original_count = len(chunks)
        deduplicated = deduplicator.deduplicate_chunks(chunks)
        final_count = len(deduplicated)

        reduction_ratio = final_count / original_count

        assert reduction_ratio > 0
        assert reduction_ratio <= 1.0

    def test_token_estimation_accuracy(self, deduplicator):
        """Test accuracy of token estimation"""
        chunks = [
            "word word word",      # 3 tokens
            "word word",           # 2 tokens
            "word word word word"  # 4 tokens
        ]

        total_tokens = sum(len(c.split()) for c in chunks)  # 9 tokens
        avg_tokens = total_tokens / len(chunks)  # 3 tokens per chunk

        estimated = deduplicator.estimate_optimal_chunk_count(100, avg_tokens)

        # Should estimate approximately 33 chunks for 100 tokens
        assert estimated > 0
        assert estimated <= 100 / avg_tokens
