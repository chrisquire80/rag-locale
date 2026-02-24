# RAG Locale — Maintenance Checklist

## Weekly Tasks

- [ ] **Review error logs**
  ```bash
  grep '"level": "ERROR"' logs/app.jsonl | wc -l
  ```
  Target: < 50 errors/week

- [ ] **Check rate limiter stats**
  ```python
  from src.rate_limiter import get_rate_limiter
  stats = get_rate_limiter().get_stats()
  print(f"Block rate: {stats['block_rate']:.1%}")
  ```
  Target: < 5% block rate

- [ ] **Verify Task Board hygiene**
  - Close completed tasks
  - Review stale URGENTE items (> 7 days old)

- [ ] **Check disk space**
  ```bash
  du -sh data/vector_db/ logs/ rag_memory.db
  ```

- [ ] **Rotate logs** (if > 100MB)
  ```bash
  mv logs/app.jsonl logs/app.$(date +%Y%m%d).jsonl
  touch logs/app.jsonl
  ```

---

## Monthly Tasks

- [ ] **Dependency security audit**
  ```bash
  pip audit  # or pip install pip-audit first
  ```

- [ ] **Update dependencies** (minor/patch only)
  ```bash
  pip list --outdated
  # Update selectively, test before committing
  pip install --upgrade <package>
  ```

- [ ] **Review Knowledge Graph quality**
  - Check for orphan nodes (entities with no connections)
  - Verify entity extraction from new file naming patterns

- [ ] **Backup SQLite database**
  ```bash
  copy rag_memory.db backups/rag_memory_$(date +%Y%m%d).db
  ```

- [ ] **Performance baseline check**
  ```bash
  python load_test_rate_limiter.py
  ```
  Compare with previous month's results

- [ ] **Review anomaly rate trend**
  ```python
  from src.memory_service import get_memory_service
  stats = get_memory_service().get_stats()
  print(f"Anomaly rate: {stats['anomaly_rate']:.1%}")
  ```

---

## Quarterly Tasks

- [ ] **Full system health check**
  ```bash
  python health_check.py
  ```

- [ ] **Major version upgrades** (Python, Streamlit, Gemini SDK)
  - Read changelogs before upgrading
  - Test in isolated venv first
  - Run full test suite after upgrade

- [ ] **Re-index all documents** (if embedding model changes)
  ```bash
  rm -rf data/vector_db/
  # Reload via Streamlit UI
  ```

- [ ] **Review and archive old chat history**
  ```sql
  -- In SQLite, archive conversations older than 90 days
  DELETE FROM chat_history WHERE timestamp < datetime('now', '-90 days');
  VACUUM;
  ```

- [ ] **Docker image rebuild** (if using containers)
  ```bash
  docker compose build --no-cache
  docker compose up -d
  ```

---

## Version Update Procedure

```bash
# 1. Create branch
git checkout -b update/deps-YYYY-MM

# 2. Update requirements
pip install --upgrade <packages>
pip freeze > requirements_locked.txt

# 3. Run tests
python -m pytest tests/ -v

# 4. Run health check
python health_check.py

# 5. Run load test
python load_test_rate_limiter.py

# 6. If all green, commit & merge
git add -A && git commit -m "chore: update deps $(date +%Y-%m)"
git checkout main && git merge update/deps-YYYY-MM
```
