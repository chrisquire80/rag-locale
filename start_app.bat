@echo off
REM Start RAG LOCALE Streamlit App
REM This script launches the Streamlit server

cd /d "C:\Users\ChristianRobecchi\Downloads\RAG LOCALE"

echo.
echo ================================================================================
echo  RAG LOCALE - STREAMLIT APP LAUNCHER
echo ================================================================================
echo.
echo Launching Streamlit server...
echo.
echo The app will open at: http://localhost:8501
echo.
echo Press Ctrl+C to stop the server
echo.
echo ================================================================================
echo.

python -m streamlit run app_streamlit_real_docs.py --server.port 8503

pause
