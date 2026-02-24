
@echo off
echo Avvio del Backend RAG LOCALE...
cd /d "%~dp0"
call .venv\Scripts\activate.bat
python src/api.py
pause
