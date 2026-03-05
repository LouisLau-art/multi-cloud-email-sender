@echo off
setlocal
chcp 65001 >nul

echo ==========================================
echo     Email System Start (Double Click)
echo ==========================================
echo.
echo Running: start.bat --temp-mode
echo.

call "%~dp0start.bat" --temp-mode

exit /b %errorlevel%
