@echo off
setlocal
echo ==========================================
echo      Email Sender - Safe Start (Windows)
echo ==========================================

REM 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found! Please install Python 3.10+
    pause
    exit /b
)

REM 2. Check Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found! Please install Node.js 18+
    pause
    exit /b
)

REM 3. Create Virtual Env
if not exist venv (
    echo [Setup] Creating virtual environment...
    python -m venv venv
)

REM 4. Install Dependencies
echo [Setup] Installing Backend Libraries...
call venv\Scripts\activate
pip install -r backend/requirements.txt

REM 5. Install Frontend
cd frontend
if not exist node_modules (
    echo [Setup] Installing Frontend Libraries...
    call npm install
)

REM 6. Start Everything
echo.
echo ====================================================
echo Starting System...
echo 1. Backend API is starting...
echo 2. Frontend UI is building...
echo.
echo DONT CLOSE THIS WINDOW.
echo ====================================================

REM Start Backend in a new window
start "Backend Server" cmd /k "..\venv\Scripts\activate && cd ..\backend && python run.py"

REM Start Frontend
echo Starting Frontend...
call npm run dev -- --host

pause