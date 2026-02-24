# Setup Windows - HP ProBook 440 G11

## Fase 1: Installazione Python 3.11

### Opzione A: Installer Ufficiale (Consigliato)

1. **Scaricare** Python 3.11 da https://www.python.org/downloads/
2. **Eseguire installer** con privilegi amministratore
3. **Aggiungere al PATH** (✓ checkbox durante installazione)
4. **Verificare**:
   ```powershell
   python --version
   pip --version
   ```

### Opzione B: Microsoft Store (Alternativa)

```powershell
# Apri Microsoft Store e cerca "Python 3.11"
# O via PowerShell (richiede account Microsoft):
# Unavailable in alcuni ambienti aziendali
```

## Fase 2: Creazione Virtual Environment

```powershell
# Naviga alla cartella progetto
cd C:\Users\ChristianRobecchi\Downloads\RAG\ LOCALE

# Crea venv isolato
python -m venv .venv

# Attiva venv (importante: aggiorna pip/setuptools)
.\.venv\Scripts\Activate.ps1

# Se ricevi errore "cannot be loaded because the execution of scripts
# is disabled on this system", esegui:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Aggiorna pip
python -m pip install --upgrade pip setuptools wheel
```

## Fase 3: Installazione Dipendenze

```powershell
# Assicurati che il venv sia attivato
pip install -r setup/requirements.txt

# Verifica installazione:
pip list
```

**Dipendenze Principali**:
- `llamaindex` - Framework RAG
- `chromadb` - Vector database
- `openai` - Client OpenAI API (per LM Studio)
- `pydantic` - Validazione config
- `python-dotenv` - Gestione secrets

## Fase 4: Installazione LM Studio

1. **Scaricare** da https://lmstudio.ai
2. **Installare** (user-level, non richiede admin)
3. **Avviare** LM Studio
4. **Scaricare modello**:
   - Accedi a "Discover" tab
   - Seleziona "Mistral 7B Instruct v0.3 Q4_K_M" (~5GB)
   - Attendi completamento download
5. **Avviare Server Locale**:
   - Accedi a "Local Server" tab
   - Seleziona il modello da dropdown
   - Premi "Start Server"
   - Verifica: `curl http://localhost:1234/v1/models` (deve rispondere)

## Fase 5: Configurazione Firewall (Sicurezza)

```powershell
# Esegui PowerShell con privilegi amministratore

# Blocca accesso esterno a porta 1234 (LM Studio)
netsh advfirewall firewall add rule name="RAG-LMStudio-Loopback" `
  dir=in action=block protocol=tcp localport=1234 remoteip=!127.0.0.1

# Blocca accesso esterno a porta 8080 (app RAG - se utilizzata)
netsh advfirewall firewall add rule name="RAG-App-Loopback" `
  dir=in action=block protocol=tcp localport=8080 remoteip=!127.0.0.1

# Verifica regole:
netsh advfirewall firewall show rule name="RAG*"
```

## Fase 6: Test Connettività

```powershell
# Attiva venv
.\.venv\Scripts\Activate.ps1

# Test LM Studio server
python -c "
import requests
try:
    resp = requests.get('http://localhost:1234/v1/models')
    print('✓ LM Studio disponibile')
    print(f'  Modelli: {resp.json()}')
except Exception as e:
    print(f'✗ Errore: {e}')
    print('  Assicurati che LM Studio sia avviato su Local Server')
"
```

## Troubleshooting

| Problema | Soluzione |
|----------|-----------|
| `python: command not found` | Reinstalla Python, assicurati che sia in PATH. Riavvia terminal. |
| `Module not found (chromadb, llamaindex)` | Verifica che venv sia attivato: `.\.venv\Scripts\Activate.ps1` |
| `LM Studio connection refused` | LM Studio non è avviato. Apri l'app e avvia "Local Server" |
| `ImportError: DLL load failed` | Potrebbe essere problema di dipendenze C++. Installa "Microsoft C++ Redistributable" |
| `Permission denied on firewall rules` | Esegui PowerShell come amministratore |

## Verifica Completa Setup

```powershell
# Script di verifica (salva come verify_setup.ps1)
.\.venv\Scripts\Activate.ps1

echo "=== Verifica Python ==="
python --version

echo "`n=== Verifica Dipendenze ==="
pip list | Select-String "llamaindex|chromadb|openai"

echo "`n=== Verifica LM Studio ==="
curl -s http://localhost:1234/v1/models | ConvertFrom-Json | Select-Object -Property object, data

echo "`n=== Verifica Storage ==="
if (Test-Path "data/vector_db") { echo "✓ Vector DB path ready" } else { mkdir data/vector_db }

echo "`n✓ Setup completato!"
```

---

**Next Step**: Leggi `src/config.py` per configurare i parametri dell'applicazione.
