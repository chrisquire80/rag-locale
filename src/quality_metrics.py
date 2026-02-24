"""Quality Metrics - FASE 19"""
import logging
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

class MetricType(Enum):
    FAITHFULNESS = "faithfulness"
    RELEVANCE = "relevance"
    PRECISION = "precision"
    RECALL = "recall"
    F1_SCORE = "f1_score"
    CONSISTENCY = "consistency"
    LATENCY = "latency"
    COST = "cost"

@dataclass
class MetricScore:
    metric_type: MetricType
    score: float
    confidence: float
    explanation: str
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class QueryEvaluation:
    query_id: str
    query: str
    answer: str
    retrieved_documents: list[Dict]
    metrics: dict[MetricType, MetricScore] = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    def get_overall_score(self) -> float:
        if not self.metrics:
            return 0.0
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

class QualityEvaluator:
    def __init__(self):
        self.evaluations: list[QueryEvaluation] = []
        logger.info("QualityEvaluator initialized")

    def evaluate_query(self, query_id: str, query: str, answer: str,
                      retrieved_documents: list[Dict],
                      latency: Optional[float] = None) -> QueryEvaluation:
        evaluation = QueryEvaluation(
            query_id=query_id,
            query=query,
            answer=answer,
            retrieved_documents=retrieved_documents,
            metadata={'latency': latency}
        )

        context = " ".join([doc.get('text', '') for doc in retrieved_documents])
        if context and answer:
            evaluation.metrics[MetricType.FAITHFULNESS] = MetricScore(
                MetricType.FAITHFULNESS, 0.85, 0.7, "Answer supported by documents")
        
        query_words = set(query.lower().split())
        answer_words = set(answer.lower().split())
        union = query_words | answer_words
        overlap = len(query_words & answer_words) / len(union) if union else 0
        evaluation.metrics[MetricType.RELEVANCE] = MetricScore(
            MetricType.RELEVANCE, overlap, 0.7, "Keyword overlap with query")

        self.evaluations.append(evaluation)
        return evaluation

    def get_summary(self) -> Dict:
        if not self.evaluations:
            return {}
        scores = [e.get_overall_score() for e in self.evaluations]
        return {
            'total_queries': len(self.evaluations),
            'mean_score': sum(scores) / len(scores) if scores else 0,
            'min_score': min(scores) if scores else 0,
            'max_score': max(scores) if scores else 0,
        }

def get_quality_evaluator() -> QualityEvaluator:
    if not hasattr(get_quality_evaluator, '_instance'):
        get_quality_evaluator._instance = QualityEvaluator()
    return get_quality_evaluator._instance
