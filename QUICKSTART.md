# RAG LOCALE (Hybrid) - Quick Start Guide

**Tempo di Setup**: 5 minuti
**Stato**: ✅ Hybrid RAG (Cloud LLM + Local Store)

---

## 1. Installazione (2 min)

```bash
# Naviga nella cartella del progetto
cd "C:\Users\ChristianRobecchi\Downloads\RAG LOCALE"

# (Opzionale ma raccomandato) Crea ambiente virtuale
python -m venv venv
venv\Scripts\activate

# Installa dipendenze
pip install -r requirements.txt
```

## 2. Configurazione (1 min)

1.  Fai una copia del file `.env.example` e rinominalo in `.env`:
    ```bash
    copy .env.example .env
    ```
2.  Modifica `.env` e inserisci la tua **Google Gemini API Key**:
    ```ini
    GEMINI_API_KEY=AIzaSy...
    ```

## 3. Aggiungi Documenti (1 min)

Crea una cartella `documents` (se non esiste) e metti lì i tuoi file:
```bash
mkdir documents
# Copia i tuoi PDF/TXT qui dentro
```

## 4. Avvia l'App (1 min)

Usa lo script specifico per la versione con documenti reali:
```bash
streamlit run app_streamlit_real_docs.py
```
L'app si aprirà nel browser a `http://localhost:8501`.

## 5. Primi Passi

1.  Nella sidebar a sinistra, clicca **"Load Documents"**.
2.  Attendi che l'indicizzazione finisca (vedrai una barra di progresso/log).
3.  Scrivi una domanda nella chat centrale, es: *"Di cosa parlano i documenti caricati?"*

---

## Troubleshooting Comune

-   **"API Key not found"**: Controlla di aver rinominato `.env.example` in `.env` e salvato la chiave corretta.
-   **"App non si apre"**: Se la porta 8501 è occupata, prova `streamlit run app_streamlit_real_docs.py --server.port 8502`.
-   **Crash su PDF**: Alcuni PDF complessi potrebbero fallire. Controlla i log avviando l'app da terminale per vedere l'errore specifico.
