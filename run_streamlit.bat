@echo off
REM Avvia Streamlit UI con configurazioni ottimali per timeout

echo.
echo ========================================================================
echo RAG LOCALE - AVVIO STREAMLIT CON TIMEOUT HANDLING MIGLIORATO
echo ========================================================================
echo.
echo Configurazione:
echo - Timeout: 300 secondi (5 minuti)
echo - Max retries: 5 tentativi con exponential backoff
echo - Retry sequence: 1s, 2s, 4s, 8s, 16s
echo.
echo Avvio della UI Streamlit...
echo.

REM Set Python encoding for proper Unicode handling
set PYTHONIOENCODING=utf-8

REM Run Streamlit with the app_ui.py
streamlit run src/app_ui.py --logger.level=info
