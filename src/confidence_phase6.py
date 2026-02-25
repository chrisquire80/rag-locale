"""
Confidence Scoring - Phase 6 Feature 2
Calculate and display response confidence based on source quality
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
import statistics

from src.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ConfidenceMetrics:
    """Confidence scoring information"""

    confidence_score: float  # 0.0-1.0
    confidence_level: str  # "High", "Medium", "Low"
    confidence_emoji: str  # 🟢, 🟡, 🔴
    explanation: str  # Human-readable explanation
    num_sources: int  # Number of sources
    source_score_range: tuple  # (min, max) of source scores


class ConfidenceCalculator:
    """Calculates confidence of RAG responses"""

    def __init__(self):
        """Initialize confidence calculator"""
        self.high_threshold = 0.75  # > 75% = High confidence
        self.medium_threshold = 0.50  # 50-75% = Medium confidence
        logger.info("Initialized ConfidenceCalculator")

    def calculate_response_confidence(
        self, sources: List[Dict]
    ) -> float:
        """
        Calculate confidence score for response based on source quality

        Args:
            sources: List of retrieved sources with similarity scores

        Returns:
            Confidence score (0.0-1.0)
        """
        if not sources:
            return 0.0

        # Extract similarity scores from sources
        scores = []
        for source in sources:
            score = source.get("score") or source.get("similarity_score", 0.0)
            if isinstance(score, (int, float)):
                scores.append(float(score))

        if not scores:
            return 0.0

        # Calculate average similarity score
        avg_score = statistics.mean(scores)

        # Boost score if many high-quality sources
        num_high_quality = sum(1 for s in scores if s > 0.8)
        if num_high_quality >= 3:
            # Multiple excellent sources = high confidence
            avg_score = min(1.0, avg_score * 1.1)

        # Penalize if scores are inconsistent (high variance = uncertainty)
        if len(scores) > 1:
            stdev = statistics.stdev(scores)
            if stdev > 0.3:
                # High variance = reduce confidence
                avg_score = max(0.0, avg_score - stdev * 0.2)

        return round(min(1.0, max(0.0, avg_score)), 2)

    def get_confidence_level(self, confidence_score: float) -> str:
        """
        Get confidence level string

        Args:
            confidence_score: Score from 0.0-1.0

        Returns:
            "High", "Medium", or "Low"
        """
        if confidence_score >= self.high_threshold:
            return "High"
        elif confidence_score >= self.medium_threshold:
            return "Medium"
        else:
            return "Low"

    def get_confidence_emoji(self, confidence_score: float) -> str:
        """
        Get emoji representation of confidence

        Args:
            confidence_score: Score from 0.0-1.0

        Returns:
            "🟢" (high), "🟡" (medium), or "🔴" (low)
        """
        level = self.get_confidence_level(confidence_score)
        emoji_map = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}
        return emoji_map.get(level, "⚪")

    def rank_sources(self, sources: List[Dict]) -> List[Dict]:
        """
        Rank sources by relevance score (highest first)

        Args:
            sources: List of sources

        Returns:
            Sorted sources by score (descending)
        """
        def get_score(source):
            return source.get("score") or source.get("similarity_score", 0.0)

        sorted_sources = sorted(sources, key=get_score, reverse=True)
        logger.debug(f"Ranked {len(sources)} sources by score")
        return sorted_sources

    def generate_confidence_explanation(
        self, sources: List[Dict], confidence_score: float
    ) -> str:
        """
        Generate human-readable confidence explanation

        Args:
            sources: List of sources
            confidence_score: Calculated confidence score

        Returns:
            Explanation string
        """
        if not sources:
            return "No sources found for this query."

        level = self.get_confidence_level(confidence_score)
        num_sources = len(sources)

        scores = []
        for source in sources:
            score = source.get("score") or source.get("similarity_score", 0.0)
            if isinstance(score, (int, float)):
                scores.append(score)

        avg_score = statistics.mean(scores) if scores else 0.0

        if level == "High":
            if num_sources >= 3:
                return f"High confidence due to {num_sources} high-quality matching sources (avg match: {avg_score:.0%})"
            else:
                return f"High confidence based on excellent source match ({avg_score:.0%})"
        elif level == "Medium":
            return f"Medium confidence with {num_sources} relevant sources (avg match: {avg_score:.0%})"
        else:
            return f"⚠️ Low confidence - only {num_sources} source(s) found, suggest verifying with additional context"

    def calculate_source_confidence_bar(self, source_score: float) -> str:
        """
        Generate visual confidence bar for individual source

        Args:
            source_score: Score from 0.0-1.0

        Returns:
            Visual bar (█░░░░)
        """
        filled = int(round(source_score * 5))
        empty = 5 - filled
        return "█" * filled + "░" * empty

    def get_confidence_metrics(
        self, sources: List[Dict]
    ) -> ConfidenceMetrics:
        """
        Get complete confidence metrics

        Args:
            sources: List of sources with scores

        Returns:
            ConfidenceMetrics with all information
        """
        confidence_score = self.calculate_response_confidence(sources)
        confidence_level = self.get_confidence_level(confidence_score)
        confidence_emoji = self.get_confidence_emoji(confidence_score)
        explanation = self.generate_confidence_explanation(sources, confidence_score)

        scores = []
        for source in sources:
            score = source.get("score") or source.get("similarity_score", 0.0)
            if isinstance(score, (int, float)):
                scores.append(score)

        source_score_range = (
            min(scores) if scores else 0.0,
            max(scores) if scores else 0.0,
        )

        return ConfidenceMetrics(
            confidence_score=confidence_score,
            confidence_level=confidence_level,
            confidence_emoji=confidence_emoji,
            explanation=explanation,
            num_sources=len(sources),
            source_score_range=source_score_range,
        )
