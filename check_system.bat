@echo off
echo ════════════════════════════════════════════════════════════
echo          RAG LOCALE - SYSTEM HEALTH CHECK
echo ════════════════════════════════════════════════════════════
echo.

cd /d "%~dp0"

echo [1/5] Verificando Python...
python --version
if errorlevel 1 (
    echo ❌ ERRORE: Python non trovato!
    goto error
)
echo ✅ Python OK
echo.

echo [2/5] Verificando dipendenze...
python -m pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Streamlit non installato
    echo Installazione in corso...
    python -m pip install -q streamlit google-genai numpy pandas chromadb
) else (
    echo ✅ Dipendenze OK
)
echo.

echo [3/5] Verificando vector store...
if exist "data\vector_db\vector_store.pkl" (
    echo ✅ Vector store trovato
) else (
    echo ⚠️  ATTENZIONE: Vector store non trovato
    echo    I documenti verranno ingestionati al primo avvio
)
echo.

echo [4/5] Verificando file di configurazione...
if exist ".env" (
    echo ✅ .env file trovato (contiene configurazione)
) else (
    echo ⚠️  ATTENZIONE: .env non trovato
    echo    Verifica che GEMINI_API_KEY sia configurato
)
echo.

echo [5/5] Eseguendo health check Python...
python -c "
import sys
sys.path.insert(0, 'src')
try:
    from config import config
    print('✅ Configurazione caricata')
except Exception as e:
    print(f'❌ ERRORE: {e}')
    sys.exit(1)
"
if errorlevel 1 goto error

echo.
echo ════════════════════════════════════════════════════════════
echo ✅ SYSTEM CHECK PASSED - Sistema pronto per Streamlit!
echo ════════════════════════════════════════════════════════════
echo.
echo Comando per avviare:
echo   start_ui.bat
echo.
pause
exit /b 0

:error
echo.
echo ════════════════════════════════════════════════════════════
echo ❌ ERRORI RILEVATI - Contatta il supporto
echo ════════════════════════════════════════════════════════════
pause
exit /b 1
