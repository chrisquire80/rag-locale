# RAG Locale — Monitoring & Alerts Setup

## Key Metrics to Track

### Application Health

| Metric | Source | Threshold | Alert |
|---|---|---|---|
| API Response Time | Gemini API logs | > 30s | ⚠️ Warning |
| API Error Rate | `structured_logging` | > 5% | 🔴 Critical |
| Rate Limit Block Rate | `rate_limiter.get_stats()` | > 40% | ⚠️ Warning |
| Memory Usage | OS monitoring | > 85% | ⚠️ Warning |
| Disk Usage | OS monitoring | > 90% | 🔴 Critical |
| Vector Store Size | `vector_store.get_stats()` | > 5GB | ℹ️ Info |
| Cache Hit Rate | Cache metrics | < 30% | ⚠️ Warning |
| SQLite DB Size | `rag_memory.db` stat | > 100MB | ℹ️ Info |

### Business Metrics

| Metric | Source | Goal |
|---|---|---|
| Queries/day | `chat_history` count | Track trend |
| Anomaly Rate | `memory_service.get_stats()` | < 20% |
| Task Completion Rate | `memory_service.get_task_completion_rate()` | > 70% |
| Documents Indexed | `vector_store.list_indexed_files()` | All uploaded |
| Quality Score (avg) | Session state `quality_scores` | > 0.85 |

---

## Structured Logging (JSON Format)

All logs are emitted in JSON format via `structured_logging.py`:

```json
{
    "timestamp": "2026-02-24T12:06:00.290432Z",
    "level": "INFO",
    "module": "rag_engine",
    "function": "query",
    "line": 157,
    "message": "Processing query",
    "query": "What is Zucchetti?",
    "user_id": 123
}
```

**Log file location:** `logs/app.jsonl`

### Quick Log Queries

```bash
# Errors in last 100 lines
tail -100 logs/app.jsonl | python -c "
import sys, json
for line in sys.stdin:
    e = json.loads(line)
    if e.get('level') in ('ERROR','CRITICAL'):
        print(f\"{e['timestamp']} [{e['module']}] {e['message']}\")
"

# Rate limit violations
grep -i "rate limit" logs/app.jsonl | tail -20

# Slow operations (>10s)
grep "elapsed" logs/app.jsonl | python -c "
import sys, json
for line in sys.stdin:
    e = json.loads(line)
    if e.get('elapsed_ms', 0) > 10000:
        print(f\"{e['timestamp']} SLOW: {e['module']}.{e['function']} ({e['elapsed_ms']}ms)\")
"
```

---

## Rate Limiter Monitoring

```python
from src.rate_limiter import get_rate_limiter

stats = get_rate_limiter().get_stats()
print(f"""
Rate Limiter Dashboard:
  Total Requests:   {stats['total_requests']}
  Blocked:          {stats['blocked_requests']}
  Block Rate:       {stats['block_rate']:.1%}
  Requests/sec:     {stats['requests_per_sec']:.1f}
  Global Tokens:    {stats['global_tokens']:.0f}
  Active Users:     {stats['active_users']}
  Active Endpoints: {stats['active_endpoints']}
  Uptime:           {stats['elapsed_seconds']:.0f}s
""")
```

---

## Performance Baselines

Measured on HP ProBook 440 G11 (16GB RAM, CPU-only):

| Operation | Expected Time | Alert If |
|---|---|---|
| Single query (RAG) | 3-8s | > 15s |
| Document ingestion (per file) | 5-30s | > 60s |
| Forecast generation | 10-20s | > 45s |
| Knowledge Graph build | 1-3s | > 10s |
| Embedding (per batch) | 2-5s | > 15s |

---

## Log Aggregation (Future)

For ELK/Datadog integration, logs are already JSON-formatted. Configure your log shipper to:

1. **Read from:** `logs/app.jsonl`
2. **Parse as:** JSON (no regex needed)
3. **Index on:** `timestamp`, `level`, `module`
4. **Alert on:**
   - `level == "CRITICAL"` → Immediate notification
   - `level == "ERROR" && count > 10/min` → Warning
   - `message contains "rate limit"` → Rate limit alert
