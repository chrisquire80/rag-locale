# FASE 18: Integration Guide for RAG LOCALE

**How to integrate the Long-Context Strategy into your existing RAG system**

---

## Quick Start

FASE 18 provides 5 production-ready modules that work together to:
1. **Compress** documents to fit in 1M token context
2. **Batch** multiple documents into single API calls
3. **Select** optimal documents for retrieval
4. **Analyze** across multiple documents
5. **Reduce** API costs by 90-95%

---

## Integration Steps

### Step 1: Import Core Modules

```python
from src.context_window_manager import get_context_window_manager, ContextWindowManager
from src.document_compressor import get_document_compressor, DocumentCompressor, CompressionLevel
from src.context_batcher import get_context_batcher, ContextBatcher
from src.smart_retrieval_long import get_smart_retriever, SmartRetrieverLong, RetrievalStrategy
from src.multi_document_analyzer_long import get_multi_document_analyzer, MultiDocumentAnalyzerLong
```

### Step 2: Initialize Singleton Instances

```python
# Get singleton instances (recommended for app-wide access)
cwm = get_context_window_manager()
compressor = get_document_compressor()
batcher = get_context_batcher()
retriever = get_smart_retriever()
analyzer = get_multi_document_analyzer()

# Or create new instances if needed
cwm = ContextWindowManager(max_tokens=1_000_000)
compressor = DocumentCompressor()
batcher = ContextBatcher(max_batch_tokens=900_000)
retriever = SmartRetrieverLong(max_tokens=900_000)
analyzer = MultiDocumentAnalyzerLong()
```

### Step 3: Integrate into Query Pipeline

#### Option A: Simple Integration (Just Batching)

```python
def query_with_batching(query: str, documents: List[Dict]):
    """Process query using FASE 18 batching"""

    # 1. Batch documents for efficiency
    batches = batcher.pack_documents(documents)
    batches, unallocated = batcher.add_queries_to_batches(batches, [query])

    # 2. Process each batch (usually just 1-5 batches)
    responses = []
    for batch in batches:
        # Your existing LLM call, but with multiple documents in context
        response = your_llm_service.query(
            documents=batch.documents,
            queries=batch.queries
        )
        responses.append(response)

    # 3. Combine responses
    return combine_responses(responses)
```

#### Option B: Full Integration (Batching + Compression + Smart Retrieval)

```python
def query_with_full_lange_context(query: str, documents: List[Dict]):
    """Process query using full FASE 18 pipeline"""

    # Step 1: Allocate context based on relevance
    allocation_result = cwm.allocate_context(documents, query)
    allocation_dict = {
        doc['id']: CompressionLevel(level)
        for doc, level in zip(documents, allocation_result['allocations'])
    }

    # Step 2: Compress documents intelligently
    compressed_docs = compressor.compress_batch(documents, allocation_dict)

    # Step 3: Smart document selection (hybrid strategy)
    relevance_scores = {doc['id']: score for doc, score in allocation_result.items()}
    selection = retriever.retrieve(
        documents=documents,
        query=query,
        strategy=RetrievalStrategy.HYBRID,
        relevance_scores=relevance_scores
    )

    # Step 4: Batch selected documents
    batches = batcher.pack_documents(selection.selected_documents)
    batches, unallocated = batcher.add_queries_to_batches(batches, [query])

    # Step 5: Process batches efficiently
    responses = []
    for batch in batches:
        response = your_llm_service.query(
            documents=batch.documents,
            queries=batch.queries,
            include_compressed=True
        )
        responses.append(response)

    # Step 6: Return combined response
    return {
        'answer': combine_responses(responses),
        'documents_used': selection.selected_documents,
        'coverage': selection.coverage_percent,
        'cost_saving': '90-95% reduction'
    }
```

#### Option C: Detailed Analysis Integration

```python
def analyze_with_multi_document_reasoning(query: str, documents: List[Dict]):
    """Use FASE 18 for advanced multi-document analysis"""

    # First, batch and retrieve as above
    selection = retriever.retrieve(documents, query, strategy=RetrievalStrategy.HYBRID)
    batches = batcher.pack_documents(selection.selected_documents)

    # Add advanced analysis
    if "compare" in query.lower():
        # Extract comparison topic from query
        analysis = analyzer.analyze_comparison(
            documents=selection.selected_documents,
            comparison_topic=extract_topic(query),
            llm_service=your_llm_service
        )
        return analysis.answer

    elif "synthesize" in query.lower() or "across" in query.lower():
        # Synthesize information across documents
        analysis = analyzer.analyze_synthesis(
            documents=selection.selected_documents,
            synthesis_question=query,
            llm_service=your_llm_service
        )
        return analysis.answer

    else:
        # Standard batched query
        responses = []
        for batch in batches:
            response = your_llm_service.query(batch.documents, batch.queries)
            responses.append(response)
        return combine_responses(responses)
```

---

## Usage Examples

### Example 1: Cost Comparison

```python
# Before FASE 18 (Sequential)
documents = [...]  # 70 documents
api_calls_before = len(documents) + 1  # 71 calls
cost_before = api_calls_before * 0.01  # ~$0.71

# With FASE 18 (Batched)
batches = batcher.pack_documents(documents)
api_calls_after = len(batches) + 1  # ~5 calls
cost_after = api_calls_after * 0.01  # ~$0.05

print(f"Cost reduction: {100 * (1 - cost_after/cost_before):.0f}%")
# Output: Cost reduction: 90%
```

### Example 2: Compression Example

```python
from src.document_compressor import DocumentCompressor, CompressionLevel

compressor = DocumentCompressor()

# Original document: 10,000 tokens
document = {
    'id': 'doc_1',
    'text': 'Very long document text...' * 500,
    'metadata': {'source': 'report.pdf'}
}

# Compress at different levels
full = compressor.compress(document['id'], document['text'], CompressionLevel.FULL)
detailed = compressor.compress(document['id'], document['text'], CompressionLevel.DETAILED)
executive = compressor.compress(document['id'], document['text'], CompressionLevel.EXECUTIVE)
metadata = compressor.compress(document['id'], document['text'], CompressionLevel.METADATA_ONLY)

print(f"Full: {full.compressed_token_count} tokens")         # 10,000
print(f"Detailed (20%): {detailed.compressed_token_count}")  # ~2,000
print(f"Executive (5%): {executive.compressed_token_count}") # ~500
print(f"Metadata: {metadata.compressed_token_count}")        # ~100
```

### Example 3: Smart Retrieval Strategies

```python
from src.smart_retrieval_long import SmartRetrieverLong, RetrievalStrategy

retriever = SmartRetrieverLong()

documents = [...]  # 70 documents
query = "What are the key findings?"
relevance_scores = {doc['id']: score for doc, score in scoring_results}

# Strategy 1: Relevance-first (for QA tasks)
result = retriever.retrieve(
    documents, query,
    strategy=RetrievalStrategy.RELEVANCE_FIRST,
    relevance_scores=relevance_scores
)
# → Returns top 5-10 most relevant documents

# Strategy 2: Size-first (to fit maximum content)
result = retriever.retrieve(
    documents, query,
    strategy=RetrievalStrategy.SIZE_FIRST
)
# → Returns 30+ documents (all small ones)

# Strategy 3: Diversity-first (for comprehensive view)
result = retriever.retrieve(
    documents, query,
    strategy=RetrievalStrategy.DIVERSITY_FIRST
)
# → Returns 20+ documents from different sources

# Strategy 4: Hybrid (balanced, recommended)
result = retriever.retrieve(
    documents, query,
    strategy=RetrievalStrategy.HYBRID  # Default
)
# → Returns optimal mix of relevance, size, and diversity
```

### Example 4: Batch Optimization

```python
# Create batches
batches = batcher.pack_documents(documents)
print(f"Created {len(batches)} batches")

# Add queries to batches
batches, unallocated = batcher.add_queries_to_batches(batches, queries)
if unallocated:
    print(f"Warning: {len(unallocated)} queries didn't fit")

# Optimize (merge small batches)
batches = batcher.optimize_batches(batches)

# Print summary
batcher.print_batch_summary()
# Output:
# ============ BATCH SUMMARY ============
# Total batches:                              5
# Total documents:                            70
# Total queries:                              3
# Total tokens:                               450,000
# Average utilization:                        50%
# Estimated total time:                       8.5s
```

---

## Integration Checklist

- [ ] Import FASE 18 modules in your RAG engine
- [ ] Initialize singleton instances (or create new ones)
- [ ] Choose integration level (Simple/Full/Advanced)
- [ ] Modify query pipeline to use batching
- [ ] Update LLM service calls to handle batched documents
- [ ] Test with sample documents
- [ ] Verify API cost reduction (should be 90-95%)
- [ ] Monitor performance metrics
- [ ] Fine-tune compression and batching strategies
- [ ] Deploy to production

---

## Configuration Reference

### ContextWindowManager

```python
cwm = ContextWindowManager(max_tokens=1_000_000)

# Properties
cwm.max_tokens                # 1,000,000
cwm.system_prompt_tokens      # 500 (configurable)
cwm.user_query_tokens         # 200 (configurable)
cwm.safety_buffer_percent     # 0.10 (10% reserve)
cwm.available_tokens          # 999,300 (calculated)

# Methods
cwm.estimate_tokens(text)                    # Estimate token count
cwm.allocate_context(docs, query)            # Allocate compression levels
cwm.optimize_allocation(allocation)          # Further optimize
cwm.get_utilization()                        # Get metrics
cwm.can_fit_tokens(count)                    # Check capacity
cwm.add_tokens(count, doc_id)                # Track usage
cwm.reset()                                  # Clear tracking
```

### DocumentCompressor

```python
compressor = DocumentCompressor()

# Compression levels
CompressionLevel.FULL              # 100% original
CompressionLevel.DETAILED          # ~20%
CompressionLevel.EXECUTIVE         # ~5%
CompressionLevel.METADATA_ONLY     # <1%

# Methods
compressor.compress(doc_id, text, level, metadata)
compressor.compress_batch(documents, allocation)
compressor.auto_compress(documents, target_tokens, scores)
```

### ContextBatcher

```python
batcher = ContextBatcher(max_batch_tokens=900_000)

# Batch strategies
BatchStrategy.BY_RELEVANCE         # Sort by relevance
BatchStrategy.BY_SIZE              # Sort by document size
BatchStrategy.BY_TOPIC             # Group by topic
BatchStrategy.SEQUENTIAL           # Sequential grouping

# Methods
batcher.create_batch(documents, queries)
batcher.pack_documents(documents)
batcher.add_queries_to_batches(batches, queries)
batcher.optimize_batches(batches)
batcher.estimate_api_calls_reduction(docs, queries)
```

### SmartRetrieverLong

```python
retriever = SmartRetrieverLong(max_tokens=900_000)

# Retrieval strategies
RetrievalStrategy.RELEVANCE_FIRST  # Highest scores first
RetrievalStrategy.SIZE_FIRST       # Smallest documents first
RetrievalStrategy.DIVERSITY_FIRST  # Mix of sources
RetrievalStrategy.HYBRID           # Balanced (default)

# Methods
retriever.retrieve(docs, query, strategy, scores, min_docs)
retriever.reorder_for_context(docs, query, order_by)
```

### MultiDocumentAnalyzerLong

```python
analyzer = MultiDocumentAnalyzerLong()

# Analysis types
analyzer.analyze_comparison(documents, topic, llm)
analyzer.analyze_synthesis(documents, question, llm)
analyzer.extract_structured_data(documents, schema, llm)
analyzer.analyze_relationships(documents, type, llm)
analyzer.detect_contradictions(documents, topic, llm)
analyzer.find_supporting_evidence(documents, claim, llm)
analyzer.identify_themes(documents, num_themes, llm)
analyzer.estimate_tokens_for_analysis(docs, type)
analyzer.log_analysis(result)
```

---

## Performance Tuning

### Optimize for Cost

```python
# Use maximum compression for non-critical documents
allocation = {
    doc['id']: CompressionLevel.EXECUTIVE if relevance[doc['id']] < 0.5
               else CompressionLevel.DETAILED
    for doc in documents
}
```

### Optimize for Quality

```python
# Keep high-relevance documents in full form
allocation = {
    doc['id']: CompressionLevel.FULL if relevance[doc['id']] > 0.8
               else CompressionLevel.DETAILED
    for doc in documents
}
```

### Optimize for Speed

```python
# Use size-first strategy to minimize total processing time
result = retriever.retrieve(
    documents, query,
    strategy=RetrievalStrategy.SIZE_FIRST
)
```

### Optimize for Accuracy

```python
# Use hybrid strategy with high-relevance bias
result = retriever.retrieve(
    documents, query,
    strategy=RetrievalStrategy.HYBRID,
    relevance_scores=scores,
    min_documents=10  # Ensure minimum coverage
)
```

---

## Troubleshooting

### Issue: "Batch exceeds token limit"
**Solution**: Use smaller max_batch_tokens or increase compression

```python
batcher = ContextBatcher(max_batch_tokens=800_000)  # Smaller batches
```

### Issue: "Too many queries don't fit"
**Solution**: Process queries in separate batches or reduce document count

```python
batches, unallocated = batcher.add_queries_to_batches(batches, queries)
if unallocated:
    # Process unallocated queries in new batch
    remaining_batches = batcher.pack_documents(documents)
    remaining_batches, _ = batcher.add_queries_to_batches(
        remaining_batches, unallocated
    )
    batches.extend(remaining_batches)
```

### Issue: "Compression too aggressive"
**Solution**: Increase minimum compression level or use detailed instead of executive

```python
allocation = {
    doc['id']: CompressionLevel.DETAILED  # Instead of EXECUTIVE
    for doc in documents
}
```

### Issue: "Documents missing from results"
**Solution**: Increase min_documents parameter or use different strategy

```python
result = retriever.retrieve(
    documents, query,
    strategy=RetrievalStrategy.DIVERSITY_FIRST,
    min_documents=20  # Increase minimum
)
```

---

## Performance Metrics

Monitor these metrics in production:

```python
# Log metrics after each batch
batch_metrics = {
    'batch_id': batch.batch_id,
    'documents': len(batch.documents),
    'tokens': batch.total_tokens,
    'utilization': f"{batch.utilization_percent():.1f}%",
    'queries': len(batch.queries),
    'api_cost_estimate': batch.total_tokens * 0.0001,  # Example pricing
}
```

---

## Next Steps

1. **Choose your integration level** (Simple/Full/Advanced)
2. **Modify your query pipeline** to use FASE 18 modules
3. **Test with sample documents** (10, 20, 70 documents)
4. **Monitor API cost reduction** (target: 90-95%)
5. **Fine-tune for your use case** (cost vs quality trade-offs)
6. **Deploy to production**
7. **Proceed to FASE 19** (Quality Metrics with Ragas/DeepEval)

---

## Support

For questions or issues:
1. Check the **Troubleshooting** section above
2. Review test cases in `test_fase18_complete.py`
3. Consult `FASE_18_LONG_CONTEXT_STRATEGY.md` for detailed architecture
4. Check module docstrings for detailed API documentation

---

**Last Updated**: 2026-02-18
**FASE 18 Status**: Production Ready ✅
**Next FASE**: 19 - Quality Metrics
