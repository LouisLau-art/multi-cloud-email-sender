#!/bin/bash
set -e

echo "=========================================="
echo "      Email Sender - Linux Builder"
echo "=========================================="

# 1. Install Backend Dependencies
echo "[1/4] Installing Python dependencies..."
pip install -r backend/requirements.txt
pip install pyinstaller

# 2. Build Frontend
echo "[2/4] Building Frontend..."
cd frontend
npm install
npm run build
cd ..

# 3. Package with PyInstaller
echo "[3/4] Packaging to Binary..."
# --onefile: Generate a single binary file
# --name: Output filename
# --add-data: Include frontend dist (Format: src:dest)
pyinstaller --name="EmailSender_Linux" --onefile --add-data="frontend/dist:frontend_dist" backend/run.py

echo "[4/4] Done!"
echo "The executable is located in: dist/EmailSender_Linux"
