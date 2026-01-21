@echo off
echo ==========================================
echo      Email Sender - Windows Start
echo ==========================================

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python is not installed or not in PATH.
    pause
    exit /b
)

REM Install Backend Dependencies
echo [1/2] Checking backend dependencies...
pip install -r backend/requirements.txt

REM Start Backend in background
echo [2/2] Starting services...
start "Backend API" /min cmd /c "cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"

REM Start Frontend
cd frontend
if not exist node_modules (
    echo Installing frontend dependencies...
    call npm install
)
echo Starting frontend...
start "Frontend UI" /min cmd /c "npm run dev -- --host"

echo.
echo App is running!
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo Close the popup windows to stop the servers.
pause
