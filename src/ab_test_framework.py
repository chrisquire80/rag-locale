"""
Phase 12.2: A/B Testing Framework

Systematic comparison of two configurations.
Supports statistical significance testing and sample size calculation.
"""

import secrets
from typing import List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from src.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class ABTestRequest:
    """A single request in an A/B test"""
    query: str
    assigned_config: str  # 'A' or 'B'
    answer: str
    quality_score: float
    latency_ms: float
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ABTestResult:
    """Result of A/B test comparison"""
    config_a_name: str
    config_b_name: str

    # Sample sizes
    total_samples: int
    samples_a: int
    samples_b: int

    # Quality metrics
    quality_a_mean: float
    quality_b_mean: float
    quality_a_std: float
    quality_b_std: float

    # Latency metrics
    latency_a_mean: float
    latency_b_mean: float
    latency_a_std: float
    latency_b_std: float

    # Statistical significance
    quality_t_statistic: float = 0.0
    quality_p_value: float = 1.0
    quality_significant: bool = False

    latency_t_statistic: float = 0.0
    latency_p_value: float = 1.0
    latency_significant: bool = False

    # Winner
    winner: Optional[str] = None  # 'A', 'B', or None (tie)
    confidence: float = 0.0  # Confidence in winner (0-1)

class ABTestRunner:
    """
    Runs A/B tests comparing two configurations.

    Statistical approach:
    1. Route requests to A or B based on split_ratio
    2. Collect metrics for each variant
    3. Perform t-test for statistical significance
    4. Determine winner based on metric and p-value
    """

    def __init__(self, config_a, config_b, split_ratio: float = 0.5):
        """
        Initialize A/B test.

        Args:
            config_a: Configuration A
            config_b: Configuration B
            split_ratio: Fraction of traffic to send to A (rest goes to B)
        """
        self.config_a = config_a
        self.config_b = config_b
        self.split_ratio = split_ratio

        self.requests: List[ABTestRequest] = []
        self.config_a_name = getattr(config_a, 'name', 'Config A')
        self.config_b_name = getattr(config_b, 'name', 'Config B')

    def route_request(self) -> str:
        """Randomly route request to A or B based on split ratio"""
        return 'A' if secrets.SystemRandom().random() < self.split_ratio else 'B'

    def record_request(
        self,
        query: str,
        assigned_config: str,
        answer: str,
        quality_score: float,
        latency_ms: float
    ):
        """Record a request result"""
        request = ABTestRequest(
            query=query,
            assigned_config=assigned_config,
            answer=answer,
            quality_score=quality_score,
            latency_ms=latency_ms
        )
        self.requests.append(request)

    def analyze(
        self,
        metric: str = "quality_score"
    ) -> ABTestResult:
        """
        Analyze A/B test results.

        Args:
            metric: "quality_score" or "latency_ms" to optimize for

        Returns:
            ABTestResult with statistical analysis
        """
        # Split requests by config
        requests_a = [r for r in self.requests if r.assigned_config == 'A']
        requests_b = [r for r in self.requests if r.assigned_config == 'B']

        samples_a = len(requests_a)
        samples_b = len(requests_b)
        total_samples = samples_a + samples_b

        if total_samples == 0:
            logger.warning("No data to analyze")
            return ABTestResult(
                config_a_name=self.config_a_name,
                config_b_name=self.config_b_name,
                total_samples=0,
                samples_a=0,
                samples_b=0,
                quality_a_mean=0.0,
                quality_b_mean=0.0,
                quality_a_std=0.0,
                quality_b_std=0.0,
                latency_a_mean=0.0,
                latency_b_mean=0.0,
                latency_a_std=0.0,
                latency_b_std=0.0,
            )

        # Calculate statistics
        quality_a = [r.quality_score for r in requests_a]
        quality_b = [r.quality_score for r in requests_b]
        latency_a = [r.latency_ms for r in requests_a]
        latency_b = [r.latency_ms for r in requests_b]

        quality_a_mean = sum(quality_a) / len(quality_a) if quality_a else 0.0
        quality_b_mean = sum(quality_b) / len(quality_b) if quality_b else 0.0

        latency_a_mean = sum(latency_a) / len(latency_a) if latency_a else 0.0
        latency_b_mean = sum(latency_b) / len(latency_b) if latency_b else 0.0

        quality_a_std = self._std_dev(quality_a, quality_a_mean)
        quality_b_std = self._std_dev(quality_b, quality_b_mean)

        latency_a_std = self._std_dev(latency_a, latency_a_mean)
        latency_b_std = self._std_dev(latency_b, latency_b_mean)

        # Perform t-tests
        quality_t, quality_p = self._t_test(
            quality_a, quality_a_mean, quality_a_std,
            quality_b, quality_b_mean, quality_b_std
        )

        latency_t, latency_p = self._t_test(
            latency_a, latency_a_mean, latency_a_std,
            latency_b, latency_b_mean, latency_b_std
        )

        # Determine winner
        quality_significant = quality_p < 0.05
        latency_significant = latency_p < 0.05

        if metric == "quality_score" and quality_significant:
            winner = 'A' if quality_a_mean > quality_b_mean else 'B'
            confidence = 1.0 - quality_p
        elif metric == "latency_ms" and latency_significant:
            winner = 'A' if latency_a_mean < latency_b_mean else 'B'
            confidence = 1.0 - latency_p
        else:
            winner = None
            confidence = 0.0

        return ABTestResult(
            config_a_name=self.config_a_name,
            config_b_name=self.config_b_name,
            total_samples=total_samples,
            samples_a=samples_a,
            samples_b=samples_b,
            quality_a_mean=quality_a_mean,
            quality_b_mean=quality_b_mean,
            quality_a_std=quality_a_std,
            quality_b_std=quality_b_std,
            latency_a_mean=latency_a_mean,
            latency_b_mean=latency_b_mean,
            latency_a_std=latency_a_std,
            latency_b_std=latency_b_std,
            quality_t_statistic=quality_t,
            quality_p_value=quality_p,
            quality_significant=quality_significant,
            latency_t_statistic=latency_t,
            latency_p_value=latency_p,
            latency_significant=latency_significant,
            winner=winner,
            confidence=confidence,
        )

    def calculate_required_sample_size(
        self,
        effect_size: float = 0.2,
        alpha: float = 0.05,
        power: float = 0.8
    ) -> int:
        """
        Calculate required sample size per variant.

        Uses standard power analysis formula.

        Args:
            effect_size: Expected effect size (Cohen's d)
            alpha: Significance level (default 0.05)
            power: Statistical power (default 0.8)

        Returns:
            Recommended samples per variant
        """
        # Simplified power analysis formula
        # n = 2 * (z_alpha/2 + z_beta)^2 / effect_size^2

        from math import sqrt, erfc

        # z-values for common alpha and power
        z_alpha = 1.96  # Two-tailed, alpha=0.05
        z_beta = 0.84   # Power=0.8

        n = 2 * ((z_alpha + z_beta) ** 2) / (effect_size ** 2)
        return int(n) + 1

    def _std_dev(self, values: List[float], mean: float) -> float:
        """Calculate standard deviation"""
        if len(values) < 2:
            return 0.0
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)

    def _t_test(
        self,
        group_a: List[float],
        mean_a: float,
        std_a: float,
        group_b: List[float],
        mean_b: float,
        std_b: float
    ) -> Tuple[float, float]:
        """
        Perform independent t-test.

        Returns: (t-statistic, p-value)
        """
        n_a = len(group_a)
        n_b = len(group_b)

        if n_a < 2 or n_b < 2:
            return 0.0, 1.0

        # Pooled standard error
        se = math.sqrt(
            (std_a ** 2 / n_a) + (std_b ** 2 / n_b)
        )

        if se == 0:
            return 0.0, 1.0

        # t-statistic
        t_stat = (mean_a - mean_b) / se

        # Degrees of freedom (Welch's approximation)
        _ = (
            ((std_a ** 2 / n_a + std_b ** 2 / n_b) ** 2) /
            ((std_a ** 2 / n_a) ** 2 / (n_a - 1) + (std_b ** 2 / n_b) ** 2 / (n_b - 1))
        )

        # Two-tailed p-value (approximate using normal distribution)
        from math import erf
        p_value = 1.0 - abs(erf(abs(t_stat) / math.sqrt(2)))

        return t_stat, p_value

# Global instance
_ab_test_runner = None

def create_ab_test(config_a, config_b, split_ratio: float = 0.5) -> ABTestRunner:
    """Create a new A/B test"""
    return ABTestRunner(config_a, config_b, split_ratio)
