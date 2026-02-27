@echo off
setlocal
chcp 65001 >nul

echo ==========================================
echo     Email System Start (Double Click)
echo ==========================================
echo.
echo Running: start.bat --no-tunnel
echo.

call "%~dp0start.bat" --no-tunnel

exit /b %errorlevel%
