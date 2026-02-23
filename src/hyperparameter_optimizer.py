"""
Phase 12.2: Hyperparameter Optimization Framework

Grid search and Bayesian optimization for RAG parameters.
Supports A/B testing and configuration comparison.
"""

import logging
import itertools
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
import time

logger = logging.getLogger(__name__)


@dataclass
class HyperparameterConfig:
    """Configuration for RAG system tuning"""
    chunk_size: int = 512  # Chunk size for document splitting
    top_k: int = 5  # Number of documents to retrieve
    similarity_threshold: float = 0.3  # Minimum relevance threshold
    alpha: float = 0.5  # BM25 (0) vs Vector (1) weighting
    temperature: float = 0.7  # LLM temperature for generation
    max_context_tokens: int = 2000  # Maximum context length
    rerank_batch_size: int = 10  # Batch size for reranking
    cache_ttl_seconds: int = 3600  # Cache time-to-live


@dataclass
class OptimizationResult:
    """Result of parameter optimization"""
    config: HyperparameterConfig
    metric_score: float  # Quality/latency/cost metric
    quality_score: float  # Answer quality (0-1)
    latency_ms: float  # Response latency
    cost_dollars: float  # API cost estimate
    evaluation_time_ms: float = 0.0


class GridSearchOptimizer:
    """
    Exhaustive grid search over parameter space.

    Parameters tested:
    - chunk_size: [256, 512, 1024, 2048]
    - top_k: [3, 5, 7, 10]
    - similarity_threshold: [0.3, 0.5, 0.7]
    - alpha: [0.3, 0.5, 0.7]
    - temperature: [0.3, 0.7]

    Total combinations: 4 * 4 * 3 * 3 * 2 = 288 configurations
    """

    def __init__(self, evaluation_function):
        """
        Initialize optimizer.

        Args:
            evaluation_function: Function that takes config and returns metrics
        """
        self.evaluate = evaluation_function
        self.results: List[OptimizationResult] = []

    def search(
        self,
        param_grid: Dict[str, List[Any]],
        sample_queries: List[str],
        metric: str = "quality_score"
    ) -> List[OptimizationResult]:
        """
        Perform exhaustive grid search.

        Args:
            param_grid: Parameter space to search
            sample_queries: Sample queries for evaluation
            metric: Metric to optimize ("quality_score", "latency_ms", "cost_dollars")

        Returns:
            Sorted list of results (best first)
        """
        # Generate all combinations
        param_names = list(param_grid.keys())
        param_values = [param_grid[name] for name in param_names]

        total_combinations = 1
        for vals in param_values:
            total_combinations *= len(vals)

        logger.info(f"Starting grid search over {total_combinations} configurations...")

        self.results = []
        evaluated = 0

        for values in itertools.product(*param_values):
            # Create config from this combination
            config_dict = dict(zip(param_names, values))
            config = self._create_config(config_dict)

            # Evaluate this configuration
            start = time.perf_counter()
            try:
                result = self.evaluate(config, sample_queries)
                elapsed_ms = (time.perf_counter() - start) * 1000
                result.evaluation_time_ms = elapsed_ms

                self.results.append(result)
                evaluated += 1

                if evaluated % max(1, total_combinations // 10) == 0:
                    logger.info(
                        f"Evaluated {evaluated}/{total_combinations} "
                        f"({100*evaluated/total_combinations:.0f}%) - "
                        f"Best {metric}: {self._get_best_score(metric):.3f}"
                    )

            except Exception as e:
                logger.warning(f"Failed to evaluate config {config_dict}: {e}")
                continue

        # Sort by metric (ascending for latency/cost, descending for quality)
        reverse = metric == "quality_score"
        self.results.sort(
            key=lambda r: getattr(r, metric),
            reverse=reverse
        )

        logger.info(
            f"Grid search complete. Best {metric}: {self._get_best_score(metric):.3f}"
        )

        return self.results

    def get_best_config(self, metric: str = "quality_score") -> HyperparameterConfig:
        """Get best configuration for metric"""
        if not self.results:
            logger.warning("No results available, returning default config")
            return HyperparameterConfig()

        reverse = metric == "quality_score"
        best = max(
            self.results,
            key=lambda r: getattr(r, metric) if not reverse else -getattr(r, metric)
        )
        return best.config

    def get_top_k_configs(
        self,
        k: int = 5,
        metric: str = "quality_score"
    ) -> List[HyperparameterConfig]:
        """Get top K configurations"""
        if not self.results:
            return [HyperparameterConfig()]

        reverse = metric == "quality_score"
        sorted_results = sorted(
            self.results,
            key=lambda r: getattr(r, metric),
            reverse=reverse
        )
        return [r.config for r in sorted_results[:k]]

    def _create_config(self, param_dict: Dict) -> HyperparameterConfig:
        """Create config object from parameter dict"""
        config = HyperparameterConfig()
        for key, value in param_dict.items():
            if hasattr(config, key):
                setattr(config, key, value)
        return config

    def _get_best_score(self, metric: str) -> float:
        """Get best score for metric"""
        if not self.results:
            return 0.0
        reverse = metric == "quality_score"
        best = max(
            self.results,
            key=lambda r: getattr(r, metric) if not reverse else -getattr(r, metric)
        )
        return getattr(best, metric)


class ConfigurationHistory:
    """Tracks all tested configurations and their performance"""

    def __init__(self):
        """Initialize history"""
        self.history: List[OptimizationResult] = []
        self.best_configs: Dict[str, HyperparameterConfig] = {}

    def record(self, result: OptimizationResult, metric: str):
        """Record a configuration evaluation"""
        self.history.append(result)

        # Update best for this metric
        if metric not in self.best_configs:
            self.best_configs[metric] = result.config
        else:
            best_result = max(
                (r for r in self.history if r.metric_score is not None),
                key=lambda r: r.metric_score
            )
            self.best_configs[metric] = best_result.config

    def get_history_for_metric(
        self,
        metric: str,
        limit: Optional[int] = None
    ) -> List[OptimizationResult]:
        """Get history sorted by metric"""
        reverse = metric == "quality_score"
        sorted_history = sorted(
            self.history,
            key=lambda r: getattr(r, metric),
            reverse=reverse
        )
        if limit:
            return sorted_history[:limit]
        return sorted_history

    def export_history(self, filepath: str):
        """Export history to JSON file"""
        import json

        data = []
        for result in self.history:
            data.append({
                "config": {
                    "chunk_size": result.config.chunk_size,
                    "top_k": result.config.top_k,
                    "similarity_threshold": result.config.similarity_threshold,
                    "alpha": result.config.alpha,
                    "temperature": result.config.temperature,
                    "max_context_tokens": result.config.max_context_tokens,
                    "rerank_batch_size": result.config.rerank_batch_size,
                    "cache_ttl_seconds": result.config.cache_ttl_seconds,
                },
                "metrics": {
                    "quality_score": result.quality_score,
                    "latency_ms": result.latency_ms,
                    "cost_dollars": result.cost_dollars,
                    "evaluation_time_ms": result.evaluation_time_ms,
                }
            })

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        logger.info(f"Exported {len(data)} configurations to {filepath}")


# Global instance
_optimizer = None
_history = None


def get_grid_search_optimizer(eval_func) -> GridSearchOptimizer:
    """Get or create grid search optimizer"""
    global _optimizer
    if _optimizer is None:
        _optimizer = GridSearchOptimizer(eval_func)
    return _optimizer


def get_configuration_history() -> ConfigurationHistory:
    """Get or create configuration history"""
    global _history
    if _history is None:
        _history = ConfigurationHistory()
    return _history
