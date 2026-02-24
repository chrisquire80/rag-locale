# 🚀 STARTUP GUIDE - RAG Locale After FASE 5

## Pre-requisiti ✅
- ✅ Python 3.14
- ✅ Tutte le dipendenze installate (`pip install -r setup/requirements.txt`)
- ✅ GEMINI_API_KEY in `.env` file
- ✅ FASE 5 hotfixes applicati

---

## Avvio Veloce (1 minuto)

### 1. Apri 2 Terminal

**Terminal 1 - Backend**:
```bash
cd "C:\Users\ChristianRobecchi\Downloads\RAG LOCALE"
python src/api.py
```
Attendi: `Uvicorn running on http://0.0.0.0:5000`

**Terminal 2 - Frontend**:
```bash
cd "C:\Users\ChristianRobecchi\Downloads\RAG LOCALE"
streamlit run src/frontend.py
```
Attendi: Browser si apre a `http://localhost:8501`

---

## Caricamento Documenti

### Metodo 1: Via Interfaccia Streamlit (Facile)
1. Clicca "Upload Document"
2. Seleziona PDF/TXT/DOCX
3. Aspetta "✅ Successfully uploaded"

### Metodo 2: Via Command Line (Batch)
```bash
for file in *.pdf; do
    curl -X POST -F "file=@$file" http://localhost:5000/api/documents/upload
    echo "Uploaded: $file"
done
```

---

## Timing Atteso

| Azione | Tempo |
|--------|-------|
| Upload 1 PDF | 2-3 secondi |
| Upload 70 PDF | 2-3 minuti |
| Query ricerca | 500-600ms |

Il backoff di 300ms su Gemini è **intenzionale** per evitare throttling.

---

## Verifiche di Salute

### Status Gemini
Nei logs backend dovresti vedere:
```
✓ Connessione Gemini API: OK
Model: gemini-2.0-flash
```

### Status Vector Store
```bash
ls -lah data/vector_db/vector_store.pkl
# Deve essere > 1MB dopo alcuni documenti
```

### Cleanup Temp Files
```bash
ls data/documents/*.json.temp
# Deve essere VUOTO
```

---

## Se Ingestion Stalla

### Quick Fix
Aumenta timeout in `src/document_ingestion.py` linea 137:
```python
# Cambio da 300 a 600
subprocess.run([...], timeout=600)
```

### Debug
```bash
tail -f logs/rag.log | grep -i "error\|timeout\|fail"
```

---

## Report Disponibili

- `FASE5_COMPLETION_REPORT.md` - Dettagli tecnici FASE 5
- `test_fase5_fixes.py` - Test suite (esegui: `python test_fase5_fixes.py`)

---

**Pronto!** Carica i tuoi documenti 📚

Sistema supporta fino a **100+ documenti** senza problemi.
