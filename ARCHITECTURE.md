# Architettura Tecnica - RAG Locale (Hybrid)

**Scopo**: Blueprint completo dell'implementazione RAG per documentazione IT aziendale.
**Target Hardware**: HP ProBook 440 G11 (16GB RAM, CPU-only).
**Principio Guida**: Hybrid RAG (Local Storage + Cloud Intelligence), GDPR-conscious.

---

## 1. Overview Architetturale

Il sistema è un **Hybrid RAG** che combina la sicurezza dello storage locale con la potenza dell'intelligenza artificiale in cloud.

```mermaid
graph TD
    User[Utente (Browser)] -->|HTTP| App[Streamlit UI]
    App -->|Orchestra| RAGEngine[RAG Engine]
    
    subgraph "Local - HP ProBook"
        RAGEngine -->|Retrieve| VectorStore[Custom Vector Store (Numpy/Pickle)]
        VectorStore -->|Load| LocalDocs[Documenti Locali (PDF/TXT)]
        Ingestion[Ingestion Pipeline] -->|Process| LocalDocs
        Ingestion -->|Index| VectorStore
    end
    
    subgraph "Cloud - Google Cloud"
        RAGEngine -->|Generazione (Chat)| GeminiChat[Google Gemini 2.0 Flash]
        Ingestion -->|Embedding| GeminiEmbed[Google Gemini Embeddings]
        VectorStore -->|Embedding Query| GeminiEmbed
    end
```

### Flusso Dati
1.  **Ingestion**: I documenti locali vengono letti, suddivisi in chunk e inviati a Google Gemini per calcolare gli *embedding* (vettori numerici).
2.  **Storage**: I vettori e il testo dei documenti vengono salvati **SOLO localmente** su disco (`data/vector_db/vector_store.pkl`).
3.  **Query**:
    -   La domanda dell'utente viene convertita in vettore (via Gemini Cloud).
    -   La ricerca semantica avviene **localmente** sul laptop (CPU-based).
    -   I chunk rilevanti vengono recuperati dal disco.
4.  **Generazione**:
    -   Il prompt (Domanda + Chunk Rilevanti) viene inviato a **Google Gemini Cloud**.
    -   Gemini genera la risposta finale.

---

## 2. Componenti Dettagliati

### 2.1 LLM & Embeddings (Cloud)
-   **Provider**: Google Gemini API via `google-genai` client.
-   **Modello Chat**: `gemini-2.0-flash` (Veloce, economico, alta finestra di contesto).
-   **Modello Embedding**: `models/text-embedding-004`.
-   **Configurazione**: `src/config.py` -> `GeminiConfig`.

### 2.2 Custom Vector Store (Local)
-   **Tecnologia**: Implementazione custom in Python pura (`src/vector_store.py`).
-   **Backend**: `numpy` per calcoli vettoriali, `pickle` per persistenza.
-   **Motivazione**: Sostituito ChromaDB per ridurre l'overhead su hardware limitato (HP ProBook) e rimuovere dipendenze complesse.
-   **Performance**: Utilizza moltiplicazione matriciale pre-calcolata per ricerca O(1) + ottimizzazioni vettoriali.

### 2.3 Document Ingestion
-   **Pipeline**: `src/document_ingestion.py`.
-   **Formati**: PDF (via `pypdf`/`pdf_worker.py`), TXT, MD, DOCX.
-   **Chunking**: RegEx-based sentence splitting (preserva struttura frasi).
-   **Safety**: I PDF vengono processati in un sottoprocesso separato per evitare crash dell'applicazione principale.

### 2.4 User Interface
-   **Framework**: Streamlit (`app_streamlit_real_docs.py`).
-   **Features**:
    -   Chat interattiva.
    -   Visualizzazione citazioni e fonti.
    -   Metriche di qualità (Faithfulness/Relevance) in tempo reale.
    -   Suggerimenti domande follow-up.

---

## 3. Sicurezza e Dati

> [!IMPORTANT]
> **Hybrid Architecture Note**:
> Sebbene lo storage sia locale, **il contenuto dei documenti viene inviato a Google Cloud** temporaneamente per la generazione degli embedding e delle risposte.

### Data Flow & Privacy
-   **A Riposo**: I documenti originali e il database vettoriale risiedono esclusivamente sul disco del laptop (`c:\Users\...\data\`).
-   **In Transito**: I dati inviati a Gemini (testo dei chunk, query utente) viaggiano su canale cifrato (HTTPS/TLS).
-   **No Addestramento**: Secondo i termini standard API di Google Cloud, i dati inviati via API **non** vengono usati per addestrare i modelli (verificare i termini specifici del proprio piano).

---

## 4. Requisiti di Sistema

-   **OS**: Windows 10/11.
-   **Python**: 3.10+.
-   **API Key**: Richiede una API Key Google Gemini valida (variabile d'ambiente `GEMINI_API_KEY`).
-   **Network**: Connessione Internet attiva (per le chiamate API Gemini).

---

## 5. Phase 8 - Semantic Understanding & Performance (Nuovo!)

### 5.1 Semantic Document Summarization
```
DocumentSummarizer (src/document_summarizer.py)
├─ summarize_document()        [LLM-based summary with keyword fallback]
├─ extract_key_points()        [Extract main topics from documents]
├─ _summarize_llm()            [Google Gemini Flash summary]
├─ _summarize_extractive()     [Fallback: keyword-based extraction]
└─ Caching                      [Disk-persisted with LRU eviction]

Vector Store Extensions
├─ update_document_summary()    [Store summaries in metadata]
└─ get_document_summaries()     [Retrieve all cached summaries]
```

**Flow**:
1. Durante ingestion, i documenti vengono automaticamente sumarizzati
2. Sommari e key points sono memorizzati nei metadata del vector store
3. UI mostra sommari espandibili nella Document Library
4. Caching on-disk per performance

### 5.2 Document Similarity Matrix
```
DocumentSimilarityMatrix (src/document_similarity_matrix.py)
├─ compute_similarity_matrix()  [NxN cosine similarity (O(N²))]
├─ get_related_documents()      [Find similar docs to a given doc]
├─ get_most_similar_pairs()     [Top-k most similar document pairs]
├─ get_clustering()             [Hierarchical clustering]
└─ build_heatmap_data()         [Plotly visualization data]

UI Integration
├─ Interactive Heatmap          [Analysis tab - "Matrice Similarità"]
├─ Related Documents            [Suggestions in Document Library]
└─ Cluster Visualization        [Statistics and grouping]
```

**Algorithm**:
- Cosine Similarity: `similarity[i,j] = embedding[i] · embedding[j] / (||e[i]|| * ||e[j]||)`
- Diagonal zeroed (no self-similarity)
- Cached to disk for large matrices (1615x1615 = 8.4MB)

### 5.3 Performance Caching Infrastructure
```
Cache Hierarchy
├─ QueryExpansionCache         [1-hour TTL, 500-item max]
│  └─ Target: 50%+ hit rate for repeated query variants
│
└─ VisionProcessingCache       [24-hour TTL, 1000-item max]
   └─ Target: 70%+ hit rate for batch image processing

Implementation
├─ LRU eviction                [Least-recently-used removal]
├─ Hash-based image keys       [SHA256 for vision results]
└─ TTL expiration              [Automatic cleanup]
```

**Usage Pattern**:
```python
# Query Expansion Cache
from src.cache import get_query_expansion_cache
cache = get_query_expansion_cache()
cached = cache.get(query)
if cached is None:
    expanded = expand_query(query)  # LLM call
    cache.set(query, expanded)

# Vision Cache
from src.cache import get_vision_processing_cache
cache = get_vision_processing_cache()
image_hash = sha256(image_bytes).hexdigest()
cached = cache.get_by_hash(image_hash)
if cached is None:
    result = process_image(image)  # Vision API call
    cache.set_by_hash(image_hash, result)
```

### 5.4 Test Coverage
```
test_fase8_summarization.py     [8 tests]
├─ Initialization, content summarization
├─ Key points extraction, caching
└─ Vector store integration

test_fase8_similarity.py        [7 tests]
├─ Matrix computation, statistics
├─ Related documents, clustering
└─ Heatmap data format

test_fase8_optimizations.py     [15 tests]
├─ QueryExpansionCache functionality
├─ VisionProcessingCache operations
├─ Cache singletons, performance
└─ Batch processing patterns

Total: 30/30 tests PASSING
Regression: 22/22 Phase 1-7 tests still PASSING
```

---

## 6. Sviluppi Futuri (Roadmap)
-   [x] **Phase 8**: Semantic Understanding + Performance (COMPLETATO)
-   [ ] **Full Local Fallback**: Reintegrare un modello locale (es. Ollama/Mistral) per operare offline.
-   [ ] **Reranking**: Migliorare la precisione con un Cross-Encoder locale.
-   [ ] **Multimodal**: Espandere l'uso della Vision API per analizzare grafici complessi nei PDF.

---
**Ultimo Aggiornamento**: Febbraio 2026 (Phase 8 Completato)
