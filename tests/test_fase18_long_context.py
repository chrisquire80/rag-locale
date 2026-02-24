"""
FASE 18: Long-Context Strategy - Tests
Tests for context window management and optimization
"""

import pytest
import logging
from src.context_window_manager import ContextWindowManager, TokenAllocation, get_context_window_manager

logger = logging.getLogger(__name__)


class TestContextWindowManager:
    """Test context window management"""

    def test_initialization(self):
        """Test ContextWindowManager initialization"""
        manager = ContextWindowManager()
        assert manager.max_tokens == 1_000_000
        assert manager.available_tokens == 1_000_000 - 500 - 200
        logger.info("✓ ContextWindowManager initialized correctly")

    def test_custom_capacity(self):
        """Test custom token capacity"""
        manager = ContextWindowManager(max_tokens=100_000)
        assert manager.max_tokens == 100_000
        logger.info("✓ Custom token capacity working")

    def test_estimate_tokens(self):
        """Test token estimation"""
        manager = ContextWindowManager()

        # Test various lengths
        test_cases = [
            ("", 0),
            ("hello", 7),  # ~1.3 tokens per word
            ("Hello world" * 10, 143),  # ~110 words * 1.3
        ]

        for text, expected_approx in test_cases:
            tokens = manager.estimate_tokens(text)
            assert tokens >= 0
            if expected_approx > 0:
                # Allow 20% variance in estimation
                assert abs(tokens - expected_approx) < expected_approx * 0.2
            logger.debug(f"  '{text[:30]}...' → {tokens} tokens")

        logger.info("✓ Token estimation working")

    def test_allocate_context_single_doc(self):
        """Test context allocation for single document"""
        manager = ContextWindowManager()

        doc = {
            'id': 'doc_1',
            'source': 'test.pdf',
            'content': 'This is a test document ' * 100,  # ~2400 words
            'type': 'text'
        }

        allocation = manager.allocate_context([doc], query="test query")

        assert 'allocations' in allocation
        assert 'total_tokens' in allocation
        assert 'utilization_percent' in allocation
        assert len(allocation['allocations']) == 1
        logger.info(f"✓ Single document allocation: {allocation['utilization_percent']:.1f}% utilized")

    def test_allocate_context_multiple_docs(self):
        """Test context allocation for multiple documents"""
        manager = ContextWindowManager()

        documents = [
            {
                'id': f'doc_{i}',
                'source': f'doc_{i}.pdf',
                'content': f'Document {i} content ' * 200,
                'type': 'text'
            }
            for i in range(5)
        ]

        allocation = manager.allocate_context(documents, query="test query")

        assert len(allocation['allocations']) <= 5
        assert allocation['total_tokens'] > 0
        assert allocation['utilization_percent'] < 100
        logger.info(f"✓ Multiple documents: {len(allocation['allocations'])} allocated, "
                   f"{allocation['utilization_percent']:.1f}% utilized")

    def test_allocation_respects_safety_buffer(self):
        """Test that allocation respects safety buffer"""
        manager = ContextWindowManager()
        manager.safety_buffer_percent = 0.1

        # Create very large document
        large_doc = {
            'id': 'large_doc',
            'source': 'large.pdf',
            'content': 'word ' * 500_000,  # Very large
            'type': 'text'
        }

        allocation = manager.allocate_context([large_doc], query="test")

        utilization = allocation['utilization_percent']
        # Should not exceed 90% due to safety buffer
        assert utilization <= 90
        logger.info(f"✓ Safety buffer respected: {utilization:.1f}% < 90%")

    def test_token_allocation_dataclass(self):
        """Test TokenAllocation dataclass"""
        alloc = TokenAllocation(
            document_id='doc_1',
            compression_level=1,
            estimated_tokens=5000,
            relevance_score=0.85
        )

        assert alloc.document_id == 'doc_1'
        assert alloc.compression_level == 1
        assert alloc.estimated_tokens == 5000
        assert alloc.relevance_score == 0.85
        logger.info("✓ TokenAllocation dataclass working")

    def test_utilization_metrics(self):
        """Test utilization metrics"""
        manager = ContextWindowManager()

        metrics = manager.get_utilization()

        assert 'total_capacity' in metrics
        assert 'available_for_context' in metrics
        assert 'utilization_percent' in metrics
        assert metrics['total_capacity'] == 1_000_000
        assert metrics['utilization_percent'] == 0.0  # No tokens used yet
        logger.info("✓ Utilization metrics working")

    def test_can_fit_tokens(self):
        """Test token capacity check"""
        manager = ContextWindowManager()
        manager.current_tokens = 900_000

        # Should fit small amount
        assert manager.can_fit_tokens(50_000)

        # Should not fit large amount
        assert not manager.can_fit_tokens(200_000)

        logger.info("✓ Token capacity checking working")

    def test_add_tokens(self):
        """Test adding tokens"""
        manager = ContextWindowManager()

        # Add some tokens
        assert manager.add_tokens(100_000, 'doc_1')
        assert manager.current_tokens == 100_000

        # Add more
        assert manager.add_tokens(100_000, 'doc_2')
        assert manager.current_tokens == 200_000

        # Should refuse to add too much
        manager.current_tokens = 900_000
        assert not manager.add_tokens(200_000, 'doc_3')

        logger.info("✓ Token addition working")

    def test_reset(self):
        """Test reset functionality"""
        manager = ContextWindowManager()
        manager.add_tokens(50_000, 'doc_1')
        manager.add_tokens(50_000, 'doc_2')

        assert manager.current_tokens == 100_000
        assert len(manager.allocated_documents) == 2

        manager.reset()

        assert manager.current_tokens == 0
        assert len(manager.allocated_documents) == 0
        logger.info("✓ Reset working")

    def test_singleton_instance(self):
        """Test singleton pattern"""
        manager1 = get_context_window_manager()
        manager2 = get_context_window_manager()

        assert manager1 is manager2
        logger.info("✓ Singleton pattern working")


class TestTokenEstimation:
    """Test token estimation accuracy"""

    def test_word_count_correlation(self):
        """Test that token count correlates with word count"""
        manager = ContextWindowManager()

        # More words should mean more tokens
        text_100 = "word " * 100
        text_1000 = "word " * 1000

        tokens_100 = manager.estimate_tokens(text_100)
        tokens_1000 = manager.estimate_tokens(text_1000)

        assert tokens_1000 > tokens_100
        # Should be roughly 10x (within 20% variance)
        ratio = tokens_1000 / tokens_100
        assert 8 < ratio < 12

        logger.info(f"✓ Token correlation: 100w→{tokens_100}t, 1000w→{tokens_1000}t (ratio: {ratio:.1f}x)")

    def test_empty_string(self):
        """Test empty string handling"""
        manager = ContextWindowManager()
        assert manager.estimate_tokens("") == 0
        assert manager.estimate_tokens("   ") >= 0
        logger.info("✓ Empty string handling working")


class TestContextOptimization:
    """Test context optimization"""

    def test_allocation_optimization(self):
        """Test allocation optimization"""
        manager = ContextWindowManager()

        docs = [
            {'id': f'doc_{i}', 'source': f'doc_{i}.pdf', 'content': f'content {i} ' * 100}
            for i in range(3)
        ]

        allocation = manager.allocate_context(docs, query="test")
        optimized = manager.optimize_allocation(allocation)

        # Should maintain same structure after optimization
        assert len(optimized['allocations']) == len(allocation['allocations'])
        logger.info("✓ Allocation optimization working")


class TestCapacityPlanning:
    """Test capacity planning for document sets"""

    def test_82_document_capacity(self):
        """Test capacity for RAG LOCALE's 82 documents"""
        manager = ContextWindowManager()

        # Simulate 82 documents of ~3500 tokens each
        documents = [
            {
                'id': f'doc_{i:02d}',
                'source': f'doc_{i:02d}.pdf',
                'content': 'word ' * 3500,  # ~4550 tokens
                'type': 'text'
            }
            for i in range(82)
        ]

        allocation = manager.allocate_context(documents, query="test query")

        # Should fit all or most documents
        assert len(allocation['allocations']) >= 70  # At least 85% of documents
        utilization = allocation['utilization_percent']
        assert utilization < 100  # Should not exceed capacity
        assert utilization > 20   # Should use reasonable amount

        logger.info(f"✓ 82 documents: {len(allocation['allocations'])} allocated, "
                   f"{utilization:.1f}% capacity used")

    def test_scalability(self):
        """Test scalability to larger document sets"""
        manager = ContextWindowManager()

        for num_docs in [10, 50, 100]:
            documents = [
                {
                    'id': f'doc_{i:03d}',
                    'source': f'doc_{i:03d}.pdf',
                    'content': 'word ' * 2000,
                    'type': 'text'
                }
                for i in range(num_docs)
            ]

            allocation = manager.allocate_context(documents, query="test")
            assert allocation['total_tokens'] > 0
            logger.debug(f"  {num_docs} docs: {allocation['utilization_percent']:.1f}% utilized")

        logger.info("✓ Scalability test passed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pytest.main([__file__, "-v"])
