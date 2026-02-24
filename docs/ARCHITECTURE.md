# RAG Locale — Architecture Overview

## System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                      STREAMLIT UI (Port 8502)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │   Chat   │ │ Forecast │ │  Graph   │ │Simulator │           │
│  │  (Q&A)   │ │(What-If) │ │(Neural)  │ │(Impact)  │           │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘           │
│       │             │            │             │                 │
│  ┌────▼─────────────▼────────────▼─────────────▼──────────────┐ │
│  │              app_streamlit_real_docs.py                     │ │
│  │         (Main Application — 2100 lines)                    │ │
│  └────┬──────────────────────────────────────────────────┬────┘ │
└───────┼──────────────────────────────────────────────────┼──────┘
        │                                                  │
┌───────▼──────────────────────────────────────────────────▼──────┐
│                        SERVICE LAYER                            │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐           │
│  │ llm_service │  │vector_store │  │memory_service│           │
│  │  (Gemini)   │  │ (ChromaDB)  │  │  (SQLite)    │           │
│  └──────┬──────┘  └──────┬──────┘  └──────┬───────┘           │
│         │                │                │                     │
│  ┌──────┴──────┐  ┌──────┴──────┐  ┌──────┴───────┐           │
│  │rate_limiter │  │graph_service│  │structured_   │           │
│  │(@rate_limit)│  │ (Knowledge) │  │   logging    │           │
│  └─────────────┘  └─────────────┘  └──────────────┘           │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐           │
│  │  reranker   │  │ config.py   │  │document_loader│          │
│  │(CrossEncode)│  │ (Pydantic)  │  │  (PDF/DOCX)  │           │
│  └─────────────┘  └─────────────┘  └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
        │                │                │
┌───────▼────┐   ┌───────▼────┐   ┌───────▼────┐
│ Gemini API │   │ ChromaDB   │   │  SQLite    │
│ (Cloud)    │   │ (Disk)     │   │  (Disk)    │
└────────────┘   └────────────┘   └────────────┘
```

---

## Data Flow

### 1. Document Ingestion

```
PDF/DOCX/TXT → DocumentLoaderManager → Text Extraction
     → Chunking (1000 tokens, 100 overlap)
     → Gemini Embedding API (models/gemini-embedding-001)
     → ChromaDB Persistent Store (data/vector_db/)
```

### 2. Query Processing (RAG)

```
User Query → Query Expansion (3 variants)
     → Vector Search (top_k=10)
     → Cross-Encoder Reranking (top_k=3)
     → Context Deduplication
     → Gemini Chat Completion (gemini-2.0-flash)
     → Quality Evaluation (LLM-as-Judge)
     → Response + Citations
```

### 3. Forecast Generation

```
Chat History (30 latest) + Anomalies + Document Stats
     → [If Simulation Active] + Scenario Parameters
     → Gemini Completion (structured prompt)
     → Risk Entity Extraction (regex: backtick-quoted)
     → Task Board Import (URGENTE/PREVENTIVO/MONITORAGGIO)
     → Knowledge Graph Risk Highlighting
```

### 4. Knowledge Graph

```
Indexed Files → Entity Extraction (filename parsing)
     → Anomaly Mapping (from chat history)
     → Risk Overlay (from forecast)
     → Simulation Overlay (from Impact Simulator)
     → Pyvis Network Visualization
```

---

## Key Files

| File | Lines | Role |
|---|---|---|
| `app_streamlit_real_docs.py` | 2100 | Main UI application |
| `src/config.py` | 310 | Centralized configuration (Pydantic) |
| `src/llm_service.py` | ~400 | Gemini API wrapper |
| `src/vector_store.py` | ~500 | ChromaDB vector store |
| `src/memory_service.py` | 329 | SQLite chat history + Task Board |
| `src/graph_service.py` | 209 | Knowledge Graph builder |
| `src/rate_limiter.py` | 346 | Centralized rate limiting |
| `src/structured_logging.py` | 203 | JSON structured logging |
| `src/logging_config.py` | ~50 | Logging configuration |
| `document_loader.py` | ~400 | Document ingestion pipeline |

---

## Database Schema

### `rag_memory.db` (SQLite)

**`chat_history`** — Stores all Q&A interactions

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `timestamp` | DATETIME | Interaction time |
| `user_query` | TEXT | User's question |
| `ai_response` | TEXT | AI's answer |
| `found_anomalies` | BOOLEAN | Anomaly flag |
| `referenced_docs` | TEXT (JSON) | Source documents |

**`action_tasks`** — Task Board persistence

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `title` | TEXT | Task description |
| `level` | TEXT | URGENTE / PREVENTIVO / MONITORAGGIO |
| `status` | TEXT | pending / completed |
| `created_at` | DATETIME | Creation time |
| `completed_at` | DATETIME | Completion time |
| `source_forecast` | TEXT | Originating forecast |

---

## Rate Limiting Strategy

| Scope | Limit | Algorithm |
|---|---|---|
| Global | 500 tokens bucket, 50/sec refill | Token Bucket |
| Per-User | 5000 req/hour | Token Bucket |
| Per-Endpoint | 10000 req/hour | Token Bucket |

Protected endpoints: `search`, `completion`, `embedding`, `forecast`, `simulation`, `web_monitoring`, `reranking`

---

## API Endpoints (FastAPI — Optional)

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Service health check |
| POST | `/api/query` | Process RAG query |
| GET | `/api/stats` | System statistics |
| POST | `/api/ingest` | Trigger document ingestion |
