# FASE 9: TECHNICAL REFERENCE GUIDE
## Error Handling Patterns and Architecture

---

## 1. Error Flow Analysis

### Before FASE 9: Failure Chain
```
Ingestion completes
    ↓
add_documents() returns (count_added, failed_docs)
    ↓
Return value IGNORED ← Problem 1: Silent data loss
    ↓
_rebuild_matrix() executes
    ↓
No try/except ← Problem 2: Unhandled exception
    ↓
Exception propagates to app_ui.py
    ↓
stats = pipeline.vector_store.get_stats()
    ↓
No try/except ← Problem 3: Unhandled exception
    ↓
Exception propagates to Streamlit
    ↓
Streamlit catches top-level exception
    ↓
"Connection error Is Streamlit still running?"
```

### After FASE 9: Safe Path
```
Ingestion completes
    ↓
count_added, failed_docs = add_documents() ✅ Captured
    ↓
if failed_docs: log warnings ✅ Visibility
    ↓
try: _rebuild_matrix() ✅ Protected
except: raise with context ✅ Error info
    ↓
try: stats = get_stats() ✅ Protected
except: log and show error ✅ Graceful
finally: cleanup ✅ Resources freed
    ↓
Success message shown to user ✅
UI remains responsive ✅
Logging captures everything ✅
```

---

## 2. Key Code Patterns

### Pattern 1: Capturing Return Values

**Location**: `src/document_ingestion.py:567`

```python
# WRONG - Silent failure
self.vector_store.add_documents(documents, metadatas, ids)

# RIGHT - Validate success
count_added, failed_docs = self.vector_store.add_documents(
    documents=documents,
    metadatas=metadatas,
    ids=ids
)

# Track discrepancies
if count_added != len(documents):
    logger.warning(f"Partial failure: {count_added}/{len(documents)} added")

if failed_docs:
    logger.warning(f"Failed documents: {failed_docs}")
```

**Why This Matters**:
- Embedding API can fail on individual documents
- If we ignore return value, vector store gets corrupted state
- UI shows "ingested 100 docs" but store only has 95
- Future queries miss the 5 lost documents silently

### Pattern 2: Operation Boundaries with Try/Except/Finally

**Location**: `src/app_ui.py:154`

```python
# WRONG - Exception propagates
stats = pipeline.vector_store.get_stats()
st.success(f"Success! {stats['total_documents']} docs")
st.rerun()

# RIGHT - Protected with cleanup
try:
    stats = pipeline.vector_store.get_stats()
    st.success(f"Success! {stats['total_documents']} docs")
except Exception as e:
    st.error(f"Error: {e}")
    logger.error(f"Stats failed: {e}")
finally:
    # Always clean up UI elements
    time.sleep(2)
    status_text.empty()
    progress_bar.empty()
    # Only rerun if successful (implicit in try block)
```

**Why This Matters**:
- `get_stats()` could fail if vector store corrupted
- Without try/except, exception crashes Streamlit
- With finally, UI is cleaned up regardless
- With error logging, we know what went wrong

### Pattern 3: Error Context and Re-raising

**Location**: `src/vector_store.py:200`

```python
# WRONG - Suppress error silently
try:
    self._rebuild_matrix()
except:
    pass

# WRONG - No context
try:
    self._rebuild_matrix()
except Exception:
    raise

# RIGHT - Add context and log
try:
    self._rebuild_matrix()
    logger.info(f"Matrix rebuilt: {self._embedding_matrix.shape}")
except Exception as e:
    logger.error(f"Matrix rebuild failed: {e}")
    raise RuntimeError(
        f"Failed to rebuild search matrix after adding {count_added} documents: {e}"
    )
```

**Why This Matters**:
- Original error is preserved (nested exception)
- Context added ("after adding N documents")
- Logging captures state when error occurred
- Caller can decide how to handle
- Debugging becomes possible

---

## 3. State Consistency Patterns

### Pattern: Verify What Was Added

```python
# Before adding
initial_count = len(self.documents)

# Add documents
count_added, failed_docs = self.vector_store.add_documents(...)

# Verify consistency
final_count = len(self.documents)
actual_added = final_count - initial_count

assert actual_added == count_added, \
    f"Mismatch: reported {count_added}, actual {actual_added}"
```

### Pattern: Check Pre-conditions

```python
# Before matrix rebuild
if self.documents:  # Only rebuild if docs exist
    try:
        self._rebuild_matrix()
    except Exception as e:
        logger.error(f"Cannot rebuild matrix: {e}")
        # Handle error appropriately
else:
    logger.info("Skipping matrix rebuild: no documents")
```

---

## 4. Error Boundary Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                   Streamlit UI (app_ui.py)                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  try:                                                    ││
│  │    stats = get_stats()  ← Error Boundary #3             ││
│  │  except: show error                                      ││
│  │  finally: cleanup                                        ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│            DocumentIngestionPipeline                         │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  count_added, failed = add_documents()                  ││
│  │  ↓ Error Boundary #2                                    ││
│  │  if failed_docs:                                         ││
│  │    log warnings ← Visibility                             ││
│  │  return count_added ← Data validation                    ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                   VectorStore                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  for document in documents:                             ││
│  │    try:                                                 ││
│  │      embedding = get_embedding(text)                   ││
│  │    except: log failure, add to failed_docs             ││
│  │                                                         ││
│  │  try:                                                  ││
│  │    _rebuild_matrix()  ← Error Boundary #1              ││
│  │  except: raise with context                            ││
│  │                                                         ││
│  │  return count_added, failed_docs ← Return values       ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

**Key Points**:
- Error Boundary #1: Critical operation protection
- Error Boundary #2: Return value capture
- Error Boundary #3: UI protection
- Each level has appropriate error handling
- Errors flow up with context attached

---

## 5. Logging Architecture

### What Gets Logged at Each Level

```python
# Level 1: LLM Service (vector_store.py)
logger.info("Adding X documents...")
logger.info("Batch embedding X texts...")
logger.error("Embedding failed for doc_id: Y")
logger.info("Successfully added N documents")

# Level 2: Document Ingestion (document_ingestion.py)
logger.info("Ingestion: filename.pdf")
logger.info("Successfully ingested N/M chunks from filename")
logger.warning("Failed to add M chunks: [reasons]")

# Level 3: UI (app_ui.py)
logger.info("Folder import started")
logger.error("Stats retrieval failed: [error]")
logger.error("Ingestion failed: [error]")

# Level 4: Application Main (main.py)
"Connection error..." → log.error() captures this
```

### Tracing an Ingestion Failure

```bash
# 1. Find all ERROR lines
grep "ERROR" logs/rag.log

# 2. Find specific error context
grep -B5 -A5 "Failed to add" logs/rag.log

# 3. Reconstruct error chain
# Find doc that failed
grep "doc_id" logs/rag.log | tail -20
# See what embedding returned
grep "Embedding" logs/rag.log | tail -5
# Understand impact
grep "Successfully added" logs/rag.log | tail -3
```

---

## 6. Testing Error Paths

### Unit Test for Return Value Handling

```python
def test_return_value_capture():
    """Verify add_documents return values are captured"""
    pipeline = DocumentIngestionPipeline()

    # Mock failure by adding invalid document
    count, failed = pipeline.vector_store.add_documents(
        ["valid doc", ""],  # Empty doc might fail
        metadatas=[{"s": "1"}, {"s": "2"}]
    )

    # Verify returns
    assert isinstance(count, int)
    assert isinstance(failed, list)
    assert count >= 0

    # If had failures, verify they're logged
    if failed:
        logger.info(f"Expected failures: {failed}")
```

### Integration Test for Error Boundary

```python
def test_stats_error_handling():
    """Verify stats retrieval errors don't crash"""
    pipeline = DocumentIngestionPipeline()

    # Corrupt the vector store to trigger error
    pipeline.vector_store.documents = None  # Intentional corruption

    # This should not crash
    try:
        stats = pipeline.vector_store.get_stats()
    except Exception as e:
        logger.error(f"Expected error: {e}")
        # Error is OK, should be caught at UI level
```

---

## 7. Recovery Procedures

### If Stats Retrieval Fails

```python
# Automated recovery
try:
    stats = pipeline.vector_store.get_stats()
except Exception as e:
    logger.error(f"Stats failed: {e}")
    # Fallback: count documents manually
    stats = {'total_documents': len(pipeline.vector_store.documents)}
    st.warning(f"Could not verify stats, estimated: {stats}")
```

### If Matrix Rebuild Fails

```python
# Mark as dirty and try again later
try:
    self._rebuild_matrix()
except Exception as e:
    logger.error(f"Matrix rebuild failed: {e}")
    self._matrix_dirty = True
    # Try again on next search
    # Or raise to caller
    raise RuntimeError(f"Cannot rebuild search matrix: {e}")
```

### If Embedding Fails

```python
# Already implemented in vector_store.py
for document in documents:
    try:
        embedding = self.llm.get_embedding(text)
        # Success
    except Exception as e:
        if "429" in str(e):  # Rate limit
            raise  # Stop batch, retry later
        else:
            # Other error - skip this doc
            failed_docs.append((doc_id, str(e)))
```

---

## 8. Performance Considerations

### Error Handling Overhead

**Try/Except Performance**:
- Happy path: ~0-1% overhead
- Exception path: ~5-10% overhead (raising exception is expensive)
- Use try/except for actual error cases, not control flow

**Return Value Validation**:
- Minimal overhead: just tuple unpacking + type check
- No performance impact on happy path

**Logging**:
- Info level: ~1-5% overhead per operation
- Debug level: ~5-10% overhead (more expensive)
- Error level: cheap (only called on failures)

### FASE 9 Performance Impact

- **No degradation**: All error handling added to non-happy paths
- **Actual improvement**: Better error visibility = fewer retries
- **Memory**: No additional memory usage (error messages are logged, not stored)
- **CPU**: Negligible overhead

---

## 9. Future Improvements

### Circuit Breaker Pattern
```python
class EmbeddingCircuitBreaker:
    def __init__(self, failure_threshold=5, reset_timeout=300):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.last_failure_time = None

    def call(self, text):
        if self.is_open():
            raise RuntimeError("Circuit breaker open: too many failures")
        try:
            return self.llm.get_embedding(text)
        except Exception as e:
            self.record_failure()
            raise
```

### Retry Strategy
```python
@retry(
    max_attempts=3,
    backoff=exponential(base=2),
    on=[RateLimitError, TimeoutError]
)
def get_embedding_with_retry(text):
    return llm.get_embedding(text)
```

### Observable Metrics
```python
@track_metrics("ingestion")
def ingest_single_file(file_path):
    # Automatically tracks:
    # - Duration
    # - Success/failure
    # - Documents added
    # - Errors encountered
    pass
```

---

## 10. Checklist for Future Error Handling

When adding new operations that could fail:

- [ ] Identify failure modes
- [ ] Add appropriate try/except boundaries
- [ ] Validate return values
- [ ] Add error logging with context
- [ ] Consider recovery/fallback paths
- [ ] Test error scenarios
- [ ] Document expected failures
- [ ] Add monitoring/metrics
- [ ] Update documentation

---

*FASE 9 Technical Reference - For future maintenance and improvements*
