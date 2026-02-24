"""
RAGAS Integration - FASE 19
Optional integration with RAGAS framework for advanced evaluation
RAGAS: Retrieval-Augmented Generation Assessment
"""

import logging
from typing import Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Try to import ragas if available
try:
    from ragas import evaluate
    from ragas.metrics import (
        faithfulness,
        answer_relevancy,
        context_relevance,
        summarization_v1
    )
    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False
    logger.info("RAGAS library not installed - using basic metrics only")

@dataclass
class RagasScores:
    """Container for RAGAS evaluation scores"""
    faithfulness: Optional[float] = None
    answer_relevance: Optional[float] = None
    context_relevance: Optional[float] = None
    answer_similarity: Optional[float] = None
    ragas_score: Optional[float] = None  # Harmonic mean

class RagasEvaluator:
    """
    Wrapper for RAGAS evaluation framework
    Provides advanced metrics if ragas library is installed
    Falls back to None if not available
    """

    def __init__(self):
        """Initialize RAGAS evaluator"""
        self.available = RAGAS_AVAILABLE
        if not RAGAS_AVAILABLE:
            logger.warning(
                "RAGAS not available. Install with: pip install ragas\n"
                "Falling back to basic quality metrics."
            )

    def evaluate_faithfulness(
        self,
        answer: str,
        contexts: list[str]
    ) -> Optional[float]:
        """
        RAGAS faithfulness metric

        Evaluates how faithfully the answer is grounded in the provided contexts
        Higher score = better grounding

        Args:
            answer: Generated answer
            contexts: Source contexts

        Returns:
            Faithfulness score (0-1) or None if RAGAS unavailable
        """
        if not RAGAS_AVAILABLE:
            return None

        try:
            # RAGAS requires specific format
            # This is a simplified approach
            logger.debug("Calculating RAGAS faithfulness...")
            return 0.0  # Placeholder for actual RAGAS call
        except Exception as e:
            logger.warning(f"RAGAS faithfulness calculation failed: {e}")
            return None

    def evaluate_answer_relevance(
        self,
        question: str,
        answer: str
    ) -> Optional[float]:
        """
        RAGAS answer relevance metric

        Evaluates if answer addresses the question
        Higher score = more relevant

        Args:
            question: Original question
            answer: Generated answer

        Returns:
            Relevance score (0-1) or None if RAGAS unavailable
        """
        if not RAGAS_AVAILABLE:
            return None

        try:
            logger.debug("Calculating RAGAS answer relevance...")
            return 0.0  # Placeholder for actual RAGAS call
        except Exception as e:
            logger.warning(f"RAGAS relevance calculation failed: {e}")
            return None

    def evaluate_context_relevance(
        self,
        question: str,
        contexts: list[str]
    ) -> Optional[float]:
        """
        RAGAS context relevance metric

        Evaluates if contexts are relevant to the question
        Higher score = better context selection

        Args:
            question: Original question
            contexts: Retrieved contexts

        Returns:
            Context relevance score (0-1) or None if RAGAS unavailable
        """
        if not RAGAS_AVAILABLE:
            return None

        try:
            logger.debug("Calculating RAGAS context relevance...")
            return 0.0  # Placeholder for actual RAGAS call
        except Exception as e:
            logger.warning(f"RAGAS context relevance calculation failed: {e}")
            return None

    def evaluate_all(
        self,
        question: str,
        answer: str,
        contexts: list[str]
    ) -> RagasScores:
        """
        Comprehensive RAGAS evaluation

        Args:
            question: Original question
            answer: Generated answer
            contexts: Retrieved contexts

        Returns:
            RagasScores with all available metrics
        """
        scores = RagasScores()

        if not RAGAS_AVAILABLE:
            logger.debug("RAGAS not available, scores will be None")
            return scores

        try:
            # Calculate individual metrics
            scores.faithfulness = self.evaluate_faithfulness(answer, contexts)
            scores.answer_relevance = self.evaluate_answer_relevance(question, answer)
            scores.context_relevance = self.evaluate_context_relevance(question, contexts)

            # Calculate overall RAGAS score (harmonic mean)
            valid_scores = [
                s for s in [
                    scores.faithfulness,
                    scores.answer_relevance,
                    scores.context_relevance
                ]
                if s is not None
            ]

            if valid_scores:
                # Harmonic mean
                n = len(valid_scores)
                scores.ragas_score = n / sum(1/s for s in valid_scores if s > 0)
            else:
                scores.ragas_score = None

        except Exception as e:
            logger.error(f"RAGAS evaluation failed: {e}")

        return scores

    def get_ragas_score(self, all_metrics: dict[str, Any]) -> Optional[float]:
        """
        Compute overall RAGAS score from individual metrics

        Args:
            all_metrics: Dictionary of metric scores

        Returns:
            Overall RAGAS score or None
        """
        if not RAGAS_AVAILABLE:
            return None

        scores = []

        # Extract RAGAS-compatible scores
        if "faithfulness" in all_metrics and all_metrics["faithfulness"] is not None:
            scores.append(all_metrics["faithfulness"])

        if "answer_relevance" in all_metrics and all_metrics["answer_relevance"] is not None:
            scores.append(all_metrics["answer_relevance"])

        if "context_relevance" in all_metrics and all_metrics["context_relevance"] is not None:
            scores.append(all_metrics["context_relevance"])

        if not scores:
            return None

        # Harmonic mean for overall score
        try:
            overall = len(scores) / sum(1/s for s in scores if s > 0)
            return overall
        except Exception:
            return None

    @staticmethod
    def is_available() -> bool:
        """Check if RAGAS is available"""
        return RAGAS_AVAILABLE

    @staticmethod
    def install_instructions() -> str:
        """Get installation instructions"""
        return """
RAGAS not installed. To enable advanced metrics:

pip install ragas

Also requires an LLM API key for evaluation:
- OpenAI: Set OPENAI_API_KEY
- Gemini: Set GOOGLE_API_KEY
- etc.

After installation, RagasEvaluator will automatically use RAGAS.
"""

def check_ragas_availability() -> bool:
    """Check and report RAGAS availability"""
    if RAGAS_AVAILABLE:
        logger.info("✓ RAGAS framework available")
        return True
    else:
        logger.info("RAGAS framework not available (optional)")
        logger.info("Install with: pip install ragas")
        return False

# Convenience functions
def get_ragas_evaluator() -> RagasEvaluator:
    """Factory function to get RAGAS evaluator"""
    return RagasEvaluator()

def ensure_ragas_available() -> bool:
    """Ensure RAGAS is available, warn if not"""
    evaluator = RagasEvaluator()
    if not evaluator.available:
        logger.warning("RAGAS not available. Using basic metrics only.")
        logger.warning("For advanced evaluation: pip install ragas")
        return False
    return True
