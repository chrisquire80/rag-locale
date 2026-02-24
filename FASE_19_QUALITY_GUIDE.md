# FASE 19: Quality Metrics & Evaluation Guide

## Overview

FASE 19 implements comprehensive quality evaluation and improvement for RAG responses. It measures faithfulness, relevance, coherence, coverage, and completeness with automatic feedback loops to improve low-quality answers.

## Key Components

### 1. QualityMetrics (`src/quality_metrics.py`)

Core metrics collection and evaluation engine.

#### Metrics Explained

| Metric | Range | Meaning | Importance |
|--------|-------|---------|-----------|
| **Faithfulness** | 0-1 | Answer stays grounded in sources | Critical (35%) |
| **Relevance** | 0-1 | Answer addresses the query | Very High (25%) |
| **Coherence** | 0-1 | Answer structure and clarity | High (15%) |
| **Coverage** | 0-1 | Query terms present in answer | High (15%) |
| **Completeness** | 0-1 | Answer provides sufficient detail | Medium (10%) |
| **Overall Score** | 0-1 | Weighted average of all metrics | Used for decisions |

#### Calculation Methods

**Faithfulness**
```
- Extracts key claims from answer
- Checks if claims appear in source documents
- Calculates: (supported_claims / total_claims)
- Boosted if citations present
```

**Relevance**
```
- Matches query terms in answer
- Scores: (matched_terms / total_terms) * length_penalty
- Penalizes very short answers
- Boosts if question answered first
```

**Coherence**
```
- Scores based on:
  * Sentence count (3-15 sentences optimal)
  * Paragraph structure
  * Transition words
  * Lexical cohesion
  * Lists/formatting
```

**Coverage**
```
- Extracts important terms from query
- Counts matches in answer
- Scores: (covered_terms / total_terms)
- Bonus for term repetition
```

**Completeness**
```
- Checks question type (why/how/what)
- Verifies appropriate answer type
- Scores answer length
- Checks for examples/explanations
```

### 2. QualityMetricsCollector

Main evaluation engine with methods for each metric.

#### Usage

```python
from src.quality_metrics import QualityMetricsCollector

collector = QualityMetricsCollector()

# Individual metrics
faithfulness = collector.calculate_faithfulness(answer, sources)
relevance = collector.calculate_relevance(query, answer)
coherence = collector.calculate_coherence(answer)

# Comprehensive evaluation
metrics = collector.evaluate_response(query, answer, sources)

# Quality checks
acceptable = collector.is_acceptable_quality(metrics)
issues = collector.get_quality_issues(metrics)
suggestions = collector.get_improvement_suggestions(metrics)
```

### 3. RagasIntegration (`src/ragas_integration.py`)

Optional integration with RAGAS framework for advanced evaluation.

```python
from src.ragas_integration import RagasEvaluator, check_ragas_availability

# Check if RAGAS available
if check_ragas_availability():
    evaluator = RagasEvaluator()
    scores = evaluator.evaluate_all(question, answer, contexts)
    # scores.faithfulness, answer_relevance, context_relevance, ragas_score
```

**Note**: RAGAS is optional. Install with:
```bash
pip install ragas
```

### 4. QualityAwareRAGEngine (`src/rag_engine_quality.py`)

Complete RAG engine with quality monitoring and automatic improvement.

#### Processing Pipeline

```
Query
  ↓
Generate Initial Response
  ↓
Evaluate Quality Metrics
  ↓
Check if Acceptable
  ├─ YES → Return with metrics
  └─ NO → Attempt Improvement
       ├─ Retry 1: Expand query + more docs
       ├─ Retry 2: Strict reranking
       └─ Retry 3: Clarity reformulation
  ↓
Return Best Response with History
```

#### Key Methods

```python
from src.rag_engine_quality import QualityAwareRAGEngine

engine = QualityAwareRAGEngine()

# Query with automatic quality improvement
response = engine.query_with_quality_feedback(
    query="Tell me about machine learning",
    use_hierarchy=True,
    enable_improvement_loop=True,  # Auto-improve if quality low
    max_retries=3
)

# Access quality information
print(f"Overall score: {response.quality_metrics.overall_score:.2f}")
print(f"Issues: {response.quality_issues}")
print(f"Suggestions: {response.improvement_suggestions}")
print(f"Retry count: {response.retry_count}")

# Get detailed report
report = engine.get_quality_report(response)
```

## Configuration Guide

### Quality Thresholds

```python
engine = QualityAwareRAGEngine()

# Customize thresholds
engine.set_quality_thresholds(
    min_overall=0.65,        # Overall minimum
    min_faithfulness=0.55    # Faithfulness minimum
)
```

### Metric Weights

Default weights (total = 1.0):

```python
weights = {
    "faithfulness": 0.35,    # Most critical
    "relevance": 0.25,       # Very important
    "coherence": 0.15,       # Important
    "coverage": 0.15,        # Important
    "completeness": 0.10     # Nice to have
}
```

To customize:

```python
collector = QualityMetricsCollector()
collector.metric_weights = {
    "faithfulness": 0.40,
    "relevance": 0.30,
    "coherence": 0.10,
    "coverage": 0.15,
    "completeness": 0.05
}
```

### Improvement Strategies

Three automatic improvement strategies applied in sequence:

1. **Expand Query**: Retrieve more documents with expanded query
2. **Strict Reranking**: Use stricter document selection
3. **Clarity Reformulation**: Reformat for maximum clarity

Disable with:
```python
response = engine.query_with_quality_feedback(
    query,
    enable_improvement_loop=False
)
```

## Performance Characteristics

### Evaluation Time

| Metric | Time (ms) |
|--------|-----------|
| Faithfulness | 50-100 |
| Relevance | 20-50 |
| Coherence | 30-70 |
| Coverage | 20-40 |
| Completeness | 30-60 |
| **Total** | **150-400** |

### Improvement Loop Time

| Retry | Strategy | Typical Time (ms) |
|-------|----------|-------------------|
| Initial | Generation | 1000-2000 |
| Retry 1 | Query expansion | 1500-2500 |
| Retry 2 | Reranking | 1200-2000 |
| Retry 3 | Reformulation | 1000-1500 |

## Usage Examples

### Basic Quality Check

```python
from src.quality_metrics import QualityMetricsCollector

collector = QualityMetricsCollector()

query = "What is machine learning?"
answer = """Machine learning is a subset of artificial intelligence...
It enables computers to learn from data..."""
sources = ["ML is a subset of AI", "Computers learn from data"]

metrics = collector.evaluate_response(query, answer, sources)

print(f"Faithfulness: {metrics.faithfulness:.2f}")
print(f"Relevance: {metrics.relevance:.2f}")
print(f"Overall: {metrics.overall_score:.2f}")

if collector.is_acceptable_quality(metrics):
    print("✓ Quality acceptable")
else:
    print("✗ Quality issues:")
    for issue in collector.get_quality_issues(metrics):
        print(f"  - {issue}")
```

### Automatic Quality Improvement

```python
from src.rag_engine_quality import QualityAwareRAGEngine

engine = QualityAwareRAGEngine()

# Query with automatic improvement if needed
response = engine.query_with_quality_feedback(
    query="Explain neural networks",
    enable_improvement_loop=True,
    max_retries=3
)

print(f"Answer: {response.answer}")
print(f"Quality: {response.quality_metrics.overall_score:.2f}")
print(f"Improved: {response.retry_count > 0} ({response.retry_count} retries)")

# Get detailed report
report = engine.get_quality_report(response)
print(f"Report: {report}")
```

### Custom Metric Configuration

```python
from src.quality_metrics import QualityMetricsCollector

# Create custom collector with different thresholds
collector = QualityMetricsCollector()
collector.min_acceptable_overall = 0.70  # Stricter
collector.min_acceptable_faithfulness = 0.65

# Evaluate
metrics = collector.evaluate_response(query, answer, sources)
acceptable = collector.is_acceptable_quality(metrics)
```

### RAGAS Integration (if available)

```python
from src.ragas_integration import RagasEvaluator, check_ragas_availability

if check_ragas_availability():
    evaluator = RagasEvaluator()

    scores = evaluator.evaluate_all(
        question="What is AI?",
        answer="Artificial intelligence...",
        contexts=["AI is a field..."]
    )

    print(f"RAGAS Faithfulness: {scores.faithfulness}")
    print(f"RAGAS Answer Relevance: {scores.answer_relevance}")
    print(f"RAGAS Context Relevance: {scores.context_relevance}")
    print(f"Overall RAGAS Score: {scores.ragas_score}")
else:
    print("RAGAS not available")
    print(RagasEvaluator.install_instructions())
```

## Metric Interpretation Guide

### Overall Score (0-1)

- **0.80+**: Excellent - Production ready
- **0.70-0.79**: Good - Minor improvements possible
- **0.60-0.69**: Acceptable - Monitor quality
- **0.50-0.59**: Poor - Needs improvement
- **<0.50**: Critical - Manual review required

### Faithfulness (0-1)

Answers if answer is grounded in sources.

- **0.80+**: Highly faithful, well-supported
- **0.60-0.79**: Mostly faithful, mostly supported
- **0.40-0.59**: Partially faithful, some unsupported claims
- **<0.40**: Low fidelity, many unsupported claims

**When to worry**: < 0.55 (default minimum)

### Relevance (0-1)

Measures if answer addresses the query.

- **0.80+**: Directly answers query
- **0.60-0.79**: Mostly answers query
- **0.40-0.59**: Partially addresses query
- **<0.40**: Doesn't address query

**When to worry**: < 0.60

### Coherence (0-1)

Rates answer structure and readability.

- **0.75+**: Well-structured, easy to read
- **0.60-0.74**: Adequately structured
- **0.40-0.59**: Some structural issues
- **<0.40**: Poorly structured

**When to worry**: < 0.50

### Coverage (0-1)

Shows if key query terms are in answer.

- **0.90+**: Comprehensive coverage
- **0.70-0.89**: Good coverage
- **0.50-0.69**: Partial coverage
- **<0.50**: Missing key terms

### Completeness (0-1)

Indicates if answer provides sufficient detail.

- **0.75+**: Comprehensive answer
- **0.60-0.74**: Adequate detail
- **0.40-0.59**: Lacking detail
- **<0.40**: Too brief

## Best Practices

### 1. Set Appropriate Thresholds

```python
# Strict mode (high-stakes applications)
engine.set_quality_thresholds(min_overall=0.75, min_faithfulness=0.70)

# Balanced (recommended)
engine.set_quality_thresholds(min_overall=0.65, min_faithfulness=0.55)

# Lenient (speed-prioritized)
engine.set_quality_thresholds(min_overall=0.55, min_faithfulness=0.45)
```

### 2. Monitor Quality Over Time

```python
# Track quality trends
quality_scores = []

for query in queries:
    response = engine.query_with_quality_feedback(query)
    quality_scores.append(response.quality_metrics.overall_score)

avg_quality = sum(quality_scores) / len(quality_scores)
print(f"Average quality: {avg_quality:.2f}")
```

### 3. Use Improvement Loop Selectively

```python
# For critical queries: enable improvement
if is_critical_query:
    response = engine.query_with_quality_feedback(
        query,
        enable_improvement_loop=True,
        max_retries=3
    )
else:
    # For regular queries: skip improvement for speed
    response = engine.query_with_quality_feedback(
        query,
        enable_improvement_loop=False
    )
```

### 4. Log Quality Metrics

```python
import logging
logger = logging.getLogger(__name__)

response = engine.query_with_quality_feedback(query)
logger.info(f"Quality: {response.quality_metrics.overall_score:.2f}")
logger.info(f"Issues: {response.quality_issues}")

if response.retry_count > 0:
    logger.info(f"Improved with {response.retry_count} retries")
```

### 5. Combine with Human Review

```python
response = engine.query_with_quality_feedback(query)

if response.requires_improvement:
    # Flag for human review
    log_for_review(response)

    # Or retry with different settings
    response = engine.query_with_quality_feedback(
        query,
        max_retries=5  # Try harder
    )
```

## Troubleshooting

### Quality Score Always Low

**Problem**: Scores consistently < 0.6

**Solutions**:
1. Check source quality (garbage in = garbage out)
2. Verify query clarity (ambiguous queries score lower)
3. Ensure sufficient source material
4. Review answer generation (may need prompt adjustment)

### Improvement Loop Never Converges

**Problem**: Retries don't improve quality

**Solutions**:
1. Increase `max_retries` to allow more attempts
2. Review improvement strategy (may need customization)
3. Check if better sources available
4. Consider manual intervention

### Quality Metrics Seem Wrong

**Problem**: Scores don't match manual evaluation

**Solutions**:
1. Verify metric weights reflect your priorities
2. Check calculation logic for specific metrics
3. Use RAGAS for validation (if installed)
4. Compare with manual scoring on sample

### Performance Issues

**Problem**: Evaluation too slow

**Solutions**:
1. Disable improvement loop for non-critical queries
2. Disable RAGAS evaluation
3. Cache evaluations for similar queries
4. Increase evaluation thresholds

## Integration Checklist

- [ ] Install quality metrics: `from src.quality_metrics import QualityMetricsCollector`
- [ ] Test individual metrics on sample data
- [ ] Configure thresholds for your use case
- [ ] Integrate with RAG engine: `QualityAwareRAGEngine`
- [ ] Test improvement loop (enable → disable)
- [ ] Verify RAGAS optional (install if available)
- [ ] Set up quality logging/monitoring
- [ ] Establish quality SLAs
- [ ] Document threshold decisions
- [ ] Plan for human review process

## Summary

FASE 19 provides production-grade quality evaluation through:

1. **Multi-Metric Evaluation**: Faithfulness, relevance, coherence, coverage, completeness
2. **Automatic Improvement**: Retry with different strategies if quality low
3. **RAGAS Integration**: Optional advanced evaluation
4. **Customizable Thresholds**: Adapt to your requirements
5. **Detailed Reporting**: Issues and suggestions for improvement

Combined with FASE 18's long-context capabilities, this enables robust, high-quality RAG systems ready for enterprise deployment.
