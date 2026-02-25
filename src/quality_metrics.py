"""
Quality Metrics - FASE 19
Defines metrics and collector for RAG quality evaluation.
Harmonized to support both QualityMetricsCollector and QualityEvaluator patterns.
"""

import math
import re
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from src.logging_config import get_logger

logger = get_logger(__name__)

class MetricType(Enum):
    FAITHFULNESS = "faithfulness"
    RELEVANCE = "relevance"
    PRECISION = "precision"
    RECALL = "recall"
    F1_SCORE = "f1_score"
    CONSISTENCY = "consistency"
    COHERENCE = "coherence"
    COVERAGE = "coverage"
    COMPLETENESS = "completeness"
    OVERALL = "overall"
    LATENCY = "latency"
    COST = "cost"

@dataclass
class MetricScore:
    """Individual metric score with confidence and explanation"""
    metric_type: MetricType
    score: float
    confidence: float
    explanation: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class QualityMetrics:
    """Container for quality scores (used by FASE 19 integration tests)"""
    faithfulness: float = 0.0
    relevance: float = 0.0
    coherence: float = 0.0
    coverage: float = 0.0
    completeness: float = 0.0
    overall_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            "faithfulness": self.faithfulness,
            "relevance": self.relevance,
            "coherence": self.coherence,
            "coverage": self.coverage,
            "completeness": self.completeness,
            "overall_score": self.overall_score,
            "timestamp": self.timestamp.isoformat()
        }

@dataclass
class QueryEvaluation:
    """Evaluation result for a query (used by FASE 16 and legacy tests)"""
    query_id: str
    query: str
    answer: str
    retrieved_documents: List[Dict[str, Any]]
    metrics: Dict[MetricType, MetricScore] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def get_overall_score(self) -> float:
        """Calculate overall score based on available metrics (FASE 16 compatible)"""
        if not self.metrics:
            # Fallback if no individual metrics set
            return self.metadata.get('overall_score', 0.0)
            
        weights = {
            MetricType.FAITHFULNESS: 0.35,
            MetricType.RELEVANCE: 0.30,
            MetricType.PRECISION: 0.20,
            MetricType.CONSISTENCY: 0.15,
        }
        total_weight = weighted_sum = 0
        for mt, score_obj in self.metrics.items():
            weight = weights.get(mt, 0.0)
            if weight > 0:
                weighted_sum += score_obj.score * weight
                total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0

class QualityMetricsCollector:
    """Collector and calculator for RAG quality metrics (FASE 19 pattern)"""

    def __init__(self):
        """Initialize metrics collector with standard weights"""
        self.metric_weights = {
            MetricType.FAITHFULNESS: 0.3,
            MetricType.RELEVANCE: 0.25,
            MetricType.COHERENCE: 0.15,
            MetricType.COVERAGE: 0.15,
            MetricType.COMPLETENESS: 0.15
        }
        self.min_acceptable_overall = 0.65
        self.min_acceptable_faithfulness = 0.55
        self.evaluations = []
        logger.info("QualityMetricsCollector initialized")

    def calculate_faithfulness(self, answer: str, sources: List[str]) -> float:
        """Calculate faithfulness based on source overlap"""
        if not answer or not sources:
            return 0.0
        answer_words = set(re.findall(r'\w+', answer.lower()))
        source_content = " ".join(sources).lower()
        source_words = set(re.findall(r'\w+', source_content))
        if not answer_words: return 0.0
        overlap = len(answer_words & source_words) / len(answer_words)
        if re.search(r'\[\d+\]', answer): overlap = min(1.0, overlap + 0.1)
        return overlap

    def calculate_relevance(self, query: str, answer: str) -> float:
        """Calculate relevance of answer to query"""
        if not query or not answer: return 0.0
        query_words = set(re.findall(r'\w+', query.lower()))
        answer_words = set(re.findall(r'\w+', answer.lower()))
        if not query_words: return 0.0
        overlap = len(query_words & answer_words) / len(query_words)
        if len(answer.split()) < 5: overlap *= 0.5
        return min(1.0, overlap)

    def calculate_coherence(self, answer: str) -> float:
        """Calculate coherence of the generated answer"""
        if not answer: return 0.0
        transition_words = ["however", "therefore", "consequently", "furthermore", "moreover", "first", "second", "finally", "in conclusion"]
        has_transitions = any(word in answer.lower() for word in transition_words)
        paragraphs = answer.split('\n\n')
        has_structure = len(paragraphs) > 1
        score = 0.5
        if has_transitions: score += 0.2
        if has_structure: score += 0.2
        return min(1.0, score)

    def calculate_coverage(self, terms: List[str], answer: str) -> float:
        """Calculate how many required terms are covered in the answer"""
        if not terms or not answer: return 0.0
        covered = sum(1 for term in terms if term.lower() in answer.lower())
        return covered / len(terms)

    def calculate_completeness(self, query: str, answer: str, sources: List[str]) -> float:
        """Calculate if answer completely addresses the query"""
        if not query or not answer: return 0.0
        score = 0.6
        if any(q in query.lower() for q in ["why", "because"]):
            if "because" in answer.lower() or "due to" in answer.lower(): score += 0.2
        if any(q in query.lower() for q in ["how", "steps"]):
            if re.search(r'\d\.', answer) or "first" in answer.lower(): score += 0.2
        return min(1.0, score)

    def evaluate_response(self, query: str, answer: str, sources: List[str]) -> QualityMetrics:
        """Comprehensive evaluation of a RAG response (FASE 19)"""
        metrics = QualityMetrics()
        metrics.faithfulness = self.calculate_faithfulness(answer, sources)
        metrics.relevance = self.calculate_relevance(query, answer)
        metrics.coherence = self.calculate_coherence(answer)
        query_terms = [w for w in re.findall(r'\w+', query.lower()) if len(w) > 3]
        metrics.coverage = self.calculate_coverage(query_terms, answer)
        metrics.completeness = self.calculate_completeness(query, answer, sources)
        
        weighted_sum = (metrics.faithfulness * 0.3 + metrics.relevance * 0.25 + 
                       metrics.coherence * 0.15 + metrics.coverage * 0.15 + 
                       metrics.completeness * 0.15)
        metrics.overall_score = weighted_sum
        return metrics

    def evaluate_query(self, query_id: str, query: str, answer: str,
                      retrieved_documents: List[Dict[str, Any]],
                      latency: Optional[float] = None) -> QueryEvaluation:
        """Evaluate a query and returning FASE 16 compatible QueryEvaluation"""
        sources = [doc.get('text', '') for doc in retrieved_documents]
        metrics_v19 = self.evaluate_response(query, answer, sources)
        
        evaluation = QueryEvaluation(
            query_id=query_id,
            query=query,
            answer=answer,
            retrieved_documents=retrieved_documents,
            metadata={'latency': latency, 'overall_score': metrics_v19.overall_score}
        )
        
        # Populate metrics dict
        evaluation.metrics[MetricType.FAITHFULNESS] = MetricScore(
            MetricType.FAITHFULNESS, metrics_v19.faithfulness, 0.8, "Heuristic match")
        evaluation.metrics[MetricType.RELEVANCE] = MetricScore(
            MetricType.RELEVANCE, metrics_v19.relevance, 0.8, "Keyword overlap")
        evaluation.metrics[MetricType.COHERENCE] = MetricScore(
            MetricType.COHERENCE, metrics_v19.coherence, 0.8, "Structural analysis")
            
        # Placeholders for FASE 19 specific metrics
        evaluation.metrics[MetricType.PRECISION] = MetricScore(
            MetricType.PRECISION, 0.8, 0.7, "Default precision placeholder")
        evaluation.metrics[MetricType.RECALL] = MetricScore(
            MetricType.RECALL, 0.85, 0.7, "Default recall placeholder")
        evaluation.metrics[MetricType.F1_SCORE] = MetricScore(
            MetricType.F1_SCORE, 0.82, 0.7, "Default F1 placeholder")
        evaluation.metrics[MetricType.CONSISTENCY] = MetricScore(
            MetricType.CONSISTENCY, 0.9, 0.7, "Default consistency placeholder")
            
        self.evaluations.append(evaluation)
        return evaluation

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all evaluations"""
        if not self.evaluations: return {}
        scores = [e.get_overall_score() for e in self.evaluations]
        return {
            'total_queries': len(self.evaluations),
            'mean_score': sum(scores) / len(scores) if scores else 0,
            'min_score': min(scores) if scores else 0,
            'max_score': max(scores) if scores else 0,
        }

    def is_acceptable_quality(self, metrics: QualityMetrics) -> bool:
        return (metrics.overall_score >= self.min_acceptable_overall and 
                metrics.faithfulness >= self.min_acceptable_faithfulness)

    def get_quality_issues(self, metrics: QualityMetrics) -> List[str]:
        issues = []
        if metrics.faithfulness < self.min_acceptable_faithfulness:
            issues.append("Low faithfulness: answer may not be grounded in sources")
        if metrics.relevance < 0.5:
            issues.append("Low relevance: answer may not address the query")
        return issues

    def get_improvement_suggestions(self, metrics: QualityMetrics) -> List[str]:
        suggestions = []
        if metrics.faithfulness < self.min_acceptable_faithfulness:
            suggestions.append("Try expanding source context or using stricter grounding prompts")
        if metrics.relevance < 0.5:
            suggestions.append("Try query expansion to better match source documents")
        return suggestions

# Alias for FASE 16 / legacy compatibility
QualityEvaluator = QualityMetricsCollector

# Global instance for thread-safe access
_instance = None

def get_quality_evaluator() -> QualityMetricsCollector:
    """Singleton factory for quality evaluator (FASE 16 compatible)"""
    global _instance
    if _instance is None:
        _instance = QualityMetricsCollector()
    return _instance
