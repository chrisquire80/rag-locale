"""
FASE 19 - Quality Metrics & Evaluation Tests
Tests quality metrics calculation, evaluation, and RAGAS integration
"""

import pytest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from quality_metrics import (
    QualityMetrics,
    QualityMetricsCollector,
    MetricType
)
from ragas_integration import (
    RagasEvaluator,
    RagasScores,
    check_ragas_availability
)
from rag_engine_quality import (
    QualityAwareRAGEngine,
    RAGResponseWithMetrics
)


class TestQualityMetrics:
    """Tests for QualityMetrics container"""

    def test_quality_metrics_initialization(self):
        """Test QualityMetrics initializes with defaults"""
        metrics = QualityMetrics()

        assert metrics.faithfulness == 0.0
        assert metrics.relevance == 0.0
        assert metrics.coherence == 0.0
        assert metrics.coverage == 0.0
        assert metrics.completeness == 0.0
        assert metrics.overall_score == 0.0

    def test_quality_metrics_to_dict(self):
        """Test converting metrics to dictionary"""
        metrics = QualityMetrics()
        metrics.faithfulness = 0.8
        metrics.relevance = 0.7

        result = metrics.to_dict()

        assert isinstance(result, dict)
        assert result["faithfulness"] == 0.8
        assert result["relevance"] == 0.7


class TestQualityMetricsCollector:
    """Tests for QualityMetricsCollector"""

    def setup_method(self):
        """Setup for each test"""
        self.collector = QualityMetricsCollector()

    def test_collector_initialization(self):
        """Test collector initializes properly"""
        assert self.collector is not None
        assert len(self.collector.metric_weights) == 5
        assert self.collector.min_acceptable_overall > 0

    def test_faithfulness_empty_inputs(self):
        """Test faithfulness with empty inputs"""
        score = self.collector.calculate_faithfulness("", [])
        assert score == 0.0

    def test_faithfulness_perfect_overlap(self):
        """Test faithfulness when answer matches source"""
        answer = "Machine learning is a subset of artificial intelligence"
        sources = ["Machine learning is a subset of artificial intelligence"]

        score = self.collector.calculate_faithfulness(answer, sources)
        assert score > 0.7

    def test_faithfulness_with_citations(self):
        """Test faithfulness boost with citation markers"""
        answer = "ML is powerful [1]. It uses algorithms [2]."
        sources = ["Machine learning is powerful", "Algorithms are used"]

        score = self.collector.calculate_faithfulness(answer, sources)
        # Should be boosted due to citation markers
        assert score > 0.5

    def test_relevance_empty_inputs(self):
        """Test relevance with empty inputs"""
        score = self.collector.calculate_relevance("", "")
        assert score == 0.0

    def test_relevance_matching_query(self):
        """Test relevance when answer addresses query"""
        query = "What is machine learning?"
        answer = "Machine learning is a subset of AI that learns from data."

        score = self.collector.calculate_relevance(query, answer)
        assert score > 0.6

    def test_relevance_non_matching_query(self):
        """Test relevance when answer doesn't match query"""
        query = "What is machine learning?"
        answer = "Python is a programming language."

        score = self.collector.calculate_relevance(query, answer)
        assert score < 0.5

    def test_relevance_penalizes_short_answers(self):
        """Test relevance penalizes very short answers"""
        query = "Tell me about machine learning"
        short_answer = "It's good."

        score = self.collector.calculate_relevance(query, short_answer)
        # Short answer should get penalty
        assert score < 0.5

    def test_coherence_empty_answer(self):
        """Test coherence with empty answer"""
        score = self.collector.calculate_coherence("")
        assert score == 0.0

    def test_coherence_well_formed_answer(self):
        """Test coherence of well-structured answer"""
        answer = """Machine learning is important.

However, it requires careful implementation.

Furthermore, proper evaluation is critical.

In conclusion, ML needs attention to detail."""

        score = self.collector.calculate_coherence(answer)
        assert score > 0.6

    def test_coherence_detects_transitions(self):
        """Test coherence detects transition words"""
        answer_with_transitions = "First, X is true. Therefore, Y follows. Consequently, Z happens."
        answer_without = "X is true. Y is also true. Z is also true."

        score_with = self.collector.calculate_coherence(answer_with_transitions)
        score_without = self.collector.calculate_coherence(answer_without)

        # With transitions should score higher
        assert score_with > score_without

    def test_coverage_empty_inputs(self):
        """Test coverage with empty inputs"""
        score = self.collector.calculate_coverage([], "")
        assert score == 0.0

    def test_coverage_all_terms_present(self):
        """Test coverage when all terms are present"""
        terms = ["machine", "learning", "algorithm"]
        answer = "Machine learning algorithms are powerful tools."

        score = self.collector.calculate_coverage(terms, answer)
        assert score > 0.8

    def test_coverage_some_terms_missing(self):
        """Test coverage when some terms are missing"""
        terms = ["machine", "learning", "algorithm", "neural"]
        answer = "Machine learning algorithms are powerful."

        score = self.collector.calculate_coverage(terms, answer)
        # Should be partial coverage
        assert 0.5 <= score <= 0.8

    def test_completeness_why_question(self):
        """Test completeness for 'why' questions"""
        query = "Why is machine learning important?"
        answer_good = "Machine learning is important because it enables automation of complex tasks."
        answer_bad = "It is important."

        score_good = self.collector.calculate_completeness(query, answer_good, [])
        score_bad = self.collector.calculate_completeness(query, answer_bad, [])

        # Answer with reasoning should score higher
        assert score_good > score_bad

    def test_completeness_how_question(self):
        """Test completeness for 'how' questions"""
        query = "How does machine learning work?"
        answer_good = "Machine learning works in three steps: 1. Data collection 2. Training 3. Prediction"
        answer_bad = "It works well."

        score_good = self.collector.calculate_completeness(query, answer_good, [])
        score_bad = self.collector.calculate_completeness(query, answer_bad, [])

        # Answer with steps should score higher
        assert score_good > score_bad

    def test_evaluate_response_comprehensive(self):
        """Test comprehensive evaluation"""
        query = "What is machine learning?"
        answer = """Machine learning is a subset of artificial intelligence.
        It enables systems to learn from data without explicit programming.

        For example, recommendation systems use machine learning.

        In conclusion, machine learning is transformative."""
        sources = ["Machine learning is a subset of AI", "Recommendation systems use ML"]

        metrics = self.collector.evaluate_response(query, answer, sources)

        assert metrics.faithfulness > 0
        assert metrics.relevance > 0
        assert metrics.coherence > 0
        assert metrics.coverage > 0
        assert metrics.overall_score > 0

    def test_is_acceptable_quality_good_response(self):
        """Test quality acceptance for good response"""
        metrics = QualityMetrics(
            faithfulness=0.8,
            relevance=0.8,
            coherence=0.7,
            coverage=0.8,
            completeness=0.7,
            overall_score=0.75
        )

        acceptable = self.collector.is_acceptable_quality(metrics)
        assert acceptable

    def test_is_acceptable_quality_poor_response(self):
        """Test quality acceptance for poor response"""
        metrics = QualityMetrics(
            faithfulness=0.3,
            relevance=0.4,
            coherence=0.3,
            coverage=0.2,
            completeness=0.3,
            overall_score=0.3
        )

        acceptable = self.collector.is_acceptable_quality(metrics)
        assert not acceptable

    def test_get_quality_issues(self):
        """Test identification of quality issues"""
        metrics = QualityMetrics(
            faithfulness=0.4,
            relevance=0.3,
            coherence=0.8,
            coverage=0.7,
            completeness=0.6,
            overall_score=0.5
        )

        issues = self.collector.get_quality_issues(metrics)
        assert len(issues) > 0
        assert any("faithfulness" in issue.lower() for issue in issues)
        assert any("relevance" in issue.lower() for issue in issues)

    def test_get_improvement_suggestions(self):
        """Test generation of improvement suggestions"""
        metrics = QualityMetrics(
            faithfulness=0.4,
            relevance=0.5,
            coherence=0.3,
            coverage=0.5,
            completeness=0.4,
            overall_score=0.4
        )

        suggestions = self.collector.get_improvement_suggestions(metrics)
        assert len(suggestions) > 0
        assert isinstance(suggestions, list)


class TestRagasIntegration:
    """Tests for RAGAS integration"""

    def setup_method(self):
        """Setup for each test"""
        self.evaluator = RagasEvaluator()

    def test_ragas_evaluator_initialization(self):
        """Test RAGAS evaluator initializes"""
        assert self.evaluator is not None

    def test_ragas_availability_check(self):
        """Test RAGAS availability check"""
        available = check_ragas_availability()
        # Should return bool regardless of installation
        assert isinstance(available, bool)

    def test_ragas_scores_initialization(self):
        """Test RagasScores initializes"""
        scores = RagasScores()

        assert scores.faithfulness is None
        assert scores.answer_relevance is None
        assert scores.context_relevance is None

    def test_ragas_is_available_method(self):
        """Test RagasEvaluator.is_available() method"""
        result = RagasEvaluator.is_available()
        assert isinstance(result, bool)

    def test_ragas_install_instructions(self):
        """Test RAGAS install instructions"""
        instructions = RagasEvaluator.install_instructions()
        assert isinstance(instructions, str)
        assert "pip install ragas" in instructions

    def test_ragas_graceful_fallback(self):
        """Test RAGAS gracefully handles unavailability"""
        # These should not raise errors even if RAGAS unavailable
        result1 = self.evaluator.evaluate_faithfulness("answer", ["source"])
        assert result1 is None or isinstance(result1, float)

        result2 = self.evaluator.evaluate_answer_relevance("question", "answer")
        assert result2 is None or isinstance(result2, float)

        result3 = self.evaluator.evaluate_context_relevance("question", ["context"])
        assert result3 is None or isinstance(result3, float)

    def test_ragas_evaluate_all(self):
        """Test RAGAS evaluate_all method"""
        scores = self.evaluator.evaluate_all(
            "What is AI?",
            "Artificial intelligence is a field of computer science.",
            ["AI is a field of computer science"]
        )

        assert isinstance(scores, RagasScores)

    def test_ragas_get_score(self):
        """Test RAGAS score calculation"""
        metrics = {
            "faithfulness": 0.8,
            "answer_relevance": 0.7,
            "context_relevance": 0.75
        }

        score = self.evaluator.get_ragas_score(metrics)
        # Should return score or None
        assert score is None or (isinstance(score, float) and 0 <= score <= 1)


class TestQualityAwareRAGEngine:
    """Tests for QualityAwareRAGEngine"""

    def setup_method(self):
        """Setup for each test"""
        self.engine = QualityAwareRAGEngine()

    def test_engine_initialization(self):
        """Test engine initializes properly"""
        assert self.engine is not None
        assert self.engine.metrics_collector is not None
        assert self.engine.ragas_evaluator is not None

    def test_query_with_quality_feedback_returns_response(self):
        """Test query returns appropriate response type"""
        response = self.engine.query_with_quality_feedback(
            "test query",
            enable_improvement_loop=False
        )

        assert isinstance(response, RAGResponseWithMetrics)
        assert hasattr(response, 'quality_metrics')

    def test_response_has_quality_metadata(self):
        """Test response includes quality metadata"""
        response = self.engine.query_with_quality_feedback(
            "test query",
            enable_improvement_loop=False
        )

        assert hasattr(response, 'quality_evaluation_time_ms')
        assert hasattr(response, 'quality_issues')
        assert hasattr(response, 'improvement_suggestions')
        assert hasattr(response, 'requires_improvement')

    def test_quality_evaluation_produces_metrics(self):
        """Test that evaluation produces metrics"""
        response = RAGResponseWithMetrics(
            answer="Machine learning is important.",
            sources=[],
            approved=True,
            hitl_required=False,
            model="gemini"
        )

        metrics = self.engine._evaluate_response_quality(response)

        assert isinstance(metrics, QualityMetrics)
        # Metrics should have values (even if low)
        assert hasattr(metrics, 'overall_score')

    def test_get_quality_report(self):
        """Test quality report generation"""
        response = RAGResponseWithMetrics(
            answer="Test answer.",
            sources=[],
            approved=True,
            hitl_required=False,
            model="gemini"
        )
        response.quality_metrics = QualityMetrics(overall_score=0.7)

        report = self.engine.get_quality_report(response)

        assert isinstance(report, dict)
        assert "overall_score" in report
        assert "metrics" in report
        assert "issues" in report
        assert "suggestions" in report

    def test_set_quality_thresholds(self):
        """Test setting quality thresholds"""
        self.engine.set_quality_thresholds(
            min_overall=0.7,
            min_faithfulness=0.6
        )

        assert self.engine.metrics_collector.min_acceptable_overall == 0.7
        assert self.engine.metrics_collector.min_acceptable_faithfulness == 0.6

    def test_improvement_strategies_available(self):
        """Test that improvement strategies are available"""
        # These should not raise errors
        assert hasattr(self.engine, '_expand_query')
        assert hasattr(self.engine, '_regenerate_for_coherence')
        assert hasattr(self.engine, '_reformulate_for_clarity')

    def test_retry_counting(self):
        """Test retry counting in responses"""
        response = RAGResponseWithMetrics(
            answer="Test",
            sources=[],
            approved=False,
            hitl_required=True,
            model="gemini",
            retry_count=3,
            max_retries=3
        )

        assert response.retry_count == 3
        assert response.max_retries == 3


class TestQualityMetricsIntegration:
    """Integration tests for quality metrics"""

    def test_end_to_end_evaluation_pipeline(self):
        """Test complete evaluation pipeline"""
        collector = QualityMetricsCollector()

        query = "How does neural networks work?"
        answer = """Neural networks are inspired by biological neurons.
        They work by connecting many simple units called neurons.
        Each neuron has weights and biases.
        For example, a simple network can learn to classify images.
        In conclusion, neural networks are powerful learning tools."""
        sources = [
            "Neural networks have layers of neurons",
            "Weights and biases are learned during training",
            "Neural networks can classify images"
        ]

        metrics = collector.evaluate_response(query, answer, sources)
        issues = collector.get_quality_issues(metrics)
        suggestions = collector.get_improvement_suggestions(metrics)

        assert metrics.overall_score > 0
        assert isinstance(issues, list)
        assert isinstance(suggestions, list)

    def test_quality_improvement_loop_simulation(self):
        """Test simulated quality improvement loop"""
        engine = QualityAwareRAGEngine()

        # Simulate poor response
        poor_response = RAGResponseWithMetrics(
            answer="ML good.",
            sources=[],
            approved=False,
            hitl_required=False,
            model="gemini"
        )

        # Evaluate and identify issues
        metrics = engine._evaluate_response_quality(poor_response)
        assert metrics.overall_score < 0.7

    def test_metric_weights_sum_to_one(self):
        """Test that metric weights sum to 1.0"""
        collector = QualityMetricsCollector()
        total_weight = sum(collector.metric_weights.values())

        assert abs(total_weight - 1.0) < 0.01


class TestQualityEdgeCases:
    """Test edge cases in quality evaluation"""

    def test_very_long_answer(self):
        """Test quality metrics with very long answer"""
        collector = QualityMetricsCollector()
        long_answer = "This is a very long answer. " * 200

        score = collector.calculate_coherence(long_answer)
        assert 0 <= score <= 1

    def test_very_short_answer(self):
        """Test quality metrics with very short answer"""
        collector = QualityMetricsCollector()
        short_answer = "Yes."

        metrics = collector.evaluate_response("Tell me about AI", short_answer, [])
        assert metrics.completeness < 0.5

    def test_multilingual_content(self):
        """Test quality metrics with multilingual content"""
        collector = QualityMetricsCollector()
        multilingual = "English text here. Texte français. Contenido en español."

        score = collector.calculate_coherence(multilingual)
        assert 0 <= score <= 1

    def test_special_characters_and_formatting(self):
        """Test quality metrics with special formatting"""
        collector = QualityMetricsCollector()
        formatted_answer = """
        # Title
        - Point 1
        - Point 2
        * Item 1
        * Item 2
        """

        score = collector.calculate_coherence(formatted_answer)
        assert score > 0.5  # Should recognize structure


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
