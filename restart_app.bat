@echo off
REM ============================================================================
REM RAG LOCALE - Application Restart Script
REM Enhanced with error handling, logging, and system checks
REM ============================================================================

setlocal enabledelayedexpansion
color 0A

REM Ensure we are in the script's directory (handles Admin mode)
cd /d "%~dp0"

REM Configuration
set PORT=8503
set APP_FILE=app_streamlit_real_docs.py
set PYTHON_PATH=python
set MAX_RETRIES=3

REM Timestamp for logging
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c-%%a-%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a:%%b)

cls
echo.
echo ================================================================================
echo     RAG LOCALE - Application Restart Script
echo     Date: %mydate% %mytime%
echo ================================================================================
echo.

REM ============================================================================
REM STEP 1: Verify Python is installed
REM ============================================================================
echo [1/4] Verifying Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python is available
echo.

REM ============================================================================
REM STEP 2: Kill existing process on port
REM ============================================================================
echo [2/4] Checking for existing process on port %PORT%...

REM Try using netstat first (Windows built-in)
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| find ":%PORT%" ^| find "LISTENING"') do (
    set PID=%%a
)

if defined PID (
    echo [FOUND] Process ID %PID% on port %PORT%
    echo [INFO] Attempting to kill process...

    taskkill /f /pid %PID% >nul 2>&1
    if errorlevel 1 (
        color 0C
        echo ERROR: Failed to kill process %PID%
        echo Please close the application manually and try again
        pause
        exit /b 1
    )
    echo [OK] Process killed successfully
    timeout /t 2 /nobreak >nul
) else (
    echo [INFO] No existing process found on port %PORT%
)
echo.

REM ============================================================================
REM STEP 3: Verify application file exists
REM ============================================================================
echo [3/4] Verifying application files...
if not exist "%APP_FILE%" (
    color 0C
    echo ERROR: File not found: %APP_FILE%
    echo Current directory: %cd%
    pause
    exit /b 1
)
echo [OK] Application file found: %APP_FILE%
echo.

REM ============================================================================
REM STEP 4: Start application
REM ============================================================================
echo [4/4] Starting RAG LOCALE application on port %PORT%...
echo.
echo ================================================================================
echo     Access the application at: http://localhost:%PORT%
echo     Press Ctrl+C to stop the server
echo ================================================================================
echo.

color 0B
python -m streamlit run "%APP_FILE%" --server.port %PORT% --logger.level=info

REM If we reach here, app crashed or was closed
color 0C
echo.
echo ================================================================================
echo WARNING: Application has stopped
echo ================================================================================
echo.
pause
exit /b 0
