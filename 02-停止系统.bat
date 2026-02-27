@echo off
setlocal
chcp 65001 >nul

echo ==========================================
echo     Email System Stop (Double Click)
echo ==========================================
echo.
echo Running: start.bat -s
echo.

call "%~dp0start.bat" -s

exit /b %errorlevel%
