
@echo off
echo ════════════════════════════════════════════════════════════
echo          RAG LOCALE - STREAMLIT UI LAUNCHER
echo ════════════════════════════════════════════════════════════
echo.
echo Avvio Interfaccia RAG (Streamlit)...
echo Configurazione: Timeout 300s, Retry 5 tentativi
echo.

cd /d "%~dp0"

:: Verifica che Python è disponibile
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ ERRORE: Python non trovato!
    echo Installa Python da https://www.python.org/
    pause
    exit /b 1
)

:: Verifica che streamlit è installato
python -m pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Streamlit non trovato. Installo dipendenze...
    python -m pip install streamlit google-genai -q
    if errorlevel 1 (
        echo ❌ ERRORE: Impossibile installare dipendenze
        pause
        exit /b 1
    )
)

echo ✅ Dipendenze verificate
echo.
echo 🚀 Avvio Streamlit...
echo.
echo 📋 Come usare:
echo    1. Si aprirà automaticamente il browser a http://localhost:8501
echo    2. Se non si apre, vai a http://localhost:8501 manualmente
echo    3. Per fermare il server: premi Ctrl+C
echo.
echo ════════════════════════════════════════════════════════════
echo.

:: Avvia Streamlit con configurazione
python -m streamlit run src/app_ui.py ^
    --logger.level=info ^
    --client.showErrorDetails=true ^
    --client.toolbarMode=viewer

echo.
echo ⏹️  Server Streamlit terminato
pause
