"""
Response Confidence Scoring System
Calculates answer confidence based on source quality and relevance
"""

import statistics
from typing import Optional, List

from src.logging_config import get_logger

logger = get_logger(__name__)

class RetrievalResult:
    """Wrapper for retrieval results to access score attribute"""
    def __init__(self, obj=None):
        self.obj = obj

    def __getattr__(self, name):
        if self.obj and hasattr(self.obj, name):
            return getattr(self.obj, name)
        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")

class ConfidenceCalculator:
    """Calculate response confidence from source metrics"""

    def __init__(self):
        self.HIGH_THRESHOLD = 0.75  # 75%
        self.MEDIUM_THRESHOLD = 0.50  # 50%

    def calculate_response_confidence(self, sources: List) -> float:
        """
        Calculate confidence score (0-100) based on source quality.

        Factors:
        - Average similarity score of sources (primary factor)
        - Number of sources (more sources = higher confidence)
        - Score variance (high variance = lower confidence)

        Args:
            sources: List of RetrievalResult objects with .score attribute

        Returns:
            Float 0-100 representing confidence percentage
        """
        if not sources:
            return 0.0

        # Extract scores
        scores = []
        for source in sources:
            score = getattr(source, 'score', 0.0)
            if isinstance(score, (int, float)):
                scores.append(float(score))

        if not scores:
            return 0.0

        # Calculate base confidence from average score
        avg_score = statistics.mean(scores)
        base_confidence = avg_score * 100

        # Boost confidence based on number of sources
        # 1 source: 1x, 2 sources: 1.1x, 3+ sources: 1.2x
        if len(scores) >= 3:
            source_boost = 1.2
        elif len(scores) == 2:
            source_boost = 1.1
        else:
            source_boost = 1.0

        confidence = min(base_confidence * source_boost, 100.0)

        # Penalize high variance (inconsistent source quality)
        if len(scores) > 1:
            try:
                variance = statistics.variance(scores)
                std_dev = statistics.stdev(scores)
                # High variance reduces confidence
                if std_dev > 0.3:  # If std dev > 0.3, reduce confidence
                    variance_penalty = std_dev / 2  # Up to 0.15 penalty per point
                    confidence = max(confidence - (variance_penalty * 100), 0)
            except (statistics.StatisticsError, ValueError):
                pass

        return confidence

    def get_confidence_level(self, score: float) -> str:
        """
        Get confidence level label.

        Args:
            score: Confidence score 0-100

        Returns:
            "High", "Medium", or "Low"
        """
        if score >= self.HIGH_THRESHOLD * 100:
            return "High"
        elif score >= self.MEDIUM_THRESHOLD * 100:
            return "Medium"
        else:
            return "Low"

    def get_confidence_emoji(self, score: float) -> str:
        """
        Get emoji representation of confidence.

        Args:
            score: Confidence score 0-100

        Returns:
            Green circle, yellow circle, or red circle
        """
        level = self.get_confidence_level(score)
        emoji_map = {
            "High": "🟢",
            "Medium": "🟡",
            "Low": "🔴"
        }
        return emoji_map.get(level, "⚪")

    def rank_sources(self, sources: List) -> List:
        """
        Rank sources by relevance (score descending).

        Args:
            sources: List of RetrievalResult objects

        Returns:
            Sorted list with highest scores first
        """
        def get_score(source):
            score = getattr(source, 'score', 0.0)
            return float(score) if isinstance(score, (int, float)) else 0.0

        return sorted(sources, key=get_score, reverse=True)

    def generate_confidence_explanation(self, sources: List, confidence: float) -> str:
        """
        Generate human-readable explanation of confidence score.

        Args:
            sources: List of RetrievalResult objects
            confidence: Confidence score 0-100

        Returns:
            String explanation of the score
        """
        if not sources:
            return "No sources available - confidence cannot be determined"

        num_sources = len(sources)
        level = self.get_confidence_level(confidence)

        # Get score range
        scores = []
        for source in sources:
            score = getattr(source, 'score', 0.0)
            if isinstance(score, (int, float)):
                scores.append(float(score))

        if scores:
            min_score = min(scores)
            max_score = max(scores)
            avg_score = statistics.mean(scores)

            explanation = f"{level} confidence ({confidence:.0f}%) based on "
            explanation += f"{num_sources} source(s) with avg match score {avg_score:.2f} "
            explanation += f"(range: {min_score:.2f}-{max_score:.2f})"

            if confidence < 50:
                explanation += " - Consider verifying with additional sources"
        else:
            explanation = f"{level} confidence based on retrieved sources"

        return explanation

    def get_source_confidence_bar(self, score: float, width: int = 20) -> str:
        """
        Get a text-based confidence bar for a source.

        Args:
            score: Similarity score 0-1
            width: Width of the bar in characters

        Returns:
            Visual bar as text
        """
        percentage = int(score * 100)
        filled = int(width * score)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}] {percentage}%"
