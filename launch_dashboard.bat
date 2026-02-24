@echo off
REM RAG LOCALE Dashboard Launcher
REM Windows batch script to easily launch the Streamlit dashboard

echo.
echo ================================================================================
echo     RAG LOCALE Dashboard Launcher
echo ================================================================================
echo.

REM Use Python from AppData
set PYTHON_PATH=%LOCALAPPDATA%\Microsoft\WindowsApps\python.exe

REM Check if Python is installed
"%PYTHON_PATH%" --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed in AppData
    echo Please install Python from Microsoft Store
    pause
    exit /b 1
)

REM Check if Streamlit is installed
"%PYTHON_PATH%" -m pip show streamlit >nul 2>&1
if errorlevel 1 (
    echo WARNING: Streamlit is not installed
    echo Installing Streamlit...
    "%PYTHON_PATH%" -m pip install streamlit
    if errorlevel 1 (
        echo ERROR: Failed to install Streamlit
        pause
        exit /b 1
    )
)

REM Launch dashboard
echo.
echo Starting RAG LOCALE Dashboard...
echo.
echo The dashboard will open in your browser at http://localhost:8503
echo Press Ctrl+C to stop the server
echo.
echo ================================================================================
echo.

"%PYTHON_PATH%" -m streamlit run app_streamlit_real_docs.py --server.port=8503 --server.address=0.0.0.0

pause
