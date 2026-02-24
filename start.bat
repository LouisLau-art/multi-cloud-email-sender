@echo off
setlocal EnableExtensions EnableDelayedExpansion

echo ==========================================
echo      Email Sender Start (Windows)
echo ==========================================

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "LOG_DIR=%ROOT_DIR%\logs"
set "BACKEND_LOG=%LOG_DIR%\backend.log"
set "FRONTEND_LOG=%LOG_DIR%\frontend.log"
set "BACKEND_VENV=%ROOT_DIR%\backend\.venv"
set "BACKEND_PY=%BACKEND_VENV%\Scripts\python.exe"
set "STARTUP_TIMEOUT_SECONDS=15"
set "FORCE_KILL=0"
set "DAEMON_MODE=0"
set "STOP_ONLY=0"

:ParseArgs
if "%~1"=="" goto ArgsDone
if /I "%~1"=="-k" (
    set "FORCE_KILL=1"
) else if /I "%~1"=="-d" (
    set "DAEMON_MODE=1"
) else if /I "%~1"=="-s" (
    set "STOP_ONLY=1"
) else (
    echo [ERROR] Unknown option: %~1
    echo Usage: %~n0 [-d] [-k] [-s]
    echo   -d  Start in daemon mode ^(do not follow logs^)
    echo   -k  Force-kill listeners on 8000/5173 before start
    echo   -s  Stop services on 8000/5173 and exit
    exit /b 1
)
shift
goto ParseArgs

:ArgsDone
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
type nul >> "%BACKEND_LOG%"
type nul >> "%FRONTEND_LOG%"
echo ===== [%date% %time%] start.bat invoked =====>>"%BACKEND_LOG%"
echo ===== [%date% %time%] start.bat invoked =====>>"%FRONTEND_LOG%"

if "%STOP_ONLY%"=="1" (
    echo [Stop] Stopping listeners on ports 8000/5173...
    call :KillPort 8000
    call :KillPort 5173
    echo [Stop] Done.
    exit /b 0
)

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+.
    pause
    exit /b 1
)

node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Please install Node.js 18+.
    pause
    exit /b 1
)

if not exist "%BACKEND_PY%" (
    echo [Setup] Creating backend virtual environment: %BACKEND_VENV%
    python -m venv "%BACKEND_VENV%"
    if errorlevel 1 (
        echo [ERROR] Failed to create backend virtual environment.
        pause
        exit /b 1
    )
)

"%BACKEND_PY%" -c "import uvicorn,sys; sys.exit(0 if hasattr(uvicorn,'run') else 1)" >nul 2>&1
if errorlevel 1 (
    echo [Setup] Installing backend dependencies...
    "%BACKEND_PY%" -m pip install --upgrade pip >nul 2>&1
    "%BACKEND_PY%" -m pip install -r "%ROOT_DIR%\backend\requirements.txt"
    if errorlevel 1 (
        echo [ERROR] Failed to install backend dependencies.
        pause
        exit /b 1
    )
)

if not exist "%ROOT_DIR%\frontend\node_modules" (
    echo [Setup] Installing frontend dependencies...
    pushd "%ROOT_DIR%\frontend"
    call npm install
    popd
    if errorlevel 1 (
        echo [ERROR] Failed to install frontend dependencies.
        pause
        exit /b 1
    )
)

if "%FORCE_KILL%"=="1" (
    echo [WARN] Force-killing listeners on 8000/5173...
    call :KillPort 8000
    call :KillPort 5173
)

call :EnsurePortFree 8000
if errorlevel 1 (
    echo Use -k to force-kill the process currently occupying port 8000.
    pause
    exit /b 1
)

call :EnsurePortFree 5173
if errorlevel 1 (
    echo Use -k to force-kill the process currently occupying port 5173.
    pause
    exit /b 1
)

echo [Start] Launching backend...
start "Email Backend" /MIN cmd /c "cd /d ""%ROOT_DIR%\backend"" && ""%BACKEND_PY%"" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 >> ""%BACKEND_LOG%"" 2>&1"

call :WaitForPort 8000 Backend "%BACKEND_LOG%"
if errorlevel 1 (
    pause
    exit /b 1
)

echo [Start] Launching frontend...
start "Email Frontend" /MIN cmd /c "cd /d ""%ROOT_DIR%\frontend"" && npm run dev -- --host >> ""%FRONTEND_LOG%"" 2>&1"

call :WaitForPort 5173 Frontend "%FRONTEND_LOG%"
if errorlevel 1 (
    pause
    exit /b 1
)

echo.
echo App running.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:5173
echo.
echo Logs:
echo   %BACKEND_LOG%
echo   %FRONTEND_LOG%
echo.
echo Stop command:
echo   %~n0 -s
echo.

if "%DAEMON_MODE%"=="1" (
    echo Daemon mode enabled. Services continue in background.
    exit /b 0
)

echo Foreground log view enabled. Press Ctrl+C to stop log follow.
powershell -NoProfile -Command "Get-Content -Path '%BACKEND_LOG%','%FRONTEND_LOG%' -Tail 80 -Wait"
echo.
echo Log follow stopped. Services are still running.
echo Use %~n0 -s to stop services.
pause
exit /b 0

:EnsurePortFree
set "PORT=%~1"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    echo [ERROR] Port %PORT% is in use by PID %%P.
    exit /b 1
)
exit /b 0

:WaitForPort
set "PORT=%~1"
set "SERVICE_NAME=%~2"
set "SERVICE_LOG=%~3"
set /a COUNT=0

:WaitForPortLoop
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    exit /b 0
)

if !COUNT! GEQ %STARTUP_TIMEOUT_SECONDS% (
    echo [ERROR] %SERVICE_NAME% failed to start on port %PORT%.
    echo [ERROR] Recent logs: %SERVICE_LOG%
    powershell -NoProfile -Command "if (Test-Path '%SERVICE_LOG%') { Get-Content '%SERVICE_LOG%' -Tail 120 }"
    exit /b 1
)

set /a COUNT+=1
timeout /t 1 /nobreak >nul
goto :WaitForPortLoop

:KillPort
set "PORT=%~1"
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
    echo [INFO] Killing PID %%P on port %PORT%.
    taskkill /F /PID %%P >nul 2>&1
)
exit /b 0
