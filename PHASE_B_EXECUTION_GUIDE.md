# PHASE B: COMPREHENSIVE TESTING EXECUTION GUIDE
**Date**: 2026-02-19
**Status**: Ready for Immediate Execution

---

## QUICK START

### Step 1: Run Test Suite
```bash
cd C:\Users\ChristianRobecchi\Downloads\RAG LOCALE
python run_phase_b_testing.py
```

Expected duration: **15-30 minutes** (depends on API response times)

### Step 2: View Results
```bash
# Results are saved to: logs/phase_b_results.jsonl
# Each line is a complete test result in JSON format
```

### Step 3: Run Streamlit App (Optional)
```bash
streamlit run app_streamlit_real_docs.py
```

---

## WHAT'S BEING TESTED

### Document Inventory
- **Total**: 71 PDFs
- **Size**: 8.3 MB
- **Language**: Italian (100%)
- **Domains**: HR, Integration, Business Platforms, Data Analytics, Training

### Test Queries (7 diverse scenarios)

| ID | Query | Type | Purpose |
|-----|-------|------|---------|
| **Q1** | How to integrate ARCA with Cerved Atoka through APIs? | Technical Integration | Multi-doc synthesis |
| **Q2** | Complete onboarding workflow in Flexibile? | Process | Sequential steps |
| **Q3** | Factorial vs Wally learning management? | Feature Comparison | Capability analysis |
| **Q4** | Etica Group's digital transformation strategy? | Strategic Context | Cross-doc linking |
| **Q5** | Key features of Permanent service in ARCA? | Specific Lookup | Factual extraction |
| **Q6** | Resolve integration issues between Intiway & BI systems? | Troubleshooting | Problem-solving |
| **Q7** | Compare data warehouse strategies (Zucchetti, Intiway, Cerved)? | Comparative Analysis | Multi-dimensional |

### Testing Methodology

**Phase 1: Baseline (No Re-ranking)**
```
For each of 7 queries:
  1. Vector search (top 10)
  2. Generate answer with Gemini LLM
  3. Evaluate quality (8-dimensional metrics)
  4. Measure: latency, quality, resources
```

**Phase 2: Optimized (With Re-ranking)**
```
For each of 7 queries:
  1. Vector search (top 10)
  2. Apply GeminiCrossEncoderReranker (alpha=0.3)
  3. Select top 3 re-ranked results
  4. Generate answer with Gemini LLM
  5. Evaluate quality
  6. Measure: latency, quality, resources
```

**Phase 3: Alpha Tuning**
```
Single query tested with alpha values:
  - 0.0 (100% re-ranking)
  - 0.3 (default: 30% original + 70% re-ranking)
  - 0.5 (50/50 balance)
  - 0.7 (70% original + 30% re-ranking)
  - 1.0 (100% original)

Observe score changes with different weightings
```

---

## KEY PERFORMANCE INDICATORS (KPIs)

### Latency Expectations

| Metric | Without Re-ranking | With Re-ranking | Target |
|--------|-------------------|-----------------|--------|
| Vector search | 200-400ms | 200-400ms | <500ms |
| Re-ranking | — | 500-1000ms | <1500ms |
| LLM generation | 800-1500ms | 800-1500ms | <2000ms |
| **Total per query** | **1000-2300ms** | **1500-3000ms** | **<4000ms** |

### Quality Expectations

| Metric | Definition | Target | Method |
|--------|-----------|--------|--------|
| **Faithfulness** | Answer grounded in docs | >0.80 | LLM evaluation |
| **Relevance** | Query-answer match | >0.75 | Semantic similarity |
| **Precision@3** | Top 3 relevance | >0.70 | Manual/LLM judgment |
| **Consistency** | Stable across runs | >0.85 | Semantic similarity |
| **Overall Quality** | Combined score | >0.75 | 8-dimensional metrics |

### Improvement Targets

| Metric | Expected | Stretch Goal |
|--------|----------|--------------|
| Quality improvement (with re-ranking) | +10-15% | +20-30% |
| Latency increase (with re-ranking) | +30-50% | <+100% |
| Cache hit rate (repeated queries) | >60% | >80% |
| Error rate | <1% | <0.5% |

---

## FILE STRUCTURE

### Test Script
```
run_phase_b_testing.py (300 lines)
├── PhaseBTester class
│   ├── setup() - Initialize all components
│   ├── retrieve_without_reranking() - Baseline retrieval
│   ├── retrieve_with_reranking() - Optimized retrieval
│   ├── run_baseline_test() - Baseline measurements
│   ├── run_optimized_test() - Optimized measurements
│   ├── run_alpha_tuning() - Alpha parameter tuning
│   └── generate_report() - Results analysis
└── main() - Entry point
```

### Output
```
logs/phase_b_results.jsonl
├── One JSON object per line
├── Each line: complete test result
├── Fields: timestamp, query, latency, quality, resources
└── Appendable (previous runs preserved)
```

### Example Result
```json
{
  "timestamp": "2026-02-19T14:30:45",
  "test_phase": "baseline",
  "query_id": "Q1",
  "query": "How can I integrate ARCA with Cerved Atoka through APIs?",
  "query_type": "technical_integration",
  "retrieval": {
    "method": "vector_only",
    "latency_ms": 245,
    "results_count": 3,
    "scores": [0.92, 0.87, 0.81],
    "documents": ["API integration guide...", "Cerved Atoka documentation...", "ARCA platform specs..."]
  },
  "generation_latency_ms": 1200,
  "quality_score": 0.78,
  "total_latency_ms": 1445
}
```

---

## EXECUTION TIMELINE

| Phase | Duration | Actions |
|-------|----------|---------|
| **Setup** | 1-2 min | Load documents, initialize modules |
| **Baseline** | 5-10 min | Run 7 queries without re-ranking |
| **Optimized** | 5-10 min | Run 7 queries with re-ranking |
| **Alpha Tuning** | 2-5 min | Test 5 alpha values |
| **Report** | 1-2 min | Generate analysis |
| **Total** | **15-30 min** | Complete test suite |

---

## WHAT TO LOOK FOR

### Console Output

**Successful Run:**
```
================================================================================
 PHASE B TESTING SETUP
================================================================================
[1/5] Loading documents...
      Loaded 71 documents (100%)
[2/5] Initializing vector store...
      Indexed 71 documents
[3/5] Initializing LLM service...
      Gemini API ready
[4/5] Initializing re-ranker...
      Re-ranker initialized
[5/5] Initializing quality evaluator...
      Quality metrics ready

✓ Setup complete

--- PHASE B BASELINE TESTING (No Re-ranking) ---

[1/7] Q1: How can I integrate ARCA with Cerved Atoka through APIs?...
      Latency: 1245ms | Quality: 0.78
[2/7] Q2: What is the complete onboarding workflow in Flexibile platform?...
      Latency: 1089ms | Quality: 0.81
...
```

**Expected Metrics:**
- Baseline latency: 1000-1500ms per query
- Optimized latency: 1500-2500ms per query
- Quality improvement: 5-15% with re-ranking

### Log File Analysis

```bash
# Count total results
wc -l logs/phase_b_results.jsonl

# View baseline averages
cat logs/phase_b_results.jsonl | jq 'select(.test_phase=="baseline") | .total_latency_ms' | awk '{sum+=$1; n++} END {print "Avg:", sum/n "ms"}'

# View optimized improvements
cat logs/phase_b_results.jsonl | jq 'select(.test_phase=="optimized") | .quality_score' | awk '{sum+=$1; n++} END {print "Avg Quality:", sum/n}'
```

---

## TROUBLESHOOTING

### Problem: "ModuleNotFoundError: No module named 'src'"
**Solution**: Run from RAG LOCALE directory
```bash
cd C:\Users\ChristianRobecchi\Downloads\RAG LOCALE
python run_phase_b_testing.py
```

### Problem: "Gemini API Error: Authentication failed"
**Solution**: Verify GEMINI_API_KEY in .env file
```bash
# Check .env exists
ls -la .env

# Verify API key is set
grep GEMINI_API_KEY .env
```

### Problem: "Vector store initialization failed"
**Solution**: Check document loader
```bash
python -c "from document_loader import DocumentLoaderManager; m = DocumentLoaderManager(); print(len(m.load_all_sources()), 'docs loaded')"
```

### Problem: "Timeout during re-ranking"
**Solution**: Normal (Gemini API can take 1-2s). If persistent, check:
- Internet connectivity
- API quota usage
- System resources (memory, CPU)

---

## NEXT STEPS

### After Test Completion

**1. Review Results** (5-10 min)
   - [ ] Check console output for errors
   - [ ] Verify all 7 queries completed
   - [ ] Note any performance anomalies

**2. Analyze Metrics** (10-15 min)
   - [ ] Compare baseline vs optimized latency
   - [ ] Calculate quality improvement percentage
   - [ ] Identify best/worst performing queries

**3. Optimization Decisions** (5 min)
   - [ ] Deploy with re-ranking? (Depends on latency tolerance)
   - [ ] Adjust alpha value? (Based on quality/latency trade-off)
   - [ ] Enable Vision API? (For multimodal support)

**4. Documentation** (5-10 min)
   - [ ] Document findings
   - [ ] Create comparison charts
   - [ ] Prepare deployment recommendation

---

## DEPLOYMENT RECOMMENDATION CRITERIA

### Deploy with Re-ranking if:
✓ Quality improvement > +10%
✓ Latency increase < +100%
✓ Error rate < 1%
✓ User satisfaction is priority

### Keep without Re-ranking if:
✓ Latency increase > +100%
✓ Quality improvement < +5%
✓ Real-time response is critical
✓ API costs are concern

### Custom Configuration if:
✓ Alpha adjustment improves trade-off
✓ Selective re-ranking (only for complex queries)
✓ Hybrid approach (re-rank only if base confidence < threshold)

---

## COMMANDS REFERENCE

```bash
# Full test suite
python run_phase_b_testing.py

# With specific log file
python run_phase_b_testing.py > test_output.log 2>&1

# Extract baseline average latency
cat logs/phase_b_results.jsonl | jq -r 'select(.test_phase=="baseline") | .total_latency_ms' | awk '{s+=$0; c++} END {print "Baseline avg:", s/c "ms"}'

# Extract optimized average latency
cat logs/phase_b_results.jsonl | jq -r 'select(.test_phase=="optimized") | .total_latency_ms' | awk '{s+=$0; c++} END {print "Optimized avg:", s/c "ms"}'

# Compare quality scores
echo "Baseline quality:" && \
cat logs/phase_b_results.jsonl | jq -r 'select(.test_phase=="baseline") | .quality_score' | awk '{s+=$0; c++} END {print s/c}' && \
echo "Optimized quality:" && \
cat logs/phase_b_results.jsonl | jq -r 'select(.test_phase=="optimized") | .quality_score' | awk '{s+=$0; c++} END {print s/c}'
```

---

## SUCCESS CRITERIA

✅ **PHASE B Complete When:**
- [ ] All 7 baseline queries executed successfully
- [ ] All 7 optimized queries executed successfully
- [ ] Alpha tuning tested with 5 values
- [ ] Results saved to `logs/phase_b_results.jsonl`
- [ ] Report generated with comparison metrics
- [ ] No critical errors in console output
- [ ] Quality metrics collected for all queries
- [ ] Latency measurements recorded

---

## ESTIMATED RESULTS

Based on 71 PDF corpus and 7 diverse queries:

| Metric | Baseline | Optimized | Change |
|--------|----------|-----------|--------|
| Average Latency | 1,200ms | 1,800ms | +50% |
| Average Quality | 0.75 | 0.82 | +9.3% |
| Error Rate | <1% | <1% | Stable |
| Cache Hit Rate | 5% | 5% | Stable |
| Memory Usage | 250MB | 260MB | +10MB |

---

## READY TO START?

### Quick Checklist
- [x] 71 PDF documents available
- [x] Test suite script created (run_phase_b_testing.py)
- [x] Test queries prepared (7 diverse scenarios)
- [x] Baseline and optimized flows defined
- [x] Results logging configured
- [x] Performance metrics defined
- [x] Troubleshooting guide provided

### Execute with:
```bash
python run_phase_b_testing.py
```

---

**Expected completion**: 15-30 minutes
**Documentation**: Complete ✓
**System Status**: Ready ✓

GO! 🚀

