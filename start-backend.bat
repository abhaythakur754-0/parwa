@echo off
REM ============================================================
REM  PARWA Backend - Windows Native Startup (No Docker, No WSL)
REM ============================================================
REM
REM  Prerequisites:
REM    1. Python 3.11+ installed (python --version)
REM    2. Run once: cd backend ^&^& python -m venv venv
REM       then:     venv\Scripts\pip install -r requirements.txt
REM
REM  Usage:
REM    Double-click this file, or run from cmd:
REM    start-backend.bat
REM
REM ============================================================

echo.
echo ==========================================
echo   PARWA Backend - Windows Native
echo ==========================================
echo.

REM Change to backend directory
cd /d "%~dp0backend"

REM Create db folder if it doesn't exist
if not exist "db" mkdir db

REM Activate virtual environment
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo.
    echo [ERROR] Virtual environment not found!
    echo.
    echo Run this first to set up:
    echo   cd backend
    echo   python -m venv venv
    echo   venv\Scripts\pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

REM Set Python path
set PYTHONPATH=%~dp0backend;%~dp0

echo   DATABASE:  SQLite (./db/parwa_dev.db)
echo   REDIS:     No-op mode (not needed locally)
echo   LLM:       LiteLLM with direct API keys
echo   URL:       http://localhost:8000
echo.
echo   API Docs:  http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server.
echo ==========================================
echo.

REM Start uvicorn
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log

pause
