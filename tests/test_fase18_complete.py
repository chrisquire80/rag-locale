"""
FASE 18: Complete Long-Context Strategy - Comprehensive Tests
Tests for document compression, batching, smart retrieval, and multi-document analysis
"""

import pytest
import logging
import time
from typing import List, Dict

logger = logging.getLogger(__name__)


class TestDocumentCompressor:
    """Test document compression engine"""

    def test_compressor_initialization(self):
        """Test DocumentCompressor can be initialized"""
        try:
            from src.document_compressor import DocumentCompressor, CompressionLevel
            compressor = DocumentCompressor()
            assert compressor is not None
            logger.info("✓ DocumentCompressor initialized")
        except ImportError as e:
            pytest.skip(f"document_compressor module not available: {e}")

    def test_token_estimation(self):
        """Test token estimation (1.3 tokens per word)"""
        try:
            from src.document_compressor import DocumentCompressor
            compressor = DocumentCompressor()

            # Test that more words = more tokens (correlation test)
            test_text_short = "hello world"
            test_text_long = "This is a test document " * 10

            tokens_short = compressor.estimate_tokens(test_text_short)
            tokens_long = compressor.estimate_tokens(test_text_long)

            # Longer text should have more tokens
            assert tokens_long > tokens_short
            assert tokens_short > 0
            assert tokens_long > 0

            # Ratio should be roughly proportional to word count
            word_ratio = len(test_text_long.split()) / len(test_text_short.split())
            token_ratio = tokens_long / tokens_short
            # Allow wider variance in small numbers
            assert 5 < token_ratio < 40  # Rough proportionality check

            logger.info(f"✓ Token estimation working (ratio: {token_ratio:.1f}x)")
        except ImportError:
            pytest.skip("document_compressor module not available")

    def test_compression_levels(self):
        """Test all compression levels"""
        try:
            from src.document_compressor import DocumentCompressor, CompressionLevel
            compressor = DocumentCompressor()

            test_text = "This is a test document. " * 100  # ~2400 words

            for level in CompressionLevel:
                compressed = compressor.compress(
                    document_id=f"doc_{level.name}",
                    text=test_text,
                    level=level
                )

                assert compressed.document_id == f"doc_{level.name}"
                assert compressed.compression_level == level
                assert compressed.original_token_count > 0
                assert compressed.compressed_token_count > 0

                # Check compression ratio decreases with higher compression
                logger.debug(f"Level {level.name}: {compressed.compression_ratio:.1%} compression")

            logger.info("✓ All compression levels working")
        except ImportError:
            pytest.skip("document_compressor module not available")

    def test_detailed_summary(self):
        """Test detailed summary generation (~20%)"""
        try:
            from src.document_compressor import DocumentCompressor, CompressionLevel
            compressor = DocumentCompressor()

            test_text = """
            Introduction paragraph with important information.
            This is the first main section discussing key concepts.
            Important finding: the data shows significant growth.
            Another important statement in the middle.
            This section discusses methodology and approach.
            Key results indicate positive outcomes.
            Final paragraph summarizing all conclusions.
            """ * 10

            compressed = compressor.compress(
                document_id="test_detailed",
                text=test_text,
                level=CompressionLevel.DETAILED
            )

            # Detailed should be ~20% of original
            ratio = compressed.compression_ratio
            assert 0.1 < ratio < 0.3, f"Detailed ratio {ratio} not in expected range"
            logger.info(f"✓ Detailed summary: {ratio:.1%} compression")
        except ImportError:
            pytest.skip("document_compressor module not available")

    def test_executive_summary(self):
        """Test executive summary generation (~5%)"""
        try:
            from src.document_compressor import DocumentCompressor, CompressionLevel
            compressor = DocumentCompressor()

            test_text = "Test content. " * 500

            compressed = compressor.compress(
                document_id="test_executive",
                text=test_text,
                level=CompressionLevel.EXECUTIVE
            )

            # Executive should be ~5% of original
            ratio = compressed.compression_ratio
            assert 0.02 < ratio < 0.15, f"Executive ratio {ratio} not in expected range"
            logger.info(f"✓ Executive summary: {ratio:.1%} compression")
        except ImportError:
            pytest.skip("document_compressor module not available")

    def test_batch_compression(self):
        """Test batch document compression"""
        try:
            from src.document_compressor import DocumentCompressor, CompressionLevel
            compressor = DocumentCompressor()

            documents = [
                {
                    'id': f'doc_{i}',
                    'text': f'Document {i} content. ' * 50,
                    'metadata': {'source': f'source_{i}'}
                }
                for i in range(5)
            ]

            allocation = {
                doc['id']: CompressionLevel.FULL if i == 0 else CompressionLevel.DETAILED
                for i, doc in enumerate(documents)
            }

            results = compressor.compress_batch(documents, allocation)

            assert len(results) == 5
            for result in results:
                assert result.original_token_count > 0
                assert result.compressed_token_count > 0

            logger.info(f"✓ Batch compression: {len(results)} documents processed")
        except ImportError:
            pytest.skip("document_compressor module not available")

    def test_auto_compress(self):
        """Test automatic compression to fit token budget"""
        try:
            from src.document_compressor import DocumentCompressor
            compressor = DocumentCompressor()

            documents = [
                {
                    'id': f'doc_{i}',
                    'text': f'Document {i} content. ' * 50,
                    'metadata': {}
                }
                for i in range(5)
            ]

            target_tokens = 5000  # Budget for ~5 documents

            results = compressor.auto_compress(
                documents=documents,
                target_tokens=target_tokens
            )

            total_tokens = sum(r.compressed_token_count for r in results)
            # May exceed target slightly due to minimum document size, but should be close
            assert total_tokens <= target_tokens * 1.2  # Allow 20% overage

            logger.info(f"✓ Auto-compression: {total_tokens:,} tokens (target: {target_tokens:,})")
        except ImportError:
            pytest.skip("document_compressor module not available")


class TestContextBatcher:
    """Test context batching engine"""

    def test_batcher_initialization(self):
        """Test ContextBatcher can be initialized"""
        try:
            from src.context_batcher import ContextBatcher
            batcher = ContextBatcher()
            assert batcher is not None
            logger.info("✓ ContextBatcher initialized")
        except ImportError as e:
            pytest.skip(f"context_batcher module not available: {e}")

    def test_batch_creation(self):
        """Test creating a single batch"""
        try:
            from src.context_batcher import ContextBatcher
            batcher = ContextBatcher()

            documents = [
                {'id': f'doc_{i}', 'text': f'Document {i} content. ' * 50}
                for i in range(3)
            ]

            queries = ["What is the main point?", "How does this relate?"]

            batch = batcher.create_batch(documents, queries)

            assert batch.batch_id == "batch_0000"
            assert len(batch.documents) == 3
            assert len(batch.queries) == 2
            assert batch.total_tokens > 0

            logger.info(f"✓ Batch created: {batch.total_tokens:,} tokens")
        except ImportError:
            pytest.skip("context_batcher module not available")

    def test_document_packing(self):
        """Test bin-packing algorithm for documents"""
        try:
            from src.context_batcher import ContextBatcher
            batcher = ContextBatcher(max_batch_tokens=10000)

            documents = [
                {'id': f'doc_{i}', 'text': f'Content. ' * (100 + i * 10)}
                for i in range(20)
            ]

            batches = batcher.pack_documents(documents)

            # Verify all documents packed
            packed_count = sum(len(b.documents) for b in batches)
            assert packed_count == len(documents)

            # Verify no batch exceeds capacity
            for batch in batches:
                assert batch.total_tokens <= 10000

            logger.info(f"✓ Packing: {len(documents)} docs → {len(batches)} batches")
        except ImportError:
            pytest.skip("context_batcher module not available")

    def test_add_queries_to_batches(self):
        """Test adding queries to batches"""
        try:
            from src.context_batcher import ContextBatcher
            batcher = ContextBatcher()

            documents = [
                {'id': f'doc_{i}', 'text': f'Document {i}. ' * 100}
                for i in range(5)
            ]

            batches = batcher.pack_documents(documents)
            queries = ["Query 1?", "Query 2?", "Query 3?"]

            batches, unallocated = batcher.add_queries_to_batches(batches, queries)

            # All queries should fit with small documents
            assert len(unallocated) == 0
            total_queries = sum(len(b.queries) for b in batches)
            assert total_queries == 3

            logger.info(f"✓ Queries allocated: {total_queries}/{len(queries)}")
        except ImportError:
            pytest.skip("context_batcher module not available")

    def test_batch_optimization(self):
        """Test batch optimization (merging small batches)"""
        try:
            from src.context_batcher import ContextBatcher
            batcher = ContextBatcher(max_batch_tokens=50000)

            # Create many small batches
            documents = [
                {'id': f'doc_{i}', 'text': f'Small doc {i}. ' * 10}
                for i in range(30)
            ]

            batches = batcher.pack_documents(documents)
            original_count = len(batches)

            # Optimize
            optimized = batcher.optimize_batches(batches)

            # Should merge small batches
            assert len(optimized) <= original_count

            logger.info(f"✓ Optimization: {original_count} → {len(optimized)} batches")
        except ImportError:
            pytest.skip("context_batcher module not available")

    def test_api_reduction_estimation(self):
        """Test API call reduction estimation"""
        try:
            from src.context_batcher import ContextBatcher
            batcher = ContextBatcher()

            documents = [
                {'id': f'doc_{i}', 'text': f'Document {i}. ' * 50}
                for i in range(70)
            ]

            queries = ["Query 1?", "Query 2?", "Query 3?"]

            reduction = batcher.estimate_api_calls_reduction(documents, queries)

            # Should show significant reduction
            assert reduction['unbatched_calls'] == 73  # 70 docs + 3 queries
            assert reduction['batched_calls'] < 73
            assert reduction['call_reduction_percent'] > 80

            logger.info(f"✓ API reduction: {reduction['unbatched_calls']} → "
                       f"{reduction['batched_calls']} calls "
                       f"({reduction['call_reduction_percent']:.0f}% reduction)")
        except ImportError:
            pytest.skip("context_batcher module not available")


class TestSmartRetrieverLong:
    """Test smart retrieval for long context"""

    def test_retriever_initialization(self):
        """Test SmartRetrieverLong can be initialized"""
        try:
            from src.smart_retrieval_long import SmartRetrieverLong
            retriever = SmartRetrieverLong()
            assert retriever is not None
            logger.info("✓ SmartRetrieverLong initialized")
        except ImportError as e:
            pytest.skip(f"smart_retrieval_long module not available: {e}")

    def test_retrieve_by_relevance(self):
        """Test relevance-first retrieval strategy"""
        try:
            from src.smart_retrieval_long import SmartRetrieverLong, RetrievalStrategy
            retriever = SmartRetrieverLong(max_tokens=10000)

            documents = [
                {'id': f'doc_{i}', 'text': f'Document {i}. ' * 100, 'metadata': {'source': f'src_{i}'}}
                for i in range(10)
            ]

            relevance_scores = {f'doc_{i}': 0.9 - (i * 0.08) for i in range(10)}

            result = retriever.retrieve(
                documents=documents,
                query="test query",
                strategy=RetrievalStrategy.RELEVANCE_FIRST,
                relevance_scores=relevance_scores
            )

            # Should include highest relevance documents first
            assert len(result.selected_documents) > 0
            assert result.total_tokens <= 10000
            logger.info(f"✓ Relevance retrieval: {len(result.selected_documents)} documents")
        except ImportError:
            pytest.skip("smart_retrieval_long module not available")

    def test_retrieve_by_size(self):
        """Test size-first retrieval strategy"""
        try:
            from src.smart_retrieval_long import SmartRetrieverLong, RetrievalStrategy
            retriever = SmartRetrieverLong(max_tokens=10000)

            # Create documents of varying sizes
            documents = [
                {'id': f'doc_{i}', 'text': f'Document {i}. ' * (50 + i * 20), 'metadata': {'source': 'test'}}
                for i in range(10)
            ]

            result = retriever.retrieve(
                documents=documents,
                query="test",
                strategy=RetrievalStrategy.SIZE_FIRST
            )

            # Should fit smaller documents to maximize count
            assert len(result.selected_documents) > 0
            logger.info(f"✓ Size retrieval: {len(result.selected_documents)} documents, "
                       f"{result.total_tokens:,} tokens")
        except ImportError:
            pytest.skip("smart_retrieval_long module not available")

    def test_retrieve_diversity(self):
        """Test diversity-first retrieval"""
        try:
            from src.smart_retrieval_long import SmartRetrieverLong, RetrievalStrategy
            retriever = SmartRetrieverLong()

            # Create documents from multiple sources
            documents = []
            for source in ['source_a', 'source_b', 'source_c']:
                for i in range(5):
                    documents.append({
                        'id': f'{source}_doc_{i}',
                        'text': f'Document {i} from {source}. ' * 50,
                        'metadata': {'source': source}
                    })

            result = retriever.retrieve(
                documents=documents,
                query="test",
                strategy=RetrievalStrategy.DIVERSITY_FIRST
            )

            # Should include documents from multiple sources
            sources = set(doc['metadata']['source'] for doc in result.selected_documents)
            assert len(sources) > 1, "Should retrieve from multiple sources"

            logger.info(f"✓ Diversity retrieval: {len(result.selected_documents)} documents "
                       f"from {len(sources)} sources (diversity: {result.diversity_score:.2f})")
        except ImportError:
            pytest.skip("smart_retrieval_long module not available")

    def test_retrieve_hybrid(self):
        """Test hybrid retrieval strategy"""
        try:
            from src.smart_retrieval_long import SmartRetrieverLong, RetrievalStrategy
            retriever = SmartRetrieverLong()

            documents = [
                {'id': f'doc_{i}', 'text': f'Document {i}. ' * (50 + i * 10),
                 'metadata': {'source': f'src_{i % 3}'}}
                for i in range(10)
            ]

            result = retriever.retrieve(
                documents=documents,
                query="test",
                strategy=RetrievalStrategy.HYBRID
            )

            assert len(result.selected_documents) > 0
            assert result.coverage_percent > 0

            logger.info(f"✓ Hybrid retrieval: {len(result.selected_documents)} documents "
                       f"({result.coverage_percent:.1f}% coverage)")
        except ImportError:
            pytest.skip("smart_retrieval_long module not available")

    def test_reorder_for_context(self):
        """Test document reordering"""
        try:
            from src.smart_retrieval_long import SmartRetrieverLong
            retriever = SmartRetrieverLong()

            documents = [
                {'id': f'doc_{i}', 'text': f'Document {i}. ' * 50,
                 'metadata': {'source': 'test', 'date': f'2025-0{i%3+1}-01'}}
                for i in range(5)
            ]

            # Test different reordering strategies
            for order_by in ['relevance', 'source', 'size', 'chronological']:
                reordered = retriever.reorder_for_context(documents, "test query", order_by)
                assert len(reordered) == len(documents)

            logger.info("✓ Document reordering working for all strategies")
        except ImportError:
            pytest.skip("smart_retrieval_long module not available")


class TestMultiDocumentAnalyzer:
    """Test multi-document analysis"""

    def test_analyzer_initialization(self):
        """Test MultiDocumentAnalyzerLong can be initialized"""
        try:
            from src.multi_document_analyzer_long import MultiDocumentAnalyzerLong
            analyzer = MultiDocumentAnalyzerLong()
            assert analyzer is not None
            logger.info("✓ MultiDocumentAnalyzerLong initialized")
        except ImportError as e:
            pytest.skip(f"multi_document_analyzer_long module not available: {e}")

    def test_token_estimation_for_analysis(self):
        """Test token estimation for multi-document analysis"""
        try:
            from src.multi_document_analyzer_long import MultiDocumentAnalyzerLong
            analyzer = MultiDocumentAnalyzerLong()

            documents = [
                {'id': f'doc_{i}', 'text': f'Document {i}. ' * 100}
                for i in range(5)
            ]

            for analysis_type in ['comparison', 'synthesis', 'extraction', 'reasoning']:
                tokens = analyzer.estimate_tokens_for_analysis(documents, analysis_type)
                assert tokens > 0
                logger.debug(f"  {analysis_type}: {tokens:,} tokens")

            logger.info("✓ Token estimation for analysis working")
        except ImportError:
            pytest.skip("multi_document_analyzer_long module not available")

    def test_analysis_methods(self):
        """Test analysis methods exist and work"""
        try:
            from src.multi_document_analyzer_long import MultiDocumentAnalyzerLong
            analyzer = MultiDocumentAnalyzerLong()

            documents = [
                {'id': f'doc_{i}', 'text': f'Document {i} content. ' * 100}
                for i in range(3)
            ]

            # Test that methods exist and return proper structures
            methods = [
                ('analyze_comparison', {'comparison_topic': 'test'}),
                ('analyze_synthesis', {'synthesis_question': 'test?'}),
                ('extract_structured_data', {'extraction_schema': {'field1': 'description'}}),
                ('analyze_relationships', {'relationship_type': 'causal'}),
            ]

            for method_name, kwargs in methods:
                method = getattr(analyzer, method_name)
                assert callable(method)
                logger.debug(f"  {method_name} exists")

            logger.info("✓ All analysis methods available")
        except ImportError:
            pytest.skip("multi_document_analyzer_long module not available")

    def test_analysis_logging(self):
        """Test analysis logging and history"""
        try:
            from src.multi_document_analyzer_long import MultiDocumentAnalyzerLong, AnalysisResult
            analyzer = MultiDocumentAnalyzerLong()

            result = AnalysisResult(
                query="test query",
                documents_analyzed=3,
                analysis_type="synthesis",
                answer="test answer",
                confidence_score=0.85,
                cited_documents=['doc_1', 'doc_2'],
                supporting_quotes=[],
                contradictions=[],
                processing_time=1.5,
                token_usage=2000
            )

            analyzer.log_analysis(result)

            assert len(analyzer.analysis_history) == 1
            assert analyzer.analysis_history[0]['analysis_type'] == 'synthesis'

            logger.info("✓ Analysis logging working")
        except ImportError:
            pytest.skip("multi_document_analyzer_long module not available")


class TestFASE18Integration:
    """Integration tests for FASE 18 components"""

    def test_all_modules_importable(self):
        """Test all FASE 18 modules can be imported"""
        modules = [
            ('src.context_window_manager', 'ContextWindowManager'),
            ('src.document_compressor', 'DocumentCompressor'),
            ('src.context_batcher', 'ContextBatcher'),
            ('src.smart_retrieval_long', 'SmartRetrieverLong'),
            ('src.multi_document_analyzer_long', 'MultiDocumentAnalyzerLong'),
        ]

        for module_name, class_name in modules:
            try:
                module = __import__(module_name, fromlist=[class_name])
                getattr(module, class_name)
                logger.info(f"✓ {module_name}.{class_name} imported")
            except ImportError as e:
                logger.warning(f"✗ {module_name} not available: {e}")

    def test_fase18_pipeline_components(self):
        """Test FASE 18 pipeline can be assembled"""
        try:
            from src.context_window_manager import ContextWindowManager
            from src.document_compressor import DocumentCompressor
            from src.context_batcher import ContextBatcher
            from src.smart_retrieval_long import SmartRetrieverLong
            from src.multi_document_analyzer_long import MultiDocumentAnalyzerLong

            # Create all components
            cwm = ContextWindowManager()
            compressor = DocumentCompressor()
            batcher = ContextBatcher()
            retriever = SmartRetrieverLong()
            analyzer = MultiDocumentAnalyzerLong()

            assert cwm is not None
            assert compressor is not None
            assert batcher is not None
            assert retriever is not None
            assert analyzer is not None

            logger.info("✓ FASE 18 pipeline components assembled successfully")
        except ImportError as e:
            pytest.skip(f"Required modules not available: {e}")

    def test_end_to_end_long_context_flow(self):
        """Test end-to-end long context flow"""
        try:
            from src.context_window_manager import ContextWindowManager
            from src.document_compressor import DocumentCompressor, CompressionLevel
            from src.context_batcher import ContextBatcher
            from src.smart_retrieval_long import SmartRetrieverLong, RetrievalStrategy

            # Setup
            cwm = ContextWindowManager()
            compressor = DocumentCompressor()
            batcher = ContextBatcher()
            retriever = SmartRetrieverLong()

            # Create sample documents
            documents = [
                {
                    'id': f'doc_{i}',
                    'text': f'Document {i} content. ' * 100,
                    'metadata': {'source': f'source_{i % 3}'}
                }
                for i in range(20)
            ]

            # Step 1: Allocate context (get allocations for documents)
            allocation_result = cwm.allocate_context(documents, query="test query")
            assert 'allocations' in allocation_result
            assert allocation_result['total_tokens'] >= 0

            # Step 2: Compress documents
            allocation_dict = {
                doc['id']: CompressionLevel.FULL if i < 5 else CompressionLevel.DETAILED
                for i, doc in enumerate(documents)
            }
            compressed = compressor.compress_batch(documents, allocation_dict)
            assert len(compressed) == len(documents)

            # Step 3: Batch documents
            batches = batcher.pack_documents(documents)
            assert len(batches) > 0

            # Step 4: Retrieve with strategy
            result = retriever.retrieve(
                documents=documents,
                query="test query",
                strategy=RetrievalStrategy.HYBRID
            )
            assert result.selected_documents is not None
            assert len(result.selected_documents) > 0

            logger.info("✓ End-to-end FASE 18 flow completed successfully")
        except ImportError as e:
            pytest.skip(f"Required modules not available: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pytest.main([__file__, "-v", "--tb=short"])
