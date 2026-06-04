@echo off
REM ============================================================
REM  PARWA - First-Time Windows Setup (No Docker, No WSL)
REM ============================================================
REM
REM  Run this ONCE to install all dependencies.
REM  After that, just use start-all.bat to run the app.
REM
REM ============================================================

echo.
echo ==========================================
echo   PARWA - First-Time Windows Setup
echo ==========================================
echo.

REM Check Python
echo [1/5] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Python not found! Install Python 3.11+ from:
    echo   https://www.python.org/downloads/
    echo.
    echo Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)
python --version

REM Check Node.js
echo.
echo [2/5] Checking Node.js...
node --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo [ERROR] Node.js not found! Install Node.js 20+ from:
    echo   https://nodejs.org/
    echo.
    pause
    exit /b 1
)
node --version

REM Setup Backend
echo.
echo [3/5] Setting up Python virtual environment...
cd /d "%~dp0backend"
if not exist "venv" (
    python -m venv venv
    echo   Created venv
) else (
    echo   venv already exists
)

echo.
echo [4/5] Installing Python dependencies (this may take a few minutes)...
call venv\Scripts\activate.bat
pip install -r requirements.txt --quiet
echo   Done

REM Create db folder for SQLite
if not exist "db" mkdir db
echo   Created db folder for SQLite

REM Setup Frontend
echo.
echo [5/5] Installing Node.js dependencies (this may take a few minutes)...
cd /d "%~dp0"
if not exist "node_modules" (
    npm install --legacy-peer-deps
) else (
    echo   node_modules already exists, skipping
)

echo.
echo ==========================================
echo   Setup Complete!
echo ==========================================
echo.
echo   To start PARWA:
echo     Double-click: start-all.bat
echo.
echo   Or start individually:
echo     start-backend.bat   (Backend on :8000)
echo     start-frontend.bat  (Frontend on :3000)
echo.
echo   IMPORTANT: Your API keys are in backend/.env:
echo     - GOOGLE_AI_API_KEY  (set)
echo     - CEREBRAS_API_KEY   (set)
echo     - GROQ_API_KEY       (set)
echo     - LLM_PROVIDER=litellm
echo.
echo   No Docker or WSL needed!
echo ==========================================
pause
