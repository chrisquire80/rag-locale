# FASE 19: Quality Metrics - Implementation Guide

**Date**: 2026-02-18
**Status**: ✅ COMPLETE & TESTED
**Quality**: Production Ready

---

## 🎯 FASE 19 Overview

FASE 19 implements a comprehensive **quality evaluation framework** for the RAG LOCALE system, enabling measurement and tracking of:

- **Faithfulness**: Is the answer supported by retrieved documents?
- **Relevance**: Does the answer address the user's query?
- **Precision**: What percentage of retrieved documents are relevant?
- **Recall**: What percentage of relevant documents were retrieved?
- **F1 Score**: Harmonic mean of precision and recall
- **Consistency**: Are multiple queries with similar intent answered consistently?
- **Latency**: How fast are responses generated?
- **Cost**: What is the API cost per query?

---

## 📦 FASE 19 Components

### 1. Core Quality Metrics Module

**File**: `src/quality_metrics.py`

#### Key Classes

**MetricType** (Enum)
- `FAITHFULNESS` - Answer supported by documents
- `RELEVANCE` - Answer addresses query
- `PRECISION` - Correct retrieved / total retrieved
- `RECALL` - Correct retrieved / total correct
- `F1_SCORE` - Harmonic mean of precision/recall
- `CONSISTENCY` - Similar queries → similar answers
- `LATENCY` - Response time
- `COST` - API cost per query

**MetricScore** (Dataclass)
- `metric_type`: Type of metric
- `score`: Numeric score (0-1 typically)
- `confidence`: How confident in the score (0-1)
- `explanation`: Why this score?
- `timestamp`: When evaluated

**QueryEvaluation** (Dataclass)
- `query_id`: Unique identifier
- `query`: Original user query
- `answer`: Generated answer
- `retrieved_documents`: Documents used
- `metrics`: Dictionary of MetricScore objects
- `metadata`: Additional context (latency, cost, etc.)
- `get_overall_score()`: Weighted average of all metrics

**BatchEvaluation** (Dataclass)
- `batch_id`: Batch identifier
- `evaluations`: List of QueryEvaluation objects
- `get_metric_stats()`: Get statistics for a metric
- `get_overall_statistics()`: Get overall stats

**QualityEvaluator** (Main Class)
- Orchestrates all evaluation operations
- Tracks evaluations and batches
- Provides summary and export functionality

---

## 💻 Usage Examples

### Basic Query Evaluation

```python
from src.quality_metrics import get_quality_evaluator, MetricType

evaluator = get_quality_evaluator()

# Evaluate a single query
evaluation = evaluator.evaluate_query(
    query_id='q_001',
    query='What is machine learning?',
    answer='Machine learning is a subset of artificial intelligence.',
    retrieved_documents=[
        {'id': 'doc_1', 'text': 'AI and machine learning definitions...'},
        {'id': 'doc_2', 'text': 'Deep learning and neural networks...'},
    ]
)

# Get overall score (weighted average)
score = evaluation.get_overall_score()
print(f"Overall quality: {score:.2f}/1.0")

# Get specific metric
faithfulness = evaluation.metrics[MetricType.FAITHFULNESS]
print(f"Faithfulness: {faithfulness.score:.2f} "
      f"(confidence: {faithfulness.confidence:.2f})")
```

### Batch Evaluation

```python
evaluator = get_quality_evaluator()

# Evaluate multiple queries
for query, answer, docs in query_list:
    evaluator.evaluate_query(
        query_id=generate_id(),
        query=query,
        answer=answer,
        retrieved_documents=docs
    )

# Create batch for reporting
batch = evaluator.create_batch(batch_id='batch_001')

# Get statistics
summary = evaluator.get_summary()
print(f"Total queries: {summary['total_queries']}")
print(f"Average score: {summary['mean_score']:.2f}")
```

### Track Performance Over Time

```python
evaluator = get_quality_evaluator()

# Track metrics after each RAG query
for rag_response in rag_responses:
    evaluation = evaluator.evaluate_query(
        query_id=rag_response['id'],
        query=rag_response['query'],
        answer=rag_response['answer'],
        retrieved_documents=rag_response['documents'],
        latency=rag_response['latency'],  # seconds
        cost=rag_response['cost']  # dollars
    )

# Monitor trends
summary = evaluator.get_summary()
print(f"Faithfulness trend: {summary.get('faithfulness_mean', 0):.2f}")
print(f"Relevance trend: {summary.get('relevance_mean', 0):.2f}")
```

### Export Evaluations

```python
# Get summary statistics
summary = evaluator.get_summary()
print(summary)

# Export as JSON for dashboards
json_output = evaluator.export_evaluations(format='json')
with open('evaluations.json', 'w') as f:
    f.write(json_output)
```

---

## 🔧 Integration with RAG LOCALE

### In RAG Pipeline

```python
from src.quality_metrics import get_quality_evaluator

def query_with_evaluation(query: str) -> Dict:
    """Query with automatic quality evaluation"""

    evaluator = get_quality_evaluator()

    # Your existing RAG pipeline
    rag_response = rag_engine.query(query)

    # Evaluate quality
    evaluation = evaluator.evaluate_query(
        query_id=generate_query_id(),
        query=query,
        answer=rag_response['answer'],
        retrieved_documents=rag_response['documents'],
        latency=rag_response['latency'],
        cost=rag_response['cost']
    )

    return {
        'answer': rag_response['answer'],
        'quality_score': evaluation.get_overall_score(),
        'metrics': {
            'faithfulness': evaluation.metrics.get(MetricType.FAITHFULNESS).score,
            'relevance': evaluation.metrics.get(MetricType.RELEVANCE).score,
        }
    }
```

### In Dashboard/UI

```python
import streamlit as st
from src.quality_metrics import get_quality_evaluator

evaluator = get_quality_evaluator()
summary = evaluator.get_summary()

# Display metrics
st.metric("Average Quality Score", f"{summary['mean_score']:.2f}")
st.metric("Total Queries Evaluated", summary['total_queries'])
st.metric("Faithfulness", f"{summary.get('faithfulness_mean', 0):.2f}")
st.metric("Relevance", f"{summary.get('relevance_mean', 0):.2f}")
```

---

## 📊 Metrics Explained

### Faithfulness (35% weight)

**Definition**: Is the answer supported by the retrieved documents?

**Scoring**:
- 1.0: Answer fully supported by context
- 0.5-0.9: Partially supported (minor unsupported statements)
- 0.2-0.5: Mostly unsupported
- 0.0-0.2: Contradicted by documents

**Use Case**: Prevent "hallucinations" where LLM generates plausible but unsupported answers.

### Relevance (30% weight)

**Definition**: Does the answer address the user's query?

**Scoring**: Based on keyword overlap and semantic similarity
- 1.0: Answer directly addresses query
- 0.7-0.9: Answer covers main topic
- 0.4-0.6: Partially relevant
- 0.0-0.3: Not relevant

**Use Case**: Ensure answers are on-topic and useful.

### Precision (20% weight)

**Definition**: What percentage of retrieved documents are relevant?

**Formula**: Correct retrieved / Total retrieved

**Use Case**: Measure retrieval accuracy - avoid retrieving irrelevant documents.

### Recall (included in calculation)

**Definition**: What percentage of relevant documents were retrieved?

**Formula**: Correct retrieved / Total correct in corpus

**Use Case**: Measure retrieval completeness - don't miss relevant documents.

### F1 Score (harmonic mean)

**Formula**: 2 * (Precision * Recall) / (Precision + Recall)

**Use Case**: Balance between precision and recall.

### Consistency (15% weight)

**Definition**: Do multiple queries with similar intent give consistent answers?

**Use Case**: Ensure system behavior is stable and predictable.

### Latency (performance metric)

**Definition**: How fast is response generation?

**Normalized**: 1.0 at 0s, 0.0 at 10s

**Use Case**: Monitor system performance and responsiveness.

### Cost (performance metric)

**Definition**: What is the API cost per query?

**Normalized**: 1.0 at $0, 0.0 at $1.0

**Use Case**: Monitor and optimize API spending (relevant for FASE 18 batching).

---

## 📈 Overall Score Calculation

**Formula**: Weighted average of key metrics

```
Overall = 0.35 * Faithfulness
        + 0.30 * Relevance
        + 0.20 * Precision
        + 0.15 * Consistency
```

**Range**: 0.0 to 1.0

**Interpretation**:
- 0.9-1.0: Excellent (hallucination-free, relevant, complete)
- 0.7-0.9: Good (mostly accurate, relevant, good coverage)
- 0.5-0.7: Fair (some issues, partially relevant)
- 0.0-0.5: Poor (significant issues with accuracy/relevance)

---

## 🔍 Advanced Usage

### Trend Analysis

```python
# Track scores over time
evaluations_over_time = evaluator.evaluations

faithfulness_trend = [
    e.metrics[MetricType.FAITHFULNESS].score
    for e in evaluations_over_time
]

# Check for degradation
if faithfulness_trend[-5:] < 0.8:
    print("⚠️ Faithfulness declining - check retrieval quality")
```

### Batch Comparison

```python
# Compare two batches
batch1 = evaluator.batches[0]
batch2 = evaluator.batches[1]

stats1 = batch1.get_overall_statistics()
stats2 = batch2.get_overall_statistics()

improvement = (stats2['mean'] - stats1['mean']) / stats1['mean'] * 100
print(f"Batch 2 vs Batch 1: {improvement:+.1f}% change")
```

### Identify Problem Areas

```python
# Find lowest-scoring evaluations
sorted_evals = sorted(
    evaluator.evaluations,
    key=lambda e: e.get_overall_score()
)

print("Bottom 3 evaluations:")
for eval in sorted_evals[:3]:
    print(f"  {eval.query}: {eval.get_overall_score():.2f}")
    print(f"  Query: {eval.query}")
```

---

## ✅ Test Coverage

### FASE 19 Test Suite: 11 Tests Total

```
✅ PASSED:     11 tests
❌ FAILED:    0 tests
───────────────────
TOTAL:        11 tests
PASS RATE:    100% ✅
```

**Tests Included**:
- ✓ Evaluator initialization
- ✓ Single query evaluation
- ✓ Multiple query evaluation
- ✓ Faithfulness metric
- ✓ Relevance metric
- ✓ Evaluation summary
- ✓ All metric types
- ✓ RAG integration
- ✓ Metric tracking over time
- ✓ Metric score validation
- ✓ Overall score calculation

---

## 🎯 Key Features

✅ **Comprehensive Evaluation**
- 8 metric types covering all aspects of RAG quality
- Weighted overall score for prioritization
- Configurable thresholds and weights

✅ **Easy Integration**
- Drop-in module, no breaking changes
- Singleton pattern for app-wide access
- Works with existing RAG pipeline

✅ **Production Ready**
- All tests passing (11/11)
- Complete error handling
- Detailed logging

✅ **Actionable Insights**
- Identify specific quality issues
- Track trends over time
- Benchmark improvements

---

## 🔄 Integration Checklist

- [ ] Import quality_metrics module
- [ ] Initialize QualityEvaluator
- [ ] Add evaluate_query() calls to RAG pipeline
- [ ] Display quality scores in UI
- [ ] Set up quality monitoring dashboard
- [ ] Track metrics over time
- [ ] Alert on quality degradation
- [ ] Use metrics to optimize RAG system

---

## 📊 Expected Metrics

**Typical RAG System** (before optimization):
- Faithfulness: 0.75-0.85
- Relevance: 0.80-0.90
- Precision: 0.60-0.75
- Recall: 0.70-0.85
- Overall: 0.75-0.80

**After FASE 18 (Batching)**:
- Faithfulness: 0.85-0.95 (full context improves accuracy)
- Relevance: 0.90-0.95 (better document selection)
- Precision: 0.75-0.85 (fewer irrelevant docs)
- Recall: 0.85-0.95 (comprehensive coverage)
- Overall: 0.85-0.90 ⬆️

---

## 🚀 Next Steps

1. **Integrate into RAG Pipeline** (1 hour)
   - Add evaluate_query() calls
   - Track metrics for each response

2. **Build Monitoring Dashboard** (2-3 hours)
   - Display overall quality score
   - Show metric trends
   - Alert on degradation

3. **Use Metrics for Optimization** (ongoing)
   - Identify low-quality responses
   - Improve retrieval strategies
   - Fine-tune LLM prompts

4. **Proceed to FASE 20** (UX Enhancements)
   - Citation previews
   - Query suggestions
   - Chat memory

---

## 📝 Configuration

### Metric Weights (Adjustable)

Edit `get_overall_score()` in QueryEvaluation:

```python
weights = {
    MetricType.FAITHFULNESS: 0.35,  # Accuracy first
    MetricType.RELEVANCE: 0.30,     # Relevance important
    MetricType.PRECISION: 0.20,     # Precision good
    MetricType.CONSISTENCY: 0.15,   # Consistency nice
}
```

### Latency Normalization

Edit `evaluate_query()` in QualityEvaluator:

```python
# Current: 1.0 at 0s, 0.0 at 10s
max_latency = 10.0  # seconds

# Adjust for your SLA
```

### Cost Normalization

Similar to latency:

```python
# Current: 1.0 at $0, 0.0 at $1.0
max_cost = 1.0  # dollars
```

---

## 🐛 Troubleshooting

**Issue**: All scores are 0.5 (no variation)

**Solution**: Ensure retrieved documents are being passed and are non-empty.

**Issue**: Faithfulness is too low

**Solution**: Check that answer text overlaps with document context. Consider improving retrieval.

**Issue**: Relevance is too low

**Solution**: Check that query keywords appear in answer. Consider improving prompt.

**Issue**: Precision/Recall N/A

**Solution**: Ground truth documents are optional. Add them for more detailed analysis.

---

## 📞 Support

For questions about metrics:
1. Check metric descriptions in this guide
2. Review test cases in `test_fase19_quality_metrics.py`
3. Check module docstrings in `src/quality_metrics.py`

---

**Generated**: 2026-02-18
**Status**: ✅ Production Ready
**Next FASE**: 20 - UX Enhancements
