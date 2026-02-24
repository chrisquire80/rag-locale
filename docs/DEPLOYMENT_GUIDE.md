# RAG Locale — Deployment & Operations Guide

## Prerequisites

| Requirement | Version | Purpose |
|---|---|---|
| Python | 3.9+ | Runtime |
| pip | 23+ | Package management |
| Git | 2.30+ | Version control |
| Google Gemini API Key | — | LLM + Embeddings |
| Poppler (optional) | — | PDF image extraction |

**Hardware (Optimized for):** HP ProBook 440 G11 — 16GB RAM, CPU-only

---

## Quick Start (Development)

```bash
# 1. Clone & enter project
git clone <repo-url> && cd RAG-LOCALE

# 2. Create virtual environment
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Linux/Mac

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env → set GEMINI_API_KEY=your_key_here

# 5. Place documents
# Copy PDF/DOCX/TXT/XLSX files into data/documents/

# 6. Launch
streamlit run app_streamlit_real_docs.py
# Opens at http://localhost:8502
```

---

## Environment Configuration

### Required Variables (`.env`)

| Variable | Description | Default |
|---|---|---|
| `GEMINI_API_KEY` | Google Gemini API key | **Required** |

### Optional Variables

| Variable | Description | Default |
|---|---|---|
| `GEMINI_MODEL_NAME` | Chat model | `gemini-2.0-flash` |
| `GEMINI_EMBEDDING_MODEL` | Embedding model | `models/gemini-embedding-001` |
| `GEMINI_MAX_TOKENS` | Max output tokens | `2048` |
| `GEMINI_TEMPERATURE` | Response creativity | `0.3` |
| `GEMINI_REQUEST_TIMEOUT` | Request timeout (sec) | `300` |
| `GEMINI_MAX_RETRIES` | Retry count | `5` |
| `CHROMADB_MODE` | `persistent` or `ephemeral` | `persistent` |
| `CHROMADB_CHUNK_SIZE` | Chunk size in tokens | `1000` |
| `CHROMADB_CHUNK_OVERLAP` | Overlap between chunks | `100` |
| `RAG_SIMILARITY_TOP_K` | Docs retrieved per query | `5` |
| `PERF_CACHE_TTL_SECONDS` | Cache TTL | `7200` (2h) |
| `APP_LOG_LEVEL` | Logging level | `INFO` |

---

## Docker Deployment

### Build & Run (Streamlit only)

```bash
docker compose up -d rag-ui
# Accessible at http://localhost:8501
```

### Build & Run (Streamlit + FastAPI)

```bash
docker compose --profile with-api up -d
# Streamlit: http://localhost:8501
# FastAPI:   http://localhost:8000
```

### Health Check

```bash
# Container health
docker inspect --format='{{.State.Health.Status}}' rag-locale-ui

# Manual health check
curl http://localhost:8501/_stcore/health

# API health (if running)
curl http://localhost:8000/api/health
```

### Volume Mounts

| Host Path | Container Path | Purpose |
|---|---|---|
| `./logs` | `/app/logs` | Application logs |
| `./data` | `/app/data` | Vector DB + persistent data |
| `./documents` | `/app/documents` | Source documents |
| `./rag_memory.db` | `/app/rag_memory.db` | Chat history + tasks |

---

## Post-Deploy Verification Checklist

- [ ] `.env` contains valid `GEMINI_API_KEY`
- [ ] `data/documents/` contains source files
- [ ] `python health_check.py` passes all 5 checks
- [ ] Streamlit UI loads at configured port
- [ ] Document ingestion completes without errors
- [ ] Chat responds with relevant document content
- [ ] Knowledge Graph displays nodes and edges
- [ ] Forecast generates without API timeout
- [ ] Task Board creates and persists tasks
- [ ] Simulator controls appear in sidebar
