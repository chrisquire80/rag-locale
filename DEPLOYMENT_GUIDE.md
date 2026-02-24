# Guida di Deployment - RAG Locale

**Ambiente**: HP ProBook 440 G11
**Utente**: Christian Robecchi (ETJCA)
**Data**: Febbraio 2026
**Conformità**: GDPR, Zero-Cloud Architecture

---

## Sommario

1. [Pre-requisiti](#pre-requisiti)
2. [Installazione Passo per Passo](#installazione-passo-per-passo)
3. [Configurazione LM Studio](#configurazione-lm-studio)
4. [Ingestion Documenti IT](#ingestion-documenti-it)
5. [Esecuzione e Testing](#esecuzione-e-testing)
6. [Troubleshooting](#troubleshooting)
7. [Manutenzione Operativa](#manutenzione-operativa)

---

## Pre-requisiti

### Hardware Verificato
- ✅ HP ProBook 440 G11
- ✅ CPU: Intel Core i5/i7 13ª gen (Raptor Lake)
- ✅ RAM: 16GB DDR5
- ✅ Storage: 512GB-1TB NVMe
- ✅ OS: Windows 11 Pro 10.0.26200

### Software Richiesto
1. **Python 3.11+** - Runtime Python
2. **LM Studio** - Server di inferenza locale
3. **Git** (opzionale) - Per version control

### Connettività
- ✅ Internet per download Python, dipendenze, modello LLM (~5GB)
- ✅ Dopo setup: zero dipendenze cloud (fully offline-capable)

### Account e Privilegi
- ✅ Accesso amministratore per configurazione firewall
- ✅ Accesso ai percorsi: C:\Users\ChristianRobecchi\Downloads\RAG\ LOCALE

---

## Installazione Passo per Passo

### Fase 1: Setup Python (30 minuti)

#### 1.1 Scaricare Python
```
Visita: https://www.python.org/downloads/
Scarica: Python 3.11 (o 3.12)
Scegli: Windows installer (64-bit)
```

#### 1.2 Installare Python
```powershell
# Esegui l'installer scaricato
# IMPORTANTE DURING INSTALLATION:
# ✓ Checkbox "Add Python to PATH"
# ✓ Checkbox "Install pip"
# ✓ Scegli "Install for all users" (opzionale)
```

#### 1.3 Verificare Installazione
```powershell
python --version
pip --version

# Output atteso:
# Python 3.11.x
# pip 23.x.x
```

### Fase 2: Setup Virtual Environment (10 minuti)

```powershell
# Naviga alla cartella progetto
cd C:\Users\ChristianRobecchi\Downloads\RAG\ LOCALE

# Crea virtual environment
python -m venv .venv

# Attiva venv
.\.venv\Scripts\Activate.ps1

# Se ricevi errore su execution policy:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Aggiorna pip
python -m pip install --upgrade pip setuptools wheel
```

### Fase 3: Installazione Dipendenze (15 minuti)

```powershell
# Assicurati che venv sia attivato (prompt deve mostrare "(.venv)")
# Installa dipendenze
pip install -r setup/requirements.txt

# Verifica installazione
pip list

# Deve mostrare: chromadb, llamaindex, openai, pydantic, etc.
```

### Fase 4: Installazione LM Studio (varabile, dipende da connessione)

#### 4.1 Scarica e Installa
```
1. Visita: https://lmstudio.ai
2. Scarica: LM Studio for Windows
3. Esegui installer (non richiede privilegi admin)
4. Completa setup wizard
```

#### 4.2 Verifica Installazione
```powershell
# LM Studio si avvia dall'applicazione
# Aprire il programma
```

#### 4.3 Scarica Modello
```
Dentro LM Studio:
1. Clicca tab "Discover"
2. Cerca: "Mistral 7B Instruct Q4_K_M"
3. Clicca "Download" (dimensione ~5GB)
4. Attendi completamento (può richiedere 20-60 minuti)
```

#### 4.4 Configura Local Server
```
Dentro LM Studio:
1. Clicca tab "Local Server"
2. Seleziona modello da dropdown: "mistral-7b-instruct-v0.3"
3. Verifica impostazioni (vedi sezione "LM Studio Configuration")
4. Clicca "Start Server"
5. Deve mostrare: "Server is listening on..."
```

---

## Configurazione LM Studio

### Memory Management (CRITICO per HP ProBook 440 - 16GB RAM)

**Accedi a**: LM Studio → Settings (⚙️ icon)

| Parametro | Valore | Perché |
|-----------|--------|--------|
| **Idle TTL** | 300 secondi | Libera modello se inattivo 5 min |
| **Auto-Evict** | ON | Scarica modello se RAM saturata |
| **GPU Offload** | OFF | CPU-only per stabilità |
| **RAM Buffer** | Max 12GB | Lascia 4GB al sistema operativo |

### Network Configuration (SICUREZZA)

| Parametro | Valore | Perché |
|-----------|--------|--------|
| **Serve on Local Network** | OFF | Zero-Cloud: accesso solo 127.0.0.1 |
| **Binding Address** | 127.0.0.1 | Loopback only |
| **Port** | 1234 | Default, firewall-bloccato esternamente |

### Performance Settings

| Parametro | Valore | Perché |
|-----------|--------|--------|
| **Context Length** | 4096-8192 | Balance tra velocità e qualità |
| **Max Response Length** | 1024 | Riduce latenza |
| **Temperature** | 0.3 | Determinismos (buono per documenti) |

### Verifica Connessione
```powershell
# Con venv attivato, esegui:
curl http://localhost:1234/v1/models

# Output atteso JSON:
# {"object": "list", "data": [{"id": "mistral-7b-instruct-v0.3", ...}]}

# Se non funziona:
# 1. LM Studio non è avviato
# 2. Modello non è caricato
# 3. Firewall bloccando porta 1234
```

---

## Ingestion Documenti IT

### Estructura Documenti

I tuoi documenti IT devono essere posizionati in:
```
C:\Users\ChristianRobecchi\Downloads\RAG\ LOCALE\data\documents\
```

**Formati supportati**:
- `.pdf` - PDF (documenti scansionati e testo)
- `.txt` - Plain text (README, policy)
- `.md` - Markdown (wiki, documentazione)
- `.docx` - Word documents

### Esempio: Aggiungi Documenti

```powershell
# Copia i tuoi documenti IT in data/documents/
# Esempi:
# - policy_smartworking.txt
# - security_procedures.pdf
# - it_compliance.docx
# - infrastructure_guide.md

# Il sistema creerà automaticamente documenti di test se empty
```

### Preparazione Documenti (Best Practice)

**Chunking Ottimale**:
- 📄 Dividi documenti lunghi in sezioni logiche
- 🏷️ Usa header chiari (## Sezione, # Capitolo)
- 📝 Mantieni frasi complete (non spezzare a metà parola)

**Esempio Policy**:
```
# POLICY SMART WORKING 2024

## 1. Principi Generali
Testo qui...

## 2. Requisiti Tecnici
Testo qui...
```

### Eseguire Ingestion Manualmente

```powershell
# Con venv attivato
python -c "
from src.document_ingestion import DocumentIngestionPipeline
pipeline = DocumentIngestionPipeline()
total = pipeline.ingest_from_directory()
print(f'Ingestiti {total} chunks')
"
```

---

## Esecuzione e Testing

### Test 1: Verifica Setup Completo

```powershell
# Con venv attivato
cd C:\Users\ChristianRobecchi\Downloads\RAG\ LOCALE

python setup/verify_setup.ps1  # Opzionale se hai creato lo script
```

### Test 2: Avvia RAG Interattivo

```powershell
# Con venv attivato
python src/main.py

# Output atteso:
# ╔════════════════════════════════════════════════════════════╗
# ║           🚀 RAG LOCALE - Sistema Aziendale              ║
# ║       Zero-Cloud • Sovranità Dato • GDPR Compliant      ║
# ╚════════════════════════════════════════════════════════════╝
#
# 💬 Domanda: _
```

### Test 3: Domanda di Prova

```
💬 Domanda: Quali sono i requisiti tecnici per smart working?

[Output: Mostra chunk pertinenti e risposta generata]
```

### Sessione Interattiva

```powershell
# Il sistema entra in loop interattivo:
# 1. Inserisci domanda
# 2. Sistema recupera chunk (con HITL validation)
# 3. Umano approva o declina
# 4. Se approva, genera risposta
# 5. Mostra risposta con citazioni

# Digita "esci" per uscire
```

---

## Troubleshooting

### Problema: Python non trovato
```
❌ Error: 'python' is not recognized

Soluzioni:
1. Riavvia PowerShell dopo installazione Python
2. Verifica che "Add to PATH" fosse selezionato durante installazione
3. Aggiungi manualmente PATH:
   [System] → Environment Variables → PATH → Aggiungi: C:\Users\...\AppData\Local\Programs\Python\Python311
```

### Problema: LM Studio connection refused
```
❌ Error: Impossibile connettersi a LM Studio (http://localhost:1234)

Soluzioni:
1. Apri LM Studio application
2. Accedi a "Local Server" tab
3. Verifica che modello sia selezionato nel dropdown
4. Clicca "Start Server"
5. Attendi messaggio "Server is listening on..."
```

### Problema: ChromaDB errors
```
❌ Error: chromadb initialization failed

Soluzioni:
1. Elimina cartella storage: data/vector_db/
2. Ricrea con: python src/vector_store.py
3. Re-ingesta documenti: python src/main.py
```

### Problema: RAM piena (System freeze)
```
⚠️ Laptop diventa lento durante query

Soluzioni:
1. Aumenta LM Studio "Idle TTL" a 60 secondi (scarica modello ogni minuto)
2. Riduci CHROMADB__HNSW_CONSTRUCTION_EF da 200 a 100
3. Riduci RAG__SIMILARITY_TOP_K da 5 a 3
4. Chiudi altre applicazioni durante uso
```

### Problema: Risposte inaccurate
```
❌ RAG genera risposta non pertinente ai documenti

Soluzioni:
1. Aumenta RAG__HITL_SCORE_THRESHOLD a 0.75
2. Migliora chunking: documenti devono avere header chiari
3. Aumenta CHROMADB__HNSW_CONSTRUCTION_EF a 300
4. Verifica che documenti siano effettivamente ingestiti:
   python -c "from src.vector_store import get_vector_store; print(get_vector_store().get_stats())"
```

---

## Manutenzione Operativa

### Check Salute Quotidiano (15 minuti)

```powershell
# 1. Avvia sessione PowerShell
.\.venv\Scripts\Activate.ps1

# 2. Verifica LM Studio
python -c "
from src.lm_studio_manager import get_lm_studio
lm = get_lm_studio()
print('✓ LM Studio OK' if lm.check_health() else '✗ LM Studio DOWN')
"

# 3. Verifica Vector Store
python -c "
from src.vector_store import get_vector_store
vs = get_vector_store()
stats = vs.get_stats()
print(f'Vector DB: {stats.get(\"total_documents\", 0)} documenti')
"

# 4. Esegui query test
# python src/main.py
```

### Backup Dati Vettoriali

```powershell
# ChromaDB data è in: data/vector_db/
# Backup settimanale:
Copy-Item -Recurse data/vector_db/ data/vector_db_backup_$(Get-Date -Format "yyyy-MM-dd")

# Retention: Mantieni 4 backup (4 settimane di history)
```

### Aggiornamento Documenti

```powershell
# Quando nuovi documenti IT sono disponibili:

# 1. Copia in data/documents/
# 2. Esegui ingestion:
python -c "
from src.document_ingestion import DocumentIngestionPipeline
p = DocumentIngestionPipeline()
p.ingest_from_directory()
"
# 3. Test una domanda correlata
# 4. Se non soddisfatto, ricrea vector DB:
#    - Elimina data/vector_db/
#    - Ricrea con python src/main.py
```

### Monitoraggio Prestazioni

```powershell
# Monitora RAM durante sessione RAG
Get-Process | Where-Object {$_.Name -match "python|lm_studio"} |
  Select-Object Name, @{l='Memory (MB)';e={[math]::Round($_.WS/1MB,2)}} |
  Format-Table

# Se RAM > 14GB, aumenta IDLE_TTL su LM Studio
```

---

## FAQ

**Q: Devo avere connessione internet sempre?**
A: No. Una volta installati Python, LM Studio, e scaricati i dati, il sistema è completamente offline. Connessione serve solo per aggiornamenti.

**Q: Posso usare un modello diverso da Mistral?**
A: Sì. Qualsiasi modello GGUF compatibile (Llama, Mixtral, ecc.) funziona. Aggiorna `LM_STUDIO__MODEL_NAME` in `.env`.

**Q: Come garantisco GDPR compliance?**
A: Il sistema è progettato per GDPR per design:
- ✅ Dati non lasciano il laptop
- ✅ Nessuna trasmissione cloud
- ✅ Storage persistente cifrato (opzionale: integra BitLocker)
- ✅ Zero dati telemetrici LM Studio

**Q: Quanta memoria occupa?**
A: Tipicamente:
- Python + dipendenze: ~1.5GB
- LM Studio + modello: ~7-8GB
- ChromaDB (100 documenti): ~200MB
- **Totale**: ~10GB, su 16GB disponibili

**Q: Posso usare GPU?**
A: Sì, se disponibile (HP ProBook 440 ha Intel Iris Xe). Disabilita "GPU Offload OFF" e abilita "GPU Use" in LM Studio. Però non è critico per i vostri use case.

---

## Supporto Tecnico

**Documenti di Riferimento**:
- `README.md` - Overview architettura
- `setup/SETUP_WINDOWS.md` - Setup Python
- `setup/firewall_setup.ps1` - Configurazione sicurezza
- `.env.example` - Configurazione dettagliata parametri

**Log File**: `logs/rag.log`

**Contatto**: Christian Robecchi (ETJCA)

---

**Documento versione**: 1.0
**Ultima modifica**: Febbraio 2026
**Status**: ✅ Production Ready
