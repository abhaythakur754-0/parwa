@echo off
REM ============================================================
REM  PARWA - Start Both Servers (Windows Native)
REM ============================================================
REM
REM  This opens two separate terminal windows:
REM    Window 1: Backend (FastAPI on port 8000)
REM    Window 2: Frontend (Next.js on port 3000)
REM
REM  Prerequisites (run ONCE):
REM    Backend:  cd backend ^&^& python -m venv venv ^&^& venv\Scripts\pip install -r requirements.txt
REM    Frontend: cd frontend ^&^& npm install --legacy-peer-deps
REM
REM ============================================================

echo.
echo ==========================================
echo   PARWA - Starting Both Servers
echo ==========================================
echo.
echo   Backend:  http://localhost:8000
echo   API Docs: http://localhost:8000/docs
echo   Frontend: http://localhost:3000
echo.
echo   Two terminal windows will open.
echo   Close each window to stop that server.
echo ==========================================
echo.

REM Start backend in a new window
start "PARWA Backend" cmd /k "%~dp0start-backend.bat"

REM Wait a moment for backend to start
timeout /t 3 /nobreak >nul

REM Start frontend in a new window
start "PARWA Frontend" cmd /k "%~dp0start-frontend.bat"

echo.
echo Both servers are starting!
echo Close their windows to stop them.
echo.
timeout /t 5 /nobreak >nul
