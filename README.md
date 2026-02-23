# RAG Locale (Hybrid) - Sistema Aziendale Documentale

## Overview

Sistema **Hybrid RAG** (Retrieval-Augmented Generation) per l'interrogazione intelligente della documentazione IT aziendale.
Progettato per girare su un hardware standard (HP ProBook 440 G11) mantenendo l'indice e i documenti in locale, delegando i calcoli pesanti (embedding/chat) a Google Gemini Cloud.

### Componenti Chiave
1.  **UI**: Interfaccia Web moderna e reattiva (Streamlit).
2.  **LLM**: Google Gemini 2.0 Flash (Cloud).
3.  **Vector Store**: Custom Local Implementation (Numpy/Pickle).
4.  **Ingestion**: Pipeline parallela per PDF/TXT/MD/DOCX.

---

## Quick Start (3 Minuti)

### 1. Prerequisiti
-   **Python 3.10+** installato.
-   **Google Gemini API Key** (ottenibile da Google AI Studio).

### 2. Installazione
```bash
# Entra nella cartella (se non ci sei già)
cd "C:\Users\ChristianRobecchi\Downloads\RAG LOCALE"

# Installa le dipendenze
pip install -r requirements.txt
```

### 3. Configurazione
Crea un file `.env` nella root del progetto (puoi copiare `.env.example`):
```ini
# .env
GEMINI_API_KEY=tua-chiave-api-qui
```

### 4. Avvio
Lancia l'applicazione reale (con supporto documenti veri):
```bash
streamlit run app_streamlit_real_docs.py
```
Il browser si aprirà automaticamente su `http://localhost:8501`.

---

## Caricamento Documenti

1.  Apri l'app nel browser.
2.  Assicurati di avere i tuoi file (PDF, TXT, ecc.) nella cartella `documents/` (o specifica un percorso personalizzato dalla sidebar).
3.  Clicca su **"Load Documents"** nella sidebar per indicizzare.
4.  Inizia a fare domande!

---

## Funzionalità Phase 8 (Nuove!)

### 📝 Semantic Document Summarization
- **Auto-summarization**: Sommari automatici generati durante l'ingestion
- **Key Points**: Estrazione automatica dei punti chiave da ogni documento
- **Caching**: Memorizzazione in cache per performance
- **UI**: Visualizzazione espandibile nella Document Library

### 🔗 Document Similarity Matrix
- **Similarity Computation**: Calcolo della matrice di similarità coseno tra tutti i documenti
- **Interactive Heatmap**: Visualizzazione Plotly nella scheda Analysis
- **Related Documents**: Suggerimenti di documenti correlati
- **Clustering**: Raggruppamento automatico in cluster semantici

### ⚡ Performance Optimizations (Caching)
- **QueryExpansionCache**: Cache per query espanse (1-hour TTL, 50%+ hit rate target)
- **VisionProcessingCache**: Cache per elaborazione visiva (24-hour TTL, 70%+ hit rate target)
- **Pronto per integrazione**: Stub di integrazione pronti in query_expansion.py e vision_service.py

## Note Architetturali

> [!WARNING]
> Questo sistema è **IBRIDO**, non completamente offline.
> - **Locale**: Storage dei vettori, documenti originali, metadata, sommari.
> - **Cloud**: Il testo viene inviato a Google per generare embedding e risposte.

Vedi `ARCHITECTURE.md` per i dettagli tecnici completi.

## Testing Phase 8

Eseguire i test per Phase 8:
```bash
# Tutti i test Phase 8 (30 test totali)
pytest test_fase8_*.py -v

# Test singoli
pytest test_fase8_summarization.py -v    # 8 test
pytest test_fase8_similarity.py -v       # 7 test
pytest test_fase8_optimizations.py -v    # 15 test

# Test di regressione (verifica che Phase 1-7 sia ancora funzionante)
pytest test_fase16_hybrid_search.py -v   # 22 test
```

**Status**:
- Phase 1-7: ✅ 22/22 test pass (no regressions)
- Phase 8: ✅ 30/30 test pass
