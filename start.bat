@echo off
REM ═══════════════════════════════════════════════════════════════
REM PARWA — Windows Start Script for Local Testing
REM ═══════════════════════════════════════════════════════════════
REM Usage:
REM   start.bat            — Start backend + frontend
REM   start.bat backend    — Start backend only
REM   start.bat frontend   — Start frontend only
REM ═══════════════════════════════════════════════════════════════

setlocal enabledelayedexpansion

echo.
echo ================================================
echo   PARWA - Starting for Local Testing (Windows)
echo ================================================
echo.

REM ── Check Python ──
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Install Python 3.10+ and add to PATH.
    pause
    exit /b 1
)

REM ── Check Node.js ──
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Install Node.js 18+ and add to PATH.
    pause
    exit /b 1
)

if "%~1"=="" goto :both
if "%~1"=="backend" goto :backend
if "%~1"=="frontend" goto :frontend
echo Usage: start.bat [backend^|frontend]
goto :eof

:both
call :backend
call :frontend
goto :eof

:backend
echo [1/2] Starting Backend (FastAPI on http://localhost:8000) ...
echo       API Docs: http://localhost:8000/docs
echo.
start "PARWA Backend" cmd /k "python start_backend.py"
echo       Backend started in a new window.
echo.
goto :eof

:frontend
echo [2/2] Starting Frontend (Next.js on http://localhost:3000) ...
echo       Using --webpack flag (Turbopack crashes on Windows)
echo.

REM Check if node_modules exist
if not exist "node_modules" (
    echo       Installing npm dependencies (first time)...
    call npm install --legacy-peer-deps
    if %errorlevel% neq 0 (
        echo [ERROR] npm install failed.
        pause
        exit /b 1
    )
)

REM Check if Prisma client is generated
if not exist "node_modules\.prisma" (
    echo       Generating Prisma client...
    call npx prisma generate
)

start "PARWA Frontend" cmd /k "npx next dev -p 3000 --webpack"
echo       Frontend started in a new window.
echo.
goto :eof
