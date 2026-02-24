# RAG LOCALE - Sistema Ripristinato e Riavviato

## Stato del Sistema

### Verifica Completata (PASS)
- [PASS] Vector Store: 7.67 MB con 74 documenti ingestionati
- [PASS] Documenti: 74 file PDF nel database
- [PASS] Connessione API Gemini: OK
- [PASS] Embedding test: Vettori di 3072 dimensioni
- [PASS] Completion test: Generazione testo OK

## Problemi Risolti

### 1. ReadTimeoutError (120s)
**Problema**: L'API Gemini timeout dopo 120 secondi durante operazioni lunghe.
**Soluzione**:
- Aumentato timeout a 300 secondi (5 minuti)
- Aggiunto dedicated timeout per embedding e completion
- Implementato exponential backoff: 1s, 2s, 4s, 8s, 16s

### 2. ConnectionResetError
**Problema**: Connessione reset durante trasferimento dati.
**Soluzione**:
- Retry logic migliorata (max 5 tentativi)
- Gestione specifica di `Timeout`, `ReadTimeout`, `ConnectionError`
- Logging migliorato per diagnostica

### 3. Streamlit Crash
**Problema**: Streamlit si crashava durante timeout.
**Soluzione**:
- Aggiunto error handling specifico per timeout
- Messaggi utente migliorati
- Client-side caching abilitato
- Logging per debug

## File Modificati

### 1. `src/config.py`
Aggiunti timeout e retry config:
```python
request_timeout: int = 300          # Timeout richiesta (5 min)
embedding_timeout: int = 300        # Timeout embedding (5 min)
completion_timeout: int = 300       # Timeout completion (5 min)
max_retries: int = 5                # Max 5 tentativi
retry_base_delay: float = 1.0       # Base delay 1s per exponential backoff
```

### 2. `src/llm_service.py`
Miglioramenti:
- Retry logic per `get_embedding()`: gestisce Timeout/ConnectionError
- Retry logic per `get_embeddings_batch()`: batch-level retry
- Retry logic per `completion()`: 5 tentativi con exponential backoff
- Import di `requests.exceptions` per timeout handling

### 3. `src/app_ui.py`
Miglioramenti:
- Logging configurato
- Timeout configuration UI (sezione diagnostica)
- Error handling specifico per TimeoutError e ConnectionError
- Messaggi utente migliorati
- Client-side caching abilitato

### 4. `health_check.py` (NUOVO)
Script di diagnostica che verifica:
- Vector store existe e ha dati
- Documenti sono nel folder
- Connessione API Gemini
- Embedding test
- Completion test

### 5. `run_streamlit.bat` (NUOVO)
Script di avvio con impostazioni ottimali

## Come Avviare il Sistema

### Opzione 1: Batch Script (Windows)
```bash
run_streamlit.bat
```

### Opzione 2: Python Diretto
```bash
streamlit run src/app_ui.py
```

### Opzione 3: Health Check Prima dell'Avvio
```bash
python health_check.py
```

## Configurazione Timeout Globale

I timeout sono configurati in `src/config.py` nella classe `GeminiConfig`:

```python
# Timeouts (in seconds)
request_timeout: int = 300           # 5 minuti
embedding_timeout: int = 300         # 5 minuti
completion_timeout: int = 300        # 5 minuti
max_retries: int = 5                 # Numero tentativi
retry_base_delay: float = 1.0        # Delay base per exponential backoff
```

## Sequenza di Retry

Quando un timeout o connection error accade:

1. **Tentativo 1**: Immediato
2. **Tentativo 2**: Dopo 1 secondo
3. **Tentativo 3**: Dopo 2 secondi
4. **Tentativo 4**: Dopo 4 secondi
5. **Tentativo 5**: Dopo 8 secondi

Totale tempo massimo attesa: ~15 secondi tra i retry, con timeout di 5 minuti per ogni tentativo.

## Diagnostica

### Vedere i log di Streamlit
```bash
# Streamlit memorizza i log nel terminale
# Cercate per [TIMEOUT/CONNECTION] per vedere retry
```

### Test manuale embedding
```python
from src.llm_service import get_llm_service

llm = get_llm_service()
embedding = llm.get_embedding("Test text")
print(f"Embedding length: {len(embedding)}")
```

### Test manuale completion
```python
from src.llm_service import get_llm_service

llm = get_llm_service()
response = llm.completion("Domanda di test")
print(response)
```

## Cosa Aspettarsi

### Durante Embedding
- Prima volta: ~2-3 secondi
- Con retry: fino a ~30 secondi nel caso peggiore (5 tentativi x 6s medio)

### Durante Completion
- Prima volta: ~3-5 secondi
- Con retry: fino a ~40 secondi nel caso peggiore

### Nel Caso di Timeout Persistente
- Streamlit mostra messaggio: "Timeout durante la generazione della risposta (riprova, il sistema ritenta automaticamente)"
- Sistema ritenta automaticamente fino a 5 volte
- Dopo 5 fallimenti: errore definitivo con log dettagliato

## Prossimi Passi Opzionali

1. **Monitoraggio**: Aggiungere prometheus metrics per timeout rate
2. **Circuit Breaker**: Implementare circuit breaker se timeout rate > 30%
3. **Connection Pooling**: Riutilizzare connessioni HTTP
4. **Async Processing**: Convertire a async/await per non bloccare UI

## Note

- Il vector store (7.67 MB) contiene tutti i documenti ingestionati
- Tutti i documenti sono salvati e disponibili per query
- La configurazione è robusta per client su CPU singola (HP ProBook)
- Timeout di 300s è sufficiente anche per documenti molto lunghi

---

**Data creazione**: 2026-02-18
**Versione**: 2.1 (Timeout Handling Improved)
