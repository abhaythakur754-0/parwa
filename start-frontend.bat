@echo off
REM ============================================================
REM  PARWA Frontend - Windows Native Startup (No Docker, No WSL)
REM ============================================================
REM
REM  Prerequisites:
REM    1. Node.js 20+ installed (node --version)
REM    2. Run once: npm install --legacy-peer-deps
REM
REM  Usage:
REM    Double-click this file, or run from cmd:
REM    start-frontend.bat
REM
REM ============================================================

echo.
echo ==========================================
echo   PARWA Frontend - Windows Native
echo ==========================================
echo.

REM Change to project root (where package.json is)
cd /d "%~dp0"

REM Check node_modules exists
if not exist "node_modules" (
    echo.
    echo [ERROR] node_modules not found!
    echo.
    echo Run this first to set up:
    echo   npm install --legacy-peer-deps
    echo.
    pause
    exit /b 1
)

echo   URL:       http://localhost:3000
echo   Backend:   http://localhost:8000
echo   API Docs:  http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server.
echo ==========================================
echo.

REM Start Next.js dev server with webpack (Turbopack disabled for Windows)
npx next dev --webpack -p 3000

pause
