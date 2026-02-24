# RAG Locale — Runbook (Emergency Procedures)

## Quick Diagnostics

```bash
# Full system health check
python health_check.py

# Check if Streamlit is running
curl http://localhost:8502/_stcore/health

# Check Gemini API connectivity
python -c "from src.llm_service import get_llm_service; print(get_llm_service().check_health())"

# Check vector store status
python -c "from src.vector_store import get_vector_store; vs = get_vector_store(); print(f'Docs: {len(vs.documents)}, Files: {len(vs.list_indexed_files())}')"
```

---

## Common Issues & Fixes

### 1. `ReadTimeoutError` / `ConnectionResetError` (Gemini API)

**Symptoms:** Timeout errors during embedding generation or chat completion.

**Cause:** Gemini API overloaded or network instability.

**Fix:**
```python
# In .env, increase timeouts:
GEMINI_REQUEST_TIMEOUT=600    # 10 minutes
GEMINI_MAX_RETRIES=8          # More retries
GEMINI_RETRY_BASE_DELAY=2.0   # Slower backoff
```

**If persistent:** Check [Google AI Status](https://status.cloud.google.com/) for outages.

---

### 2. `RuntimeError: Rate limit` (Rate Limiter Blocking)

**Symptoms:** Functions raise `RuntimeError: Rate limit: Global rate limit exceeded`.

**Cause:** Too many rapid API calls (burst traffic exceeds bucket capacity).

**Fix:**
```python
# In src/rate_limiter.py → RateLimitConfig:
refill_rate: float = 100.0    # Increase from 50.0
bucket_capacity: int = 1000   # Increase from 500
```

**Monitoring:**
```python
from src.rate_limiter import get_rate_limiter
stats = get_rate_limiter().get_stats()
print(f"Block rate: {stats['block_rate']:.1%}")
print(f"Tokens available: {stats['global_tokens']:.0f}")
```

---

### 3. `ProgrammingError: Cannot operate on a closed database`

**Symptoms:** SQLite errors after task toggle/delete operations.

**Cause:** `conn.close()` called on pooled connection (fixed in commit `21f399d`).

**Fix:** Ensure `memory_service.py` does NOT call `conn.close()` in any method except `close()`.

---

### 4. PDF Processing Crashes

**Symptoms:** `Segfault` or `MemoryError` during document ingestion.

**Cause:** Corrupted PDF or extremely large file.

**Fix:**
```bash
# Identify problematic file
python -c "
from document_loader import DocumentLoaderManager
m = DocumentLoaderManager()
for f in sorted(Path('data/documents').glob('*.pdf')):
    try:
        m.load_single_file(str(f))
        print(f'OK: {f.name}')
    except Exception as e:
        print(f'FAIL: {f.name} - {e}')
"
```

**Workaround:** Move problematic PDF to a quarantine folder and re-ingest.

---

### 5. Vector Store Corrupted / Empty

**Symptoms:** Search returns no results; `vector_store.pkl` missing or zero-size.

**Fix:**
```bash
# Remove corrupted store and re-index
rm data/vector_db/vector_store.pkl
# Then reload documents via Streamlit UI → "Carica Documenti"
```

---

### 6. Streamlit UI Unresponsive

**Symptoms:** Page loads but spinner never stops.

**Cause:** Usually a blocking LLM call (Welcome Briefing) or infinite rerun loop.

**Fix:**
```bash
# Kill and restart
taskkill /F /IM streamlit.exe    # Windows
# kill -9 $(pgrep streamlit)     # Linux

# Restart
streamlit run app_streamlit_real_docs.py
```

**If briefing hangs:** Disable web monitoring temporarily in sidebar settings.

---

### 7. Memory Warning (>85% RAM)

**Symptoms:** `APP__MEMORY_WARNING_THRESHOLD_PCT` alert in logs.

**Fix:**
1. Close other applications
2. Reduce `PERF_CACHE_MAX_SIZE` from 1000 to 500
3. Reduce `PERF_TOP_K_MAX` from 20 to 10
4. Restart Streamlit to release cached objects

---

## Rollback Procedure

```bash
# 1. List recent commits
git log --oneline -10

# 2. Identify last known good commit
git checkout <commit-hash>

# 3. If Docker: rebuild
docker compose build --no-cache
docker compose up -d

# 4. If local: restart
streamlit run app_streamlit_real_docs.py
```

---

## Log Analysis

```bash
# View recent errors (structured JSON logs)
python -c "
import json
with open('logs/app.jsonl') as f:
    for line in f:
        entry = json.loads(line)
        if entry.get('level') in ('ERROR', 'CRITICAL'):
            print(f\"{entry['timestamp']} [{entry['module']}] {entry['message']}\")
"

# Count errors per module
python -c "
import json
from collections import Counter
errors = Counter()
with open('logs/app.jsonl') as f:
    for line in f:
        entry = json.loads(line)
        if entry.get('level') == 'ERROR':
            errors[entry.get('module', 'unknown')] += 1
for mod, count in errors.most_common(10):
    print(f'{count:4d} errors in {mod}')
"
```
