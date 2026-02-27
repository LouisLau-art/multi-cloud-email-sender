@echo off
setlocal
echo ==========================================
echo      Email Sender - Safe Builder (Windows)
echo ==========================================

REM 1. Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found! Please install Python 3.10+ and add to PATH.
    pause
    exit /b
)

REM 2. Create Virtual Environment (The safest way to isolate dependencies)
if not exist venv (
    echo [1/5] Creating virtual environment...
    python -m venv venv
)

REM 3. Activate venv & Install
echo [2/5] Installing dependencies...
call venv\Scripts\activate
pip install --upgrade pip
pip install -r backend/requirements.txt
pip install pyinstaller

REM 4. Build Frontend
echo [3/5] Building Frontend...
cd frontend
call npm install
call npm run build
cd ..

REM 5. Package (Folder Mode + Console Visible)
echo [4/5] Packaging...
REM --onedir: Creates a folder (More stable than single file)
REM --console: Keeps the window open (Crucial for debugging)
REM --clean: Clears cache
pyinstaller --noconfirm --name="EmailSender" --onedir --console --clean --add-data="frontend/dist;frontend_dist" backend/run.py

echo.
echo [5/5] Done!
echo The app is in: dist\EmailSender\EmailSender.exe
echo.
echo Please run the .exe file inside that folder.
echo A black window will appear - THIS IS NORMAL. Do not close it.
pause