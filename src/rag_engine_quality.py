"""
Quality-Aware RAG Engine - FASE 19
Extends LongContextRAGEngine with quality metrics and feedback loops
"""

import time
from typing import Optional
from dataclasses import dataclass, field

try:
    from src.rag_engine_longcontext import (
        LongContextRAGEngine,
        LongContextRAGResponse
    )
except ImportError:
    from src.rag_engine_multimodal import MultimodalRAGEngine as LongContextRAGEngine
    from src.rag_engine_multimodal import MultimodalRAGResponse as LongContextRAGResponse

from src.quality_metrics import QualityMetrics, QualityMetricsCollector
from src.ragas_integration import RagasEvaluator

logger = get_logger(__name__)

@dataclass
class RAGResponseWithMetrics(LongContextRAGResponse):
    """RAG response extended with quality metrics"""
    quality_metrics: QualityMetrics = field(default_factory=QualityMetrics)
    quality_evaluation_time_ms: float = 0.0
    quality_issues: list[str] = field(default_factory=list)
    improvement_suggestions: list[str] = field(default_factory=list)
    requires_improvement: bool = False
    ragas_scores: Optional[dict] = None
    retry_count: int = 0
    max_retries: int = 3

class QualityAwareRAGEngine(LongContextRAGEngine):
    """RAG Engine with built-in quality monitoring and improvement"""

    def __init__(self):
        """Initialize quality-aware RAG engine"""
        super().__init__()

        # Quality monitoring
        self.metrics_collector = QualityMetricsCollector()
        self.ragas_evaluator = RagasEvaluator()

        # Quality thresholds
        self.min_overall_quality = 0.65
        self.min_faithfulness = 0.55

        logger.info("✓ QualityAwareRAGEngine initialized")

    def query_with_quality_feedback(
        self,
        query: str,
        use_hierarchy: bool = True,
        enable_improvement_loop: bool = True,
        max_retries: int = 3
    ) -> RAGResponseWithMetrics:
        """
        Process query with quality feedback and improvement

        Pipeline:
        1. Generate initial response
        2. Evaluate quality metrics
        3. If quality is low, improve and retry
        4. Return best response with metrics

        Args:
            query: User query
            use_hierarchy: Use hierarchical organization
            enable_improvement_loop: Enable retry-on-poor-quality
            max_retries: Maximum improvement retries

        Returns:
            Response with quality metrics and improvement history
        """
        start_time = time.time()
        response = RAGResponseWithMetrics(
            answer="",
            sources=[],
            image_sources=[],
            text_sources=[],
            approved=False,
            hitl_required=False,
            model="gemini-2.0-flash",
            max_retries=max_retries
        )

        # Generate initial response
        logger.info(f"Generating initial response for: {query[:60]}...")
        base_response = self.query_with_long_context(
            query,
            use_hierarchy=use_hierarchy
        )

        # Copy base response fields
        response.answer = base_response.answer
        response.sources = base_response.sources
        response.text_sources = base_response.text_sources
        response.image_sources = base_response.image_sources
        response.context_token_count = base_response.context_token_count

        # Evaluate quality
        evaluation_start = time.time()
        response.quality_metrics = self._evaluate_response_quality(response)
        response.quality_evaluation_time_ms = (time.time() - evaluation_start) * 1000

        # Get RAGAS scores if available
        if self.ragas_evaluator.is_available():
            ragas_scores = self.ragas_evaluator.evaluate_all(
                query,
                response.answer,
                [s.document if hasattr(s, 'document') else str(s) for s in response.sources]
            )
            response.ragas_scores = ragas_scores.to_dict() if ragas_scores else None

        # Check if improvement is needed
        response.requires_improvement = not self.metrics_collector.is_acceptable_quality(
            response.quality_metrics
        )

        # Identify issues
        response.quality_issues = self.metrics_collector.get_quality_issues(
            response.quality_metrics
        )
        response.improvement_suggestions = self.metrics_collector.get_improvement_suggestions(
            response.quality_metrics
        )

        logger.info(f"Initial quality score: {response.quality_metrics.overall_score:.2f}")

        # Attempt improvements if enabled and quality is low
        if enable_improvement_loop and response.requires_improvement:
            logger.info("Quality below threshold, attempting improvements...")
            response = self._improve_response_quality(
                response,
                query,
                max_retries
            )

        response.approved = not response.requires_improvement
        response.hitl_required = response.requires_improvement

        response.latency_breakdown = {
            "total_ms": (time.time() - start_time) * 1000,
            "evaluation_ms": response.quality_evaluation_time_ms,
            "improvement_ms": (time.time() - start_time - response.quality_evaluation_time_ms / 1000) * 1000
        }

        return response

    def _evaluate_response_quality(
        self,
        response: RAGResponseWithMetrics
    ) -> QualityMetrics:
        """
        Evaluate response quality using multiple metrics

        Args:
            response: Response to evaluate

        Returns:
            QualityMetrics with all scores
        """
        try:
            # Extract sources as strings
            sources = []
            for source in response.sources:
                if hasattr(source, 'document'):
                    sources.append(source.document)
                else:
                    sources.append(str(source))

            # Get original query from context (using heuristic)
            # In practice, this would be passed through
            query = "user query"

            # Calculate metrics
            metrics = self.metrics_collector.evaluate_response(
                query,
                response.answer,
                sources
            )

            logger.debug(f"Quality metrics: {metrics.to_dict()}")
            return metrics

        except Exception as e:
            logger.error(f"Quality evaluation failed: {e}")
            return QualityMetrics()

    def _improve_response_quality(
        self,
        response: RAGResponseWithMetrics,
        query: str,
        max_retries: int
    ) -> RAGResponseWithMetrics:
        """
        Attempt to improve low-quality responses

        Strategies:
        1. Expand query and retrieve more context
        2. Use more stringent reranking
        3. Generate with different prompting
        4. Increase temperature for diversity

        Args:
            response: Initial response
            query: Original query
            max_retries: Maximum retry attempts

        Returns:
            Improved response
        """
        retry_count = 0
        best_response = response
        best_score = response.quality_metrics.overall_score

        while retry_count < max_retries:
            retry_count += 1
            logger.info(f"Improvement retry {retry_count}/{max_retries}...")

            improvement_response = self._generate_with_improvement_strategy(
                query,
                retry_count,
                response
            )

            # Evaluate improved response
            metrics = self._evaluate_response_quality(improvement_response)
            improvement_response.quality_metrics = metrics
            improvement_response.retry_count = retry_count

            # Check if better
            if metrics.overall_score > best_score:
                logger.info(
                    f"Improved: {best_score:.2f} → {metrics.overall_score:.2f}"
                )
                best_response = improvement_response
                best_score = metrics.overall_score

                # If acceptable now, stop
                if self.metrics_collector.is_acceptable_quality(metrics):
                    best_response.requires_improvement = False
                    best_response.approved = True
                    logger.info("Response improved to acceptable quality")
                    break

        return best_response

    def _generate_with_improvement_strategy(
        self,
        query: str,
        retry_count: int,
        previous_response: RAGResponseWithMetrics
    ) -> RAGResponseWithMetrics:
        """
        Generate response using improvement strategy based on retry count

        Args:
            query: Query
            retry_count: Current retry count
            previous_response: Previous response

        Returns:
            New response with improvement strategy applied
        """
        improvement_response = RAGResponseWithMetrics(
            answer="",
            sources=previous_response.sources,
            approved=False,
            hitl_required=False,
            model="gemini-2.0-flash",
            retry_count=retry_count
        )

        try:
            if retry_count == 1:
                # Strategy 1: Expand query and retrieve more documents
                logger.debug("Strategy 1: Expanding query")
                expanded_query = self._expand_query(query)
                response = self.query_with_long_context(
                    expanded_query,
                    top_k_docs=15  # More documents
                )
                improvement_response.answer = response.answer

            elif retry_count == 2:
                # Strategy 2: Use stricter reranking and coherence prompting
                logger.debug("Strategy 2: Strict reranking")
                response = self.query_with_long_context(
                    query,
                    top_k_docs=10
                )
                # Add coherence-focused regeneration
                improvement_response.answer = self._regenerate_for_coherence(
                    response.answer,
                    query
                )

            else:
                # Strategy 3: Manual reformulation for clarity
                logger.debug("Strategy 3: Clarity reformulation")
                improvement_response.answer = self._reformulate_for_clarity(
                    previous_response.answer,
                    query
                )

        except Exception as e:
            logger.error(f"Improvement strategy failed: {e}")
            improvement_response.answer = previous_response.answer

        return improvement_response

    def _expand_query(self, query: str) -> str:
        """Expand query with related terms"""
        # Simple expansion - in practice would use query expansion engine
        expansions = {
            "machine learning": "machine learning algorithms, ML models, deep learning",
            "database": "database systems, SQL, data management, DBMS",
            "python": "Python programming, Python code, Python libraries, Python language",
        }

        for key, expansion in expansions.items():
            if key.lower() in query.lower():
                return f"{query}. Related topics: {expansion}"

        return query + " (expanded)"

    def _regenerate_for_coherence(self, answer: str, query: str) -> str:
        """Regenerate answer focused on coherence"""
        # In practice, would call LLM with specific prompt
        prompt = f"""Reformat the following answer to be more coherent and well-structured.
        Maintain accuracy but improve organization, flow, and clarity.

        Query: {query}
        Original answer: {answer}

        Reformatted answer:"""

        # Placeholder for actual LLM call
        return answer  # Would return regenerated version

    def _reformulate_for_clarity(self, answer: str, query: str) -> str:
        """Reformulate answer for maximum clarity"""
        # In practice, would call LLM with specific prompt
        prompt = f"""Reformulate this answer to be maximally clear and easy to understand.
        Use simple language, short sentences, and clear structure.

        Original answer: {answer}

        Clear answer:"""

        # Placeholder for actual LLM call
        return answer  # Would return reformulated version

    def get_quality_report(
        self,
        response: RAGResponseWithMetrics
    ) -> dict:
        """
        Generate detailed quality report

        Args:
            response: Response to report on

        Returns:
            Dictionary with quality analysis
        """
        return {
            "overall_score": response.quality_metrics.overall_score,
            "metrics": response.quality_metrics.to_dict(),
            "issues": response.quality_issues,
            "suggestions": response.improvement_suggestions,
            "acceptable": not response.requires_improvement,
            "retry_count": response.retry_count,
            "evaluation_time_ms": response.quality_evaluation_time_ms,
            "ragas_scores": response.ragas_scores
        }

    def set_quality_thresholds(
        self,
        min_overall: float = 0.65,
        min_faithfulness: float = 0.55
    ) -> None:
        """
        Configure quality thresholds

        Args:
            min_overall: Minimum overall quality score
            min_faithfulness: Minimum faithfulness score
        """
        self.metrics_collector.min_acceptable_overall = min_overall
        self.metrics_collector.min_acceptable_faithfulness = min_faithfulness
        logger.info(f"Quality thresholds updated: overall={min_overall}, faith={min_faithfulness}")
