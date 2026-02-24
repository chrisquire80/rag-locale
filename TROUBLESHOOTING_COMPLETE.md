# RAG LOCALE - Guida Troubleshooting Completa

## ✅ STATO VERIFICATO

```
Vector Store:        7.67 MB ✓
Documents:           286 ✓
Config:              OK ✓
Imports:             OK ✓
Gemini API:          Ready ✓
```

---

## 🚀 AVVIO RAPIDO

### Metodo 1: Click sul .bat file (Consigliato)
```
Doppio-click su: start_ui.bat
Aspetta 10-15 secondi
Browser si apre automaticamente
```

### Metodo 2: Terminal
```powershell
cd "C:\Users\ChristianRobecchi\Downloads\RAG LOCALE"
python -m streamlit run src/app_ui.py
```

### Metodo 3: Python launcher
```powershell
python launch_ui.py
```

---

## ⚠️ PROBLEMI COMUNI E SOLUZIONI

### PROBLEMA 1: "ERR_CONNECTION_REFUSED" nel browser

**Sintomi:**
- Browser dice "Cannot reach localhost:8501"
- Console del terminal è pulita

**Cause Probabili:**
1. Streamlit non ha finito di avviarsi
2. Porta 8501 è in uso da un altro processo
3. Firewall blocca la connessione

**Soluzioni:**

**Soluzione A** (probabilità: 90%):
```
Attendi 10-15 secondi dal double-click
Poi ricarica il browser (F5)
```

**Soluzione B** (probabilità: 8%):
```powershell
# Verifica se porta 8501 è in uso
netstat -ano | findstr :8501

# Se c'è un processo, termina:
taskkill /PID [numero] /F

# Poi riavvia start_ui.bat
```

**Soluzione C** (probabilità: 2%):
```
Aggiungi un'eccezione firewall:
1. Apri Windows Defender Firewall
2. "Allow an app through firewall"
3. Consenti Python.exe
```

---

### PROBLEMA 2: "ModuleNotFoundError: No module named 'streamlit'"

**Sintomi:**
- Terminal dice: `No module named 'streamlit'`
- Avvio fallisce immediatamente

**Soluzione:**
```powershell
cd "C:\Users\ChristianRobecchi\Downloads\RAG LOCALE"
python -m pip install streamlit google-genai numpy pandas chromadb
```

---

### PROBLEMA 3: "GEMINI_API_KEY not found"

**Sintomi:**
- Terminal mostra: `ValueError: GEMINI_API_KEY not found`
- O: `APIConnectionError`

**Soluzione:**

1. Crea file `.env` nella cartella RAG LOCALE:
```
GEMINI_API_KEY=your_actual_key_here
```

2. Oppure imposta variabile d'ambiente Windows:
```powershell
$env:GEMINI_API_KEY = "your_actual_key_here"
```

3. Riavvia Streamlit

---

### PROBLEMA 4: Timeout durante caricamento PDF

**Sintomi:**
- "Connection timeout" nel browser
- Terminal mostra: `ReadTimeoutError: HTTP 120`
- O: `ConnectionResetError`

**Questo è NORMALE durante l'ingestion di file grandi!**

**Come gestire:**
1. **Non chiudere il browser o il terminal**
2. **Aspetta**: Il sistema ha retry automatici (fino a 5 tentativi)
3. **Tempo massimo**: 5-10 minuti per file grandi
4. **Se davvero non finisce** (dopo 15 min):
   - Chiudi start_ui.bat (Ctrl+C)
   - Aspetta 10 secondi
   - Riavvia

**Prevenzione:**
- Carica un PDF alla volta (non bulk)
- PDF piccoli (<10MB) funzionano meglio
- File con molte immagini: più lenti

---

### PROBLEMA 5: "The Streamlit app crashed"

**Sintomi:**
- Pagina bianca nel browser
- Terminal mostra errore con traceback

**Soluzioni:**

**A) Se l'errore è nel file app_ui.py:**
```
1. Leggi l'errore nel terminal
2. Nota il file e la linea
3. Contatta support con lo screenshot
```

**B) Se è Memory error:**
```
Chiudi tutte le altre applicazioni:
  • Chiudi browser
  • Chiudi editor
  • Chiudi altre finestre
Riavvia Streamlit
```

**C) Se è random/intermittente:**
```
Riavvia il PC
Riavvia Streamlit
Se persiste: check_system.bat
```

---

### PROBLEMA 6: Vector store non contiene i dati

**Sintomi:**
- "No documents found" quando fai una query
- Search results vuoti

**Verifica:**
```powershell
cd "C:\Users\ChristianRobecchi\Downloads\RAG LOCALE"
python -c "
import sys
sys.path.insert(0, 'src')
from vector_store import get_vector_store
vs = get_vector_store()
print(f'Documents: {vs.get_stats()[\"total_documents\"]}')
"
```

**Se la risposta è 0:**
```
Carica i PDF usando "Importa Documenti" nella UI
```

**Se la risposta è >0:**
```
Vector store ha dati - il problema è nel search
Prova con una query più semplice
```

---

### PROBLEMA 7: Memoria piena / "MemoryError"

**Sintomi:**
- Terminal mostra: `MemoryError`
- O: Pagina diventa molto lenta
- Sistema diventa freezato

**Soluzione immediata:**
```
1. Chiudi Streamlit (Ctrl+C)
2. Chiudi il browser
3. Aspetta 30 secondi (memoria si libera)
4. Riavvia
```

**Prevenzione:**
```
Carica documenti in batch piccoli:
  • 5-10 PDF per volta
  • Non 50+ PDF contemporaneamente
  • Aspetta completamento prima di caricarne altri
```

---

## 🔍 DEBUG AVANZATO

### Verificare che tutto funziona:
```powershell
cd "C:\Users\ChristianRobecchi\Downloads\RAG LOCALE"

# Test 1: Import modules
python check_system.bat

# Test 2: Check vector store
python -c "
import sys; sys.path.insert(0, 'src')
from vector_store import get_vector_store
vs = get_vector_store()
print(f'OK: {vs.get_stats()[\"total_documents\"]} docs')
"

# Test 3: Check API connection
python -c "
import sys; sys.path.insert(0, 'src')
from llm_service import get_llm_service
llm = get_llm_service()
print('OK: API connected')
"
```

### Vedere i log completi:
```powershell
# Continua a leggere i log mentre accade qualcosa:
tail -f logs/rag.log

# O su Windows PowerShell:
Get-Content logs/rag.log -Wait
```

### Testare API direttamente:
```powershell
cd "C:\Users\ChristianRobecchi\Downloads\RAG LOCALE"
python -c "
import sys; sys.path.insert(0, 'src')
from llm_service import get_llm_service

llm = get_llm_service()

# Test embedding
emb = llm.get_embedding('test')
print(f'Embedding OK: {len(emb)} dimensions')

# Test completion
resp = llm.completion('Say hello')
print(f'Completion OK: {resp[:50]}...')
"
```

---

## 📊 COME INTERPRETARE I LOG

### Esempio log buono:
```
2026-02-18 10:00:00 | app_ui | INFO | Streamlit app started
2026-02-18 10:00:05 | vector_store | INFO | Adding 10 documents
2026-02-18 10:00:10 | llm_service | INFO | Embedding generated (3072 dimensions)
```

### Esempio log con warning (OK):
```
2026-02-18 10:05:00 | urllib3 | WARNING | Retrying connection...
2026-02-18 10:05:05 | urllib3 | WARNING | Retry (total=2)...
2026-02-18 10:05:10 | llm_service | INFO | Embedding OK (after retry)
```
→ Questo è NORMALE, il retry logic sta funzionando

### Esempio log con errore (BAD):
```
2026-02-18 10:10:00 | llm_service | ERROR | ConnectionError: Failed to connect
2026-02-18 10:10:01 | app_ui | CRITICAL | App crashed
```
→ Problema serio, contatta support

---

## 🆘 QUANDO CONTATTARE SUPPORT

Se hai provato tutte le soluzioni e il problema persiste:

1. **Salva lo screenshot dell'errore**
2. **Copia i log dalla console** (ultimi 50 righe)
3. **Nota il timestamp quando è accaduto**
4. **Fornisci**:
   - Riga esatta dell'errore
   - Cosa stavi facendo quando è accaduto
   - Quanti tentativi hai fatto
   - Quale soluzione hai provato

---

## ✅ CHECKLIST PRE-LAUNCH

Prima di ogni avvio:

- [ ] Ho .env con GEMINI_API_KEY
- [ ] Vector store esiste (data/vector_db/vector_store.pkl)
- [ ] Ho 286 documenti nel store
- [ ] Nessun altro processo usa porta 8501
- [ ] Ho almeno 2GB di RAM libera
- [ ] Internet connection è stabile

---

## 🎯 PERFORMANCE EXPECTATIONS

Quando usi il sistema, aspettati:

| Operazione | Tempo | Note |
|-----------|-------|------|
| Avvio Streamlit | 10-15s | Prima volta più lenta |
| Query semplice | 2-5s | Con cache |
| Query con immagini | 5-15s | Vision API è lenta |
| Upload 1 PDF | 10-30s | Dipende da size |
| Upload 5 PDF | 1-3 min | Se non troppo grandi |

Se è molto più lento: check_system.bat e vedi logs

---

## 🎉 SUCCESSO!

Se tutto funziona:
- ✅ Browser apre a http://localhost:8501
- ✅ Puoi scrivere domande
- ✅ Vedi risposte con sources
- ✅ Puoi caricare PDF

Allora sei pronto per usare il sistema! 🚀

---

**Ultima cosa:** Lascia sempre il terminal aperto mentre usi Streamlit.
Se lo chiudi, il server si ferma!

Buon uso! 🎉
