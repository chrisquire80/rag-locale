# Quick Start - RAG Locale

⏱️ **Tempo stimato**: 1-2 ore (dipende da download Mistral 7B)

---

## In 5 Passi

### 1️⃣ Installare Python (15 min)

```powershell
# Scarica Python 3.11+
# https://www.python.org/downloads/

# Esegui installer
# ✓ Checkbox "Add Python to PATH"
# ✓ Checkbox "Install pip"

# Verifica
python --version
pip --version
```

### 2️⃣ Setup Virtual Environment (5 min)

```powershell
cd C:\Users\ChristianRobecchi\Downloads\RAG\ LOCALE

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install --upgrade pip setuptools wheel
pip install -r setup/requirements.txt
```

### 3️⃣ Installare LM Studio (5 min setup + 30-60 min download)

```
1. Scarica: https://lmstudio.ai
2. Esegui installer
3. Apri LM Studio
4. Tab "Discover" → Cerca "Mistral 7B Q4_K_M" → Download
5. Tab "Local Server" → Seleziona modello → Start Server
```

**Verifica connessione**:
```powershell
curl http://localhost:1234/v1/models
# Deve tornare JSON con lista modelli
```

### 4️⃣ Configurare Firewall (5 min)

```powershell
# Esegui PowerShell come Amministratore
cd C:\Users\ChristianRobecchi\Downloads\RAG\ LOCALE
.\setup\firewall_setup.ps1
```

### 5️⃣ Avviare RAG (2 min)

```powershell
# Con venv attivato
python src/main.py

# Output:
# ╔════════════════════════════════════════════════════════════╗
# ║           🚀 RAG LOCALE - Sistema Aziendale              ║
# ╚════════════════════════════════════════════════════════════╝
#
# 💬 Domanda: _
```

---

## Test Domande

Prova con questi esempi:

```
1. "Quali sono i requisiti tecnici per smart working?"
2. "Quali sono le frequenze di backup obbligatorie?"
3. "Come si configura la multi-factor authentication?"
4. "Cosa dice la policy su password?"
```

---

## Troubleshooting Rapido

| Problema | Soluzione |
|----------|-----------|
| `python: command not found` | Riavvia PowerShell dopo Python install |
| `Connection refused (LM Studio)` | Assicurati che "Local Server" sia avviato in LM Studio |
| `ModuleNotFoundError` | Verifica venv sia attivato: `.\.venv\Scripts\Activate.ps1` |
| `Laptop becomes slow` | Aumenta `Idle TTL` in LM Studio a 60s |

---

## Next Steps

1. 📚 Leggi `DEPLOYMENT_GUIDE.md` per setup completo
2. 🏗️ Leggi `ARCHITECTURE.md` per capire come funziona
3. 📄 Aggiungi i tuoi documenti IT in `data/documents/`
4. 🔍 Prova queries sulla tua documentazione
5. 🔐 Se in ufficio: configura VPN prima di lanciare

---

## File Importanti

```
README.md                  ← Overview progetto
DEPLOYMENT_GUIDE.md        ← Setup dettagliato
ARCHITECTURE.md            ← Come funziona tecnicamente
QUICK_START.md             ← Questo file
setup/SETUP_WINDOWS.md     ← Istruzioni Python step-by-step
setup/firewall_setup.ps1   ← Script firewall
setup/requirements.txt     ← Dipendenze Python

src/
├─ main.py                 ← Entry point
├─ config.py               ← Configurazione
├─ lm_studio_manager.py    ← Interfaccia LLM
├─ vector_store.py         ← Database vettoriale
├─ document_ingestion.py   ← Caricamento documenti
└─ rag_engine.py           ← Core RAG + HITL

data/
├─ documents/              ← Tuoi documenti IT
└─ vector_db/              ← Vector database (autogenerato)

logs/
└─ rag.log                 ← Log applicazione
```

---

## Support

📧 **Domande tecniche?** Leggi `DEPLOYMENT_GUIDE.md` sezione FAQ

🐛 **Bug?** Controlla `logs/rag.log` per errori

📌 **Configurazione avanzata?** Modifica `.env` (copia da `.env.example`)

---

**Versione**: 1.0 | **Status**: ✅ Ready to Deploy
