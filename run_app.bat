@echo off
echo.
echo ====================================================================
echo          RAG LOCALE Assistant - Streamlit Application
echo ====================================================================
echo.
echo Starting application...
echo Open your browser at: http://localhost:8501
echo.
echo Press Ctrl+C to stop the server
echo.

python -m streamlit run app_streamlit.py --logger.level=warning

pause
