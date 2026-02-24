@echo off
REM RAG LOCALE - Quick Start with Document Folder Helper
REM This script helps you find your documents folder and launch the app

echo.
echo ================================================================================
echo   RAG LOCALE - Quick Start
echo ================================================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/
    pause
    exit /b 1
)

echo.
echo Select an option:
echo.
echo   1. Help me find my documents folder
echo   2. Launch RAG LOCALE app directly
echo   3. View documentation
echo   4. Exit
echo.

set /p choice="Enter your choice (1-4): "

if "%choice%"=="1" (
    echo.
    echo Starting document folder finder...
    python find_documents_folder.py
    pause
    goto start
) else if "%choice%"=="2" (
    echo.
    echo Launching RAG LOCALE...
    python launch_app.py
    pause
    goto end
) else if "%choice%"=="3" (
    echo.
    echo Opening documentation...
    if exist LOAD_REAL_DOCUMENTS.md (
        start notepad LOAD_REAL_DOCUMENTS.md
    ) else (
        echo [ERROR] Documentation file not found
        pause
    )
    goto start
) else if "%choice%"=="4" (
    goto end
) else (
    echo [ERROR] Invalid choice
    pause
    goto start
)

:start
cls
goto quick_start

:end
echo.
echo [GOODBYE] Thank you for using RAG LOCALE!
echo.
pause
