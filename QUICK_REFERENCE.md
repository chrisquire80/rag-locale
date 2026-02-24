# 🚀 RAG LOCALE - QUICK REFERENCE GUIDE

## ⚡ Quick Start

### 1. Start Backend (FastAPI)
```bash
cd C:\Users\ChristianRobecchi\Downloads\RAG LOCALE
python src/api.py
# Server runs at http://localhost:5000
```

### 2. Start Frontend (Streamlit)
```bash
cd C:\Users\ChristianRobecchi\Downloads\RAG LOCALE
streamlit run src/frontend.py
# UI opens at http://localhost:8501
```

### 3. Ingest Documents (No UI)
```bash
cd C:\Users\ChristianRobecchi\Downloads\RAG LOCALE
python ingest_all_documents.py
# Ingests all PDFs from data/documents/
# Takes ~1.4s per PDF (68 PDFs → ~93 seconds total)
```

---

## 📁 File Structure

```
RAG LOCALE/
├── src/
│   ├── api.py                      # FastAPI backend
│   ├── frontend.py                 # Streamlit UI
│   ├── llm_service.py              # Gemini API integration
│   ├── vector_store.py             # Vector storage & search
│   ├── document_ingestion.py       # PDF processing pipeline
│   ├── document_processor.py       # PDF extraction
│   ├── pdf_worker.py               # Subprocess handler
│   └── config.py                   # Configuration
├── data/
│   ├── documents/                  # PDF files (upload here)
│   ├── vector_store.pkl            # Embeddings database
│   ├── ingestion_blacklist.txt     # Failed files (auto-generated)
│   └── ingestion_lock.txt          # Safety lock (auto-generated)
├── logs/
│   └── rag.log                     # Application logs
├── setup/
│   └── requirements.txt            # Python dependencies
├── .env                            # API keys (NOT in git)
└── ingest_all_documents.py         # Bulk ingestion script
```

---

## 🔑 Configuration

### Environment Variables (.env)
```ini
# Gemini API Configuration
GEMINI__API_KEY=your-api-key-here
GEMINI__MODEL_NAME=gemini-2.0-flash
GEMINI__EMBEDDING_MODEL=models/gemini-embedding-001

# Optional: API Configuration
API_HOST=0.0.0.0
API_PORT=5000
```

### Config File (src/config.py)
- Default: `data/documents/` for PDF uploads
- Default: `data/vector_store.pkl` for embeddings
- Timeout: 300 seconds per PDF
- Max chunks: No limit
- Embedding dimension: 3072

---

## 📊 Key APIs

### Query Endpoint
```bash
POST http://localhost:5000/api/query
Content-Type: application/json

{
    "query": "What is the key topic discussed?",
    "top_k": 3
}

Response:
{
    "answer": "...",
    "sources": [
        {"document": "...", "similarity": 0.85},
        {"document": "...", "similarity": 0.82},
        {"document": "...", "similarity": 0.78}
    ]
}
```

### Upload Document
```bash
POST http://localhost:5000/api/upload
Files: file.pdf

Response:
{
    "filename": "file.pdf",
    "chunks": 4,
    "status": "success"
}
```

### Health Check
```bash
GET http://localhost:5000/api/health

Response:
{
    "status": "ok",
    "gemini": "connected",
    "documents": 68
}
```

---

## 🧪 Testing

### Run All Tests
```bash
# FASE 6 Unit Tests (5 tests)
python test_fase6_fixes.py

# Batch Ingestion Test (10 PDFs)
python test_ingestion_batch.py

# Full Ingestion (68 PDFs)
python ingest_all_documents.py
```

### Expected Results
- ✅ All unit tests should pass (5/5)
- ✅ Batch test should show 100% success
- ✅ Full ingestion should complete with 0 failures

---

## 🐛 Troubleshooting

### Issue: "Gemini API not available"
**Solution**:
```bash
# Check .env file has correct API key
# Test API key:
python -c "from src.llm_service import get_llm_service; get_llm_service().check_health()"
```

### Issue: "Rate limited - retrying"
**Solution**: This is normal! System automatically retries with exponential backoff (0.5s → 1s → 2s). Let it continue.

### Issue: "PDF processing stuck"
**Solution**:
```bash
# Kill any stuck processes
taskkill /F /IM python.exe

# Restart system
python ingest_all_documents.py
```

### Issue: "Vector store corrupted"
**Solution**:
```bash
# Backup current store
copy data\vector_store.pkl data\vector_store.pkl.backup

# Clear and regenerate
rm data\vector_store.pkl
python ingest_all_documents.py
```

### Issue: "FutureWarning about google-generativeai"
**Solution**: Already fixed! System uses google-genai (v1.63.0) - no warnings.

---

## 📈 Performance Optimization

### Speed Up Ingestion
- Current: 1.4s per PDF (optimal)
- Batch size: Auto-optimized
- Parallel: Currently sequential (by design, for reliability)

### Speed Up Queries
- Current: <100ms (optimal)
- Uses pre-computed matrix (no per-query rebuilding)
- Cosine similarity (vectorized with NumPy)

### Reduce Memory Usage
- Vector store: ~250MB for 68 documents
- Embeddings: 3072 dimensions × 74 vectors = 912KB
- Cache: Automatically cleared between queries

---

## 🔐 Security Notes

### Safety Features Enabled
- ✅ Gemini API safety filters (BLOCK_MEDIUM_AND_ABOVE)
- ✅ Path traversal prevention
- ✅ Rate-limit protection
- ✅ Error propagation (no silent failures)

### API Considerations
- ⚠️ Local-only deployment (not exposed to internet)
- ⚠️ API key stored in .env (never commit to git)
- ⚠️ No authentication layer (trusted local use)
- ⚠️ File uploads limited to data/documents/ directory

---

## 📚 Common Tasks

### Add New Documents
1. Place PDF files in `data/documents/`
2. Run `python ingest_all_documents.py`
3. System processes incrementally (only new files)
4. Use UI or API to query

### Remove Documents
1. Delete PDF from `data/documents/`
2. Clear vector store: `rm data/vector_store.pkl`
3. Re-ingest remaining documents

### Export Search Results
```python
# In Python:
from src.vector_store import get_vector_store
vs = get_vector_store()
results = vs.search("your query", top_k=10)
for result in results:
    print(f"Score: {result['similarity_score']}")
    print(f"Text: {result['document'][:100]}...")
```

### Monitor System
```bash
# Check logs
tail -f logs/rag.log

# Check vector store
python -c "
from src.vector_store import get_vector_store
vs = get_vector_store()
print(f'Documents: {len(vs.documents)}')
if vs._embedding_matrix is not None:
    print(f'Matrix: {vs._embedding_matrix.shape}')
"
```

---

## 🚀 Advanced Configuration

### Change Model
Edit `src/config.py`:
```python
model_name="gemini-2.0-flash"     # Or: gemini-1.5-pro, etc.
embedding_model="models/gemini-embedding-001"
```

### Change Chunk Size
Edit `src/document_processor.py`:
```python
CHUNK_SIZE = 512  # tokens (currently optimized)
OVERLAP = 50      # tokens
```

### Change Vector Store Location
Edit `src/config.py`:
```python
VECTOR_STORE_FILE = Path("path/to/custom/store.pkl")
```

### Disable Safety Filters (NOT RECOMMENDED)
Edit `src/llm_service.py`:
```python
# Change BLOCK_MEDIUM_AND_ABOVE to BLOCK_NONE
# Only do this if you trust all documents!
```

---

## 📞 Support

### Logs Location
```
C:\Users\ChristianRobecchi\Downloads\RAG LOCALE\logs\rag.log
```

### Key Log Patterns
- `✓ Successfully ingested` = PDF processed
- `[429 Rate Limited]` = Gemini throttling (normal, auto-retry)
- `✗ Errore` = Error (check details)
- `CRITICAL` = System issue (save logs)

### Status Files
```
data/ingestion_blacklist.txt  # Failed PDFs (auto-generated)
data/ingestion_lock.txt       # Prevents concurrent ingestion
```

---

## 🔄 Release History

### FASE 6 (17 Feb 2026)
- Fixed rate-limit cascade (BUG #1)
- Fixed error propagation (BUG #2)
- Added batch retry logic (BUG #3)
- Result: 68/68 PDFs ingesting at 100%

### FASE 7 (17 Feb 2026)
- Migrated from google-generativeai to google-genai
- Updated all API calls to new Client pattern
- Result: Zero deprecation warnings, same 100% success

---

**Last Updated**: 17 Febbraio 2026
**System Version**: FASE 7 (Production Ready)
**Status**: ✅ All systems operational
