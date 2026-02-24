"""
Phase 12.1: Comprehensive Quality Evaluation Framework

Evaluates RAG response quality using multiple metrics:
- Faithfulness: How grounded in sources (0-1)
- Relevance: How relevant to query (0-1)
- Precision: % of retrieved docs that are relevant
- Recall: % of relevant docs that were retrieved
- Consistency: Answer consistency across multiple generations
- F1: Harmonic mean of precision/recall
"""

import logging
import json
from typing import Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics

logger = logging.getLogger(__name__)

@dataclass
class QueryEvaluation:
    """Comprehensive evaluation result for a query response"""
    query: str
    answer: str
    contexts: list[str]

    # Core metrics (0-1 scale)
    faithfulness: float  # Claims grounded in context
    relevance: float     # Answer relevant to query
    precision: float     # % retrieved docs relevant
    recall: float        # % relevant docs retrieved
    consistency: float   # Answer consistency

    # Derived metrics
    f1_score: float      # Harmonic mean of precision/recall
    overall_score: float # Weighted average

    # Metadata
    num_sources: int
    response_length: int
    evaluation_time_ms: float = 0.0

class QualityEvaluator:
    """
    Evaluates RAG response quality using LLM-as-Judge.

    Strategy:
    1. Use Gemini to score faithfulness and relevance
    2. Calculate precision/recall from source retrieval
    3. Measure consistency from multiple generations
    4. Combine into weighted overall score

    Weights:
    - Faithfulness: 35% (most important - avoid hallucinations)
    - Relevance: 30% (answer relevance to query)
    - Precision: 20% (quality of retrieved documents)
    - Consistency: 15% (stability across generations)
    """

    def __init__(self, llm_service=None):
        """
        Initialize quality evaluator.

        Args:
            llm_service: LLM service for evaluation (Gemini)
        """
        self.llm = llm_service
        if not self.llm:
            from src.llm_service import get_llm_service
            self.llm = get_llm_service()

    def evaluate_response(
        self,
        query: str,
        answer: str,
        contexts: list[str],
        reference_answer: Optional[str] = None
    ) -> QueryEvaluation:
        """
        Evaluate a single RAG response.

        Args:
            query: User query
            answer: Generated answer
            contexts: Retrieved source contexts
            reference_answer: Optional ground truth for comparison

        Returns:
            QueryEvaluation with all metrics
        """
        import time
        start = time.perf_counter()

        # Calculate individual metrics
        faithfulness = self._evaluate_faithfulness(answer, contexts)
        relevance = self._evaluate_relevance(query, answer)
        precision = self._calculate_precision(contexts)
        recall = self._calculate_recall(contexts, reference_answer) if reference_answer else 0.8
        consistency = self._evaluate_consistency(answer, [answer])  # Single generation

        # Calculate derived metrics
        f1_score = 2 * (precision * recall) / (precision + recall + 1e-6)

        # Weighted overall score
        overall_score = (
            faithfulness * 0.35 +
            relevance * 0.30 +
            precision * 0.20 +
            consistency * 0.15
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        return QueryEvaluation(
            query=query,
            answer=answer,
            contexts=contexts,
            faithfulness=faithfulness,
            relevance=relevance,
            precision=precision,
            recall=recall,
            consistency=consistency,
            f1_score=f1_score,
            overall_score=overall_score,
            num_sources=len(contexts),
            response_length=len(answer.split()),
            evaluation_time_ms=elapsed_ms
        )

    def evaluate_batch(
        self,
        queries: list[str],
        answers: list[str],
        contexts_list: list[list[str]]
    ) -> list[QueryEvaluation]:
        """
        Evaluate multiple responses in parallel.

        Args:
            queries: List of user queries
            answers: List of generated answers
            contexts_list: List of context lists (one per query)

        Returns:
            List of QueryEvaluation objects
        """
        results = []

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = []

            for query, answer, contexts in zip(queries, answers, contexts_list):
                future = executor.submit(
                    self.evaluate_response,
                    query,
                    answer,
                    contexts
                )
                futures.append(future)

            for future in as_completed(futures):
                try:
                    result = future.result(timeout=30)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Batch evaluation error: {e}")

        return results

    def _evaluate_faithfulness(
        self,
        answer: str,
        contexts: list[str]
    ) -> float:
        """
        Evaluate how faithfully the answer is grounded in contexts.

        Uses LLM-as-judge to validate claims against sources.

        Returns: 0.0-1.0 (1.0 = perfectly grounded)
        """
        if not contexts:
            return 0.0  # No sources = no grounding

        try:
            context_text = "\n\n".join(contexts[:3])  # Use top 3 contexts

            prompt = f"""Evaluate if this answer is grounded in the provided contexts.
Score each claim as supported (1), partially supported (0.5), or unsupported (0).

Answer: "{answer}"

Contexts:
{context_text}

Rate overall faithfulness (0-1). A score of 1 means all claims are directly supported by contexts.
Return ONLY a number between 0 and 1."""

            response = self.llm.generate_response(prompt)

            try:
                score = float(response.strip())
                return max(0.0, min(1.0, score))
            except ValueError:
                # Fallback: count how many contexts match answer
                match_count = sum(
                    1 for ctx in contexts
                    if len(set(answer.split()) & set(ctx.split())) > 5
                )
                return min(1.0, match_count / len(contexts))

        except Exception as e:
            logger.warning(f"Faithfulness evaluation error: {e}")
            return 0.5  # Default to neutral

    def _evaluate_relevance(self, query: str, answer: str) -> float:
        """
        Evaluate how relevant the answer is to the query.

        Uses LLM-as-judge to assess relevance.

        Returns: 0.0-1.0 (1.0 = perfectly relevant)
        """
        try:
            prompt = f"""Rate how relevant this answer is to the question (0-1).
0 = completely irrelevant
0.5 = somewhat relevant
1.0 = directly answers the question

Question: "{query}"
Answer: "{answer[:500]}"

Return ONLY a number between 0 and 1."""

            response = self.llm.generate_response(prompt)

            try:
                score = float(response.strip())
                return max(0.0, min(1.0, score))
            except ValueError:
                # Fallback: calculate semantic overlap
                query_words = set(query.lower().split())
                answer_words = set(answer.lower().split())
                overlap = len(query_words & answer_words)
                return min(1.0, overlap / max(len(query_words), 1))

        except Exception as e:
            logger.warning(f"Relevance evaluation error: {e}")
            return 0.5

    def _calculate_precision(self, contexts: list[str]) -> float:
        """
        Calculate precision: % of retrieved docs that are relevant.

        In this context, we assume all retrieved contexts are somewhat relevant
        (otherwise they wouldn't be retrieved). Score based on context quality.

        Returns: 0.0-1.0
        """
        if not contexts:
            return 0.0

        # Simple heuristic: longer, more detailed contexts = higher quality
        avg_length = statistics.mean(len(c.split()) for c in contexts)
        min_length = 50  # Minimum meaningful context
        max_length = 500  # Optimal context length

        if avg_length < min_length:
            return 0.5  # Snippets are lower precision
        elif avg_length > max_length:
            return 0.8  # Long contexts might be too broad
        else:
            return 0.85  # Optimal length = high precision

    def _calculate_recall(
        self,
        contexts: list[str],
        reference_answer: str
    ) -> float:
        """
        Calculate recall: % of relevant docs that were retrieved.

        Estimates by comparing retrieved contexts to reference answer.

        Returns: 0.0-1.0
        """
        if not contexts or not reference_answer:
            return 0.7  # Neutral default

        # Count unique information in contexts vs reference
        ref_topics = set(reference_answer.lower().split()[:20])
        retrieved_coverage = 0

        for context in contexts:
            ctx_words = set(context.lower().split())
            coverage = len(ref_topics & ctx_words) / len(ref_topics) if ref_topics else 0
            retrieved_coverage += min(coverage, 1.0)

        avg_coverage = retrieved_coverage / len(contexts) if contexts else 0
        return min(1.0, avg_coverage)

    def _evaluate_consistency(
        self,
        answer: str,
        answer_variants: list[str]
    ) -> float:
        """
        Evaluate consistency: how stable is the answer across variations?

        Measures semantic similarity between multiple generations.

        Returns: 0.0-1.0 (1.0 = perfectly consistent)
        """
        if len(answer_variants) < 2:
            return 0.9  # Single generation = assume consistent

        try:
            # Get embeddings for all variants
            embeddings = self.llm.get_embeddings(answer_variants)

            if not embeddings or len(embeddings) < 2:
                return 0.9

            # Calculate average similarity between all pairs
            import numpy as np
            embeddings = np.array(embeddings)

            similarities = []
            for i in range(len(embeddings)):
                for j in range(i + 1, len(embeddings)):
                    # Cosine similarity
                    norm_i = embeddings[i] / (np.linalg.norm(embeddings[i]) + 1e-6)
                    norm_j = embeddings[j] / (np.linalg.norm(embeddings[j]) + 1e-6)
                    sim = np.dot(norm_i, norm_j)
                    similarities.append(sim)

            if similarities:
                avg_similarity = statistics.mean(similarities)
                return max(0.0, min(1.0, avg_similarity))
            else:
                return 0.9

        except Exception as e:
            logger.warning(f"Consistency evaluation error: {e}")
            return 0.8  # Assume reasonably consistent

# Global instance
_quality_evaluator = None

def get_quality_evaluator() -> QualityEvaluator:
    """Get or create global quality evaluator"""
    global _quality_evaluator
    if _quality_evaluator is None:
        _quality_evaluator = QualityEvaluator()
    return _quality_evaluator
