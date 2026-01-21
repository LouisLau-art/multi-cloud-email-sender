@echo off
echo ==========================================
echo      Email Sender - Windows Builder
echo ==========================================

REM 1. Install Backend Dependencies
echo [1/4] Installing Python dependencies...
pip install -r backend/requirements.txt
pip install pyinstaller

REM 2. Build Frontend (Requires Node.js)
echo [2/4] Building Frontend...
cd frontend
call npm install
call npm run build
cd ..

REM 3. Package with PyInstaller
echo [3/4] Packaging to EXE...
REM --onedir: Generate a folder (easier for debugging)
REM --noconsole: Hide the black command window (remove this if you want to see logs)
REM --add-data: Include the frontend dist folder
pyinstaller --name="EmailSender" --onedir --noconsole --add-data="frontend/dist;frontend_dist" backend/run.py

echo [4/4] Done!
echo.
echo The executable is located in: dist\EmailSender\EmailSender.exe
pause
