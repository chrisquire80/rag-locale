# 📑 Indice Completo - RAG Locale

Navigazione della documentazione del progetto RAG Locale per HP ProBook 440 G11

---

## 🚀 Iniziare da Qui

### Per implementazione rapida
**[QUICK_START.md](QUICK_START.md)** ⏱️ 1-2 ore
- 5 passaggi per avviare il sistema
- Test domande pronte
- Troubleshooting rapido

### Per setup manuale dettagliato
**[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** 📋 Lettura completa
- Installazione passo per passo
- Configurazione LM Studio (memory management)
- Ingestion documenti IT
- Manutenzione operativa
- FAQ completo

---

## 📚 Documentazione Tecnica

### Capire l'architettura
**[ARCHITECTURE.md](ARCHITECTURE.md)** 🏗️ Riferimento tecnico
- Overview architetturale (diagram)
- Componenti dettagliati
- Data flow (ingestion + query)
- Memory management strategy
- Security architecture
- Technology rationale
- Scalability & limitations

### Panoramica progetto
**[README.md](README.md)** 📖 Overview
- Introduzione al progetto
- Componenti principali
- Struttura directory
- Quick start reference
- Parametri critici HP ProBook 440

---

## 🛠️ Setup e Configurazione

### Istruzioni Python
**[setup/SETUP_WINDOWS.md](setup/SETUP_WINDOWS.md)** 🐍 Python installation
- Installazione Python 3.11+
- Virtual environment setup
- Installazione dipendenze
- Configurazione LM Studio
- Firewall rules
- Testing connettività
- Troubleshooting setup

### Script Firewall
**[setup/firewall_setup.ps1](setup/firewall_setup.ps1)** 🔒 Security hardening
- Configurazione Windows Firewall
- Isolamento porta LM Studio (1234)
- Isolamento porta RAG App (8080)
- Esecuzione: `powershell -ExecutionPolicy Bypass -File setup/firewall_setup.ps1`

### Dipendenze Python
**[setup/requirements.txt](setup/requirements.txt)** 📦 Package list
- LlamaIndex + ChromaDB
- OpenAI client (per LM Studio)
- Document processing (pdfplumber, python-docx)
- Utilities (logging, monitoring)

### Template Configurazione
**[.env.example](.env.example)** ⚙️ Configuration template
- Copia in `.env` per override
- Parametri LM Studio (idle TTL, temperature, etc.)
- Parametri ChromaDB (HNSW config)
- Parametri RAG (HITL threshold, top-k)
- Commenti dettagliati per ogni parametro

---

## 💻 Codice Sorgente

### Configurazione centralizzata
**[src/config.py](src/config.py)** 🎛️
- Pydantic BaseSettings
- LMStudioConfig, ChromaDBConfig, RAGConfig
- Path management (PROJECT_ROOT, DATA_DIR, etc.)
- print_config() per debug

### Interfaccia LM Studio
**[src/lm_studio_manager.py](src/lm_studio_manager.py)** 🤖
- Connessione server LM Studio
- Health check + model discovery
- completion() method per inference
- Token counting (euristica)
- Session + retry strategy

### Vector Database
**[src/vector_store.py](src/vector_store.py)** 📦
- ChromaDB wrapper
- HNSW configuration
- add_documents() per ingestion
- search() per retrieval semantico
- Metadata filtering
- Statistiche database

### Pipeline Ingestion
**[src/document_ingestion.py](src/document_ingestion.py)** 📄
- DocumentProcessor (multi-format)
- PDF extraction (pdfplumber)
- DOCX processing
- Markdown parsing (header-aware)
- RegEx-based chunking (sentence-aware)
- DocumentIngestionPipeline (orchestration)

### RAG Engine + HITL
**[src/rag_engine.py](src/rag_engine.py)** 🔍
- RAGEngine orchestration
- Retrieval phase (vector search)
- HITL validation (human approval)
- Generation phase (LLM inference)
- Output formatting + citations
- interactive_rag_session() REPL

### Entry Point
**[src/main.py](src/main.py)** 🚀
- Orchestrazione completa
- Health check LM Studio
- Document ingestion automatica
- Session interattiva
- Creazione documenti di test
- Banner e print_config()

---

## 📊 Directory Structure

```
RAG LOCALE/
│
├─ README.md                    # Overview
├─ QUICK_START.md              # Quick start guide
├─ DEPLOYMENT_GUIDE.md         # Complete setup guide
├─ ARCHITECTURE.md             # Technical architecture
├─ INDEX.md                    # This file
├─ .env.example                # Configuration template
│
├─ setup/
│  ├─ SETUP_WINDOWS.md         # Python setup detailed
│  ├─ firewall_setup.ps1       # Firewall hardening
│  └─ requirements.txt         # Python dependencies
│
├─ src/
│  ├─ __init__.py
│  ├─ config.py                # Configuration management
│  ├─ lm_studio_manager.py    # LLM interface
│  ├─ vector_store.py          # Vector database
│  ├─ document_ingestion.py   # Document processing
│  ├─ rag_engine.py            # RAG + HITL core
│  └─ main.py                  # Entry point
│
├─ data/
│  ├─ documents/               # Your IT documents
│  │  ├─ policy_smartworking.txt
│  │  ├─ security_procedures.txt
│  │  └─ (your files here)
│  │
│  └─ vector_db/               # ChromaDB storage (auto-created)
│     ├─ chroma.db
│     ├─ index/
│     └─ embeddings.parquet
│
└─ logs/
   └─ rag.log                  # Application logs
```

---

## 🔄 Workflow Tipico

### Day 1: Setup Iniziale
1. Leggi [QUICK_START.md](QUICK_START.md)
2. Segui 5 passi di installazione
3. Testa con domande di esempio

### Day 2-3: Customizzazione
1. Aggiungi tuoi documenti IT in `data/documents/`
2. Modifica parametri in `.env` se necessario
3. Esegui `python src/main.py` per ingestion
4. Testa queries sulla tua documentazione

### Ongoing: Manutenzione
1. Consulta [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) sezione "Manutenzione Operativa"
2. Monitora `logs/rag.log` per errori
3. Aggiungi nuovi documenti quando disponibili
4. Backup settimanale di `data/vector_db/`

---

## 🎯 Documenti per Ruolo

### Per Sviluppatore / AI Engineer
- **Primo**: [ARCHITECTURE.md](ARCHITECTURE.md) - Comprensione tecnica
- **Secondo**: [src/](src/) - Lettura codice
- **Terzo**: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Setup dettagliato
- **Riferimento**: [.env.example](.env.example) - Parametri tuning

### Per IT Administrator / DevOps
- **Primo**: [QUICK_START.md](QUICK_START.md) - Setup rapido
- **Secondo**: [setup/firewall_setup.ps1](setup/firewall_setup.ps1) - Security config
- **Terzo**: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - Manutenzione
- **Riferimento**: [setup/SETUP_WINDOWS.md](setup/SETUP_WINDOWS.md) - Troubleshooting

### Per End User / Business Analyst
- **Primo**: [QUICK_START.md](QUICK_START.md) - Come usare
- **Secondo**: [README.md](README.md) - Cos'è il progetto
- **Terzo**: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - FAQ
- **Supporto**: `logs/rag.log` - Se ci sono problemi

---

## 🔍 Ricerca Rapida per Argomento

### Installazione
- Python: [setup/SETUP_WINDOWS.md](setup/SETUP_WINDOWS.md)
- LM Studio: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#configurazione-lm-studio)
- Dipendenze: [setup/requirements.txt](setup/requirements.txt)

### Configurazione
- Parametri critici: [ARCHITECTURE.md](ARCHITECTURE.md#memory-management-strategy)
- Environment variables: [.env.example](.env.example)
- LM Studio settings: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#parametri-critici-hp-probook-440)

### Sicurezza
- Firewall: [setup/firewall_setup.ps1](setup/firewall_setup.ps1)
- Network isolation: [ARCHITECTURE.md](ARCHITECTURE.md#network-isolation)
- GDPR compliance: [ARCHITECTURE.md](ARCHITECTURE.md#compliance)

### Documenti IT
- Ingestion: [src/document_ingestion.py](src/document_ingestion.py)
- Formato: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#preparazione-documenti-best-practice)
- Chunking: [ARCHITECTURE.md](ARCHITECTURE.md#document-ingestion-pipeline)

### Query & Retrieval
- RAG flow: [ARCHITECTURE.md](ARCHITECTURE.md#query-flow)
- HITL validation: [src/rag_engine.py](src/rag_engine.py)
- Similarity search: [src/vector_store.py](src/vector_store.py)

### Troubleshooting
- Quick fixes: [QUICK_START.md](QUICK_START.md#troubleshooting-rapido)
- Detailed: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md#troubleshooting)
- Debug logs: `logs/rag.log`

---

## 🌐 Dipendenze Esterne

**During Development/Setup**:
- Python 3.11+ download
- LM Studio installer
- Mistral 7B model (~5GB) - scaricato 1 volta
- PyPI packages (`pip install`)

**During Operation**:
- ✅ ZERO - Completamente offline-capable
- 🔒 Nessuna cloud API
- 🔐 Nessuna trasmissione dati esterna

---

## 📝 Versionamento

- **Documento version**: 1.0
- **Ultima modifica**: Febbraio 2026
- **Stato**: ✅ Production Ready
- **Mantainer**: Christian Robecchi (ETJCA)
- **Hardware**: HP ProBook 440 G11

---

## 💡 Tips & Tricks

```powershell
# Attiva venv rapidamente
alias activate=".\.venv\Scripts\Activate.ps1"
activate

# Avvia RAG con log in real-time
python src/main.py | tee logs/rag.log

# Monitor memoria durante sessione
while(1) { Get-Process python | Select Name, @{l='MB';e={[int]($_.WS/1MB)}}; sleep 5 }

# Test connessione LM Studio
$response = curl -s http://localhost:1234/v1/models | ConvertFrom-Json
$response.data | Select-Object id

# Backup vector database
Copy-Item -Recurse data/vector_db/ data/vector_db_backup_$(Get-Date -Format "yyyyMMdd")
```

---

**Happy RAG! 🚀**
