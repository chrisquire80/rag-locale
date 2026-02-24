"""FASE 19: Quality Metrics - Comprehensive Tests"""

import pytest
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class TestQualityEvaluator:
    """Test quality evaluation functionality"""

    def test_evaluator_initialization(self):
        """Test QualityEvaluator can be initialized"""
        try:
            from src.quality_metrics import get_quality_evaluator
            evaluator = get_quality_evaluator()
            assert evaluator is not None
            logger.info("✓ QualityEvaluator initialized")
        except ImportError as e:
            pytest.skip(f"quality_metrics module not available: {e}")

    def test_evaluate_single_query(self):
        """Test evaluating a single query"""
        try:
            from src.quality_metrics import get_quality_evaluator
            evaluator = get_quality_evaluator()

            documents = [
                {'id': 'doc_1', 'text': 'Document 1 content about AI and machine learning.'},
                {'id': 'doc_2', 'text': 'Document 2 content about neural networks and deep learning.'},
            ]

            evaluation = evaluator.evaluate_query(
                query_id='q_1',
                query='What is machine learning?',
                answer='Machine learning is a subset of artificial intelligence.',
                retrieved_documents=documents
            )

            assert evaluation.query_id == 'q_1'
            assert evaluation.query == 'What is machine learning?'
            assert len(evaluation.metrics) > 0
            assert evaluation.get_overall_score() >= 0

            logger.info(f"✓ Query evaluation: score {evaluation.get_overall_score():.2f}")
        except ImportError:
            pytest.skip("quality_metrics module not available")

    def test_evaluate_multiple_queries(self):
        """Test evaluating multiple queries"""
        try:
            from src.quality_metrics import get_quality_evaluator
            evaluator = get_quality_evaluator()

            documents = [
                {'id': f'doc_{i}', 'text': f'Content about topic {i}.'} for i in range(5)
            ]

            queries = [
                ('q_1', 'What is topic 0?', 'Topic 0 is about...'),
                ('q_2', 'What is topic 1?', 'Topic 1 is about...'),
                ('q_3', 'What is topic 2?', 'Topic 2 is about...'),
            ]

            for query_id, query, answer in queries:
                evaluator.evaluate_query(
                    query_id=query_id,
                    query=query,
                    answer=answer,
                    retrieved_documents=documents
                )

            assert len(evaluator.evaluations) >= 3
            logger.info(f"✓ Evaluated {len(evaluator.evaluations)} queries")
        except ImportError:
            pytest.skip("quality_metrics module not available")

    def test_faithfulness_metric(self):
        """Test faithfulness evaluation"""
        try:
            from src.quality_metrics import get_quality_evaluator, MetricType
            evaluator = get_quality_evaluator()

            documents = [
                {'id': 'doc_1', 'text': 'The Earth is round and orbits the Sun.'},
            ]

            evaluation = evaluator.evaluate_query(
                query_id='q_faith',
                query='What shape is the Earth?',
                answer='The Earth is round.',
                retrieved_documents=documents
            )

            faithfulness = evaluation.metrics.get(MetricType.FAITHFULNESS)
            assert faithfulness is not None
            assert faithfulness.score > 0
            assert 0 <= faithfulness.confidence <= 1

            logger.info(f"✓ Faithfulness: {faithfulness.score:.2f}")
        except ImportError:
            pytest.skip("quality_metrics module not available")

    def test_relevance_metric(self):
        """Test relevance evaluation"""
        try:
            from src.quality_metrics import get_quality_evaluator, MetricType
            evaluator = get_quality_evaluator()

            documents = [
                {'id': 'doc_1', 'text': 'Content about the topic.'},
            ]

            evaluation = evaluator.evaluate_query(
                query_id='q_rel',
                query='What is the topic?',
                answer='The topic is important.',
                retrieved_documents=documents
            )

            relevance = evaluation.metrics.get(MetricType.RELEVANCE)
            assert relevance is not None
            assert 0 <= relevance.score <= 1

            logger.info(f"✓ Relevance: {relevance.score:.2f}")
        except ImportError:
            pytest.skip("quality_metrics module not available")

    def test_evaluation_summary(self):
        """Test getting evaluation summary"""
        try:
            from src.quality_metrics import get_quality_evaluator
            evaluator = get_quality_evaluator()

            documents = [
                {'id': 'doc_1', 'text': 'Test content.'},
            ]

            for i in range(5):
                evaluator.evaluate_query(
                    query_id=f'q_{i}',
                    query=f'Query {i}?',
                    answer=f'Answer {i}.',
                    retrieved_documents=documents
                )

            summary = evaluator.get_summary()

            assert 'total_queries' in summary
            assert summary['total_queries'] >= 5
            assert 'mean_score' in summary

            logger.info(f"✓ Summary: {summary['total_queries']} queries, "
                       f"avg score {summary['mean_score']:.2f}")
        except ImportError:
            pytest.skip("quality_metrics module not available")

    def test_metric_types(self):
        """Test all metric types are available"""
        try:
            from src.quality_metrics import MetricType

            metric_types = [
                MetricType.FAITHFULNESS,
                MetricType.RELEVANCE,
                MetricType.PRECISION,
                MetricType.RECALL,
                MetricType.F1_SCORE,
                MetricType.CONSISTENCY,
                MetricType.LATENCY,
                MetricType.COST,
            ]

            assert len(metric_types) == 8
            logger.info(f"✓ All {len(metric_types)} metric types available")
        except ImportError:
            pytest.skip("quality_metrics module not available")

class TestIntegrationWithRAG:
    """Integration tests with RAG pipeline"""

    def test_quality_evaluator_with_rag_results(self):
        """Test evaluator with RAG pipeline results"""
        try:
            from src.quality_metrics import get_quality_evaluator
            evaluator = get_quality_evaluator()

            # Simulate RAG pipeline output
            rag_result = {
                'query': 'What is RAG?',
                'answer': 'RAG is Retrieval Augmented Generation.',
                'retrieved_docs': [
                    {'id': 'doc_1', 'text': 'RAG combines retrieval and generation.'},
                    {'id': 'doc_2', 'text': 'Retrieval finds relevant documents.'},
                ]
            }

            evaluation = evaluator.evaluate_query(
                query_id='rag_test',
                query=rag_result['query'],
                answer=rag_result['answer'],
                retrieved_documents=rag_result['retrieved_docs']
            )

            assert evaluation.get_overall_score() > 0
            logger.info(f"✓ RAG integration: score {evaluation.get_overall_score():.2f}")
        except ImportError:
            pytest.skip("quality_metrics module not available")

    def test_metric_tracking_over_time(self):
        """Test tracking metrics over multiple queries"""
        try:
            from src.quality_metrics import get_quality_evaluator
            evaluator = get_quality_evaluator()

            # Simulate multiple RAG queries
            test_cases = [
                ('Query 1', 'Answer 1 with good content.'),
                ('Query 2', 'Answer 2 discussing the topic.'),
                ('Query 3', 'Answer 3 providing details.'),
                ('Query 4', 'Answer 4 with comprehensive information.'),
                ('Query 5', 'Answer 5 addressing the question.'),
            ]

            for i, (query, answer) in enumerate(test_cases):
                evaluator.evaluate_query(
                    query_id=f'seq_{i}',
                    query=query,
                    answer=answer,
                    retrieved_documents=[
                        {'id': 'doc_1', 'text': 'Relevant content document.'}
                    ]
                )

            summary = evaluator.get_summary()
            assert summary['total_queries'] >= 5

            logger.info(f"✓ Tracked metrics over {summary['total_queries']} sequential queries")
        except ImportError:
            pytest.skip("quality_metrics module not available")

class TestMetricsValidation:
    """Test metric validation and constraints"""

    def test_metric_score_range(self):
        """Test metric scores are within valid range"""
        try:
            from src.quality_metrics import get_quality_evaluator
            evaluator = get_quality_evaluator()

            evaluation = evaluator.evaluate_query(
                query_id='range_test',
                query='Test query?',
                answer='Test answer.',
                retrieved_documents=[{'id': 'd1', 'text': 'Test content.'}]
            )

            for metric_type, metric_score in evaluation.metrics.items():
                assert 0 <= metric_score.score <= 1, f"{metric_type} score out of range"
                assert 0 <= metric_score.confidence <= 1, f"{metric_type} confidence out of range"

            logger.info("✓ All metric scores within valid range [0,1]")
        except ImportError:
            pytest.skip("quality_metrics module not available")

    def test_overall_score_calculation(self):
        """Test overall score weighted calculation"""
        try:
            from src.quality_metrics import get_quality_evaluator
            evaluator = get_quality_evaluator()

            evaluation = evaluator.evaluate_query(
                query_id='overall_test',
                query='What is the answer?',
                answer='The answer is positive.',
                retrieved_documents=[{'id': 'd1', 'text': 'Answer content.'}]
            )

            overall = evaluation.get_overall_score()
            assert 0 <= overall <= 1
            logger.info(f"✓ Overall score: {overall:.2f} (valid range)")
        except ImportError:
            pytest.skip("quality_metrics module not available")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    pytest.main([__file__, "-v"])
