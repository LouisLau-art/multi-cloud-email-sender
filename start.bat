@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Force UTF-8 console + Python I/O encoding on Windows.
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=UTF-8"

echo ==========================================
echo      Email Sender Start (Windows)
echo ==========================================

set "SCRIPT_NAME=%~n0"
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
set "SHOW_ACCESS_POPUP=1"
set "ENABLE_QUICK_TUNNEL=1"
set "TUNNEL_START_TIMEOUT_SECONDS=25"
set "TUNNEL_LOG=%LOG_DIR%\tunnel.log"
set "TUNNEL_URL_FILE=%LOG_DIR%\track_domain.txt"
set "CLOUDFLARED_EXE="
set "TUNNEL_URL="

:ParseArgs
if "%~1"=="" goto ArgsDone
if /I "%~1"=="-k" (
    set "FORCE_KILL=1"
) else if /I "%~1"=="-d" (
    set "DAEMON_MODE=1"
) else if /I "%~1"=="-s" (
    set "STOP_ONLY=1"
) else if /I "%~1"=="--no-popup" (
    set "SHOW_ACCESS_POPUP=0"
) else if /I "%~1"=="--no-tunnel" (
    set "ENABLE_QUICK_TUNNEL=0"
) else (
    echo [ERROR] Unknown option: %~1
    echo Usage: %~n0 [-d] [-k] [-s] [--no-popup] [--no-tunnel]
    echo   -d  Start in daemon mode ^(do not follow logs^)
    echo   -k  Force-kill listeners on 8000/5173 before start
    echo   -s  Stop services on 8000/5173 and exit
    echo   --no-popup  Do not show startup access popup
    echo   --no-tunnel  Do not auto-start cloudflared quick tunnel
    exit /b 1
)
shift
goto ParseArgs

:ArgsDone
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
if not exist "%BACKEND_LOG%" type nul > "%BACKEND_LOG%" 2>nul
if not exist "%FRONTEND_LOG%" type nul > "%FRONTEND_LOG%" 2>nul
if not exist "%TUNNEL_LOG%" type nul > "%TUNNEL_LOG%" 2>nul
(echo ===== [%date% %time%] start.bat invoked =====)>>"%BACKEND_LOG%" 2>nul
(echo ===== [%date% %time%] start.bat invoked =====)>>"%FRONTEND_LOG%" 2>nul
(echo ===== [%date% %time%] start.bat invoked =====)>>"%TUNNEL_LOG%" 2>nul

if "%STOP_ONLY%"=="1" (
    echo [Stop] Stopping listeners on ports 8000/5173 and tunnel...
    call :KillPort 8000
    call :KillPort 5173
    call :StopTunnel
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

"%BACKEND_PY%" -c "import sys; import uvicorn, fastapi, sqlalchemy, itsdangerous; sys.exit(0 if hasattr(uvicorn,'run') else 1)" >nul 2>&1
if errorlevel 1 (
    echo [Setup] Installing/repairing backend dependencies...
    "%BACKEND_PY%" -m pip install --upgrade pip
    "%BACKEND_PY%" -m pip install -r "%ROOT_DIR%\backend\requirements.txt"
    if errorlevel 1 (
        echo [ERROR] Failed to install backend dependencies.
        pause
        exit /b 1
    )
    "%BACKEND_PY%" -c "import sys; import uvicorn, fastapi, sqlalchemy, itsdangerous; sys.exit(0 if hasattr(uvicorn,'run') else 1)" >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Backend dependencies are still incomplete after installation.
        echo [ERROR] Please verify Python permissions/network and rerun start.bat.
        pause
        exit /b 1
    )
)

set "NEED_FRONTEND_INSTALL=0"
if not exist "%ROOT_DIR%\frontend\node_modules" (
    set "NEED_FRONTEND_INSTALL=1"
) else (
    pushd "%ROOT_DIR%\frontend"
    call npm ls --depth=0 >nul 2>&1
    if errorlevel 1 set "NEED_FRONTEND_INSTALL=1"
    if not exist "node_modules\dompurify\package.json" set "NEED_FRONTEND_INSTALL=1"
    popd
)

if "%NEED_FRONTEND_INSTALL%"=="1" (
    echo [Setup] Installing/repairing frontend dependencies...
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
    call :StopTunnel
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

call :PrepareTrackingDomain
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
if defined TUNNEL_URL (
    echo Track domain: %TUNNEL_URL%
)
call :PrintFrontendNetworkInfo
call :ShowAccessPopup
echo.
echo Logs:
echo   %BACKEND_LOG%
echo   %FRONTEND_LOG%
if "%ENABLE_QUICK_TUNNEL%"=="1" echo   %TUNNEL_LOG%
echo.
echo Stop command:
echo   %SCRIPT_NAME% -s
echo.

if "%DAEMON_MODE%"=="1" (
    echo Daemon mode enabled. Services continue in background.
    exit /b 0
)

echo Foreground log view enabled. Press Ctrl+C to stop log follow.
powershell -NoProfile -Command "Get-Content -Path '%BACKEND_LOG%','%FRONTEND_LOG%' -Tail 80 -Wait"
echo.
echo Log follow stopped. Services are still running.
echo Use %SCRIPT_NAME% -s to stop services.
pause
exit /b 0

:PrepareTrackingDomain
call :ReadCurrentTrackDomain
if defined CURRENT_TRACK_DOMAIN (
    echo [Track] Current track_domain: %CURRENT_TRACK_DOMAIN%
) else (
    echo [Track] Current track_domain is empty.
)

call :IsFixedTrackDomain "%CURRENT_TRACK_DOMAIN%"
if errorlevel 1 (
    if "%ENABLE_QUICK_TUNNEL%"=="0" (
        echo [Tunnel] Auto quick tunnel disabled by flag.
        echo [Track] No fixed track_domain detected. Public tracking readiness check skipped.
        exit /b 0
    )
    call :StartTunnelAndSyncTrackDomain
    exit /b %errorlevel%
)

echo [Track] Fixed track_domain detected. Verifying public tracking endpoint...
call :CheckTrackDomainHealth "%CURRENT_TRACK_DOMAIN%"
if errorlevel 1 (
    echo [ERROR] Fixed track_domain is unreachable: %CURRENT_TRACK_DOMAIN%
    echo [ERROR] Startup aborted to avoid sending with broken open/click tracking.
    powershell -NoProfile -Command "try{$s=Get-Service cloudflared -ErrorAction Stop; if($s.Status -eq 'Running'){exit 0}else{exit 2}}catch{exit 1}" >nul 2>&1
    if errorlevel 2 (
        echo [HINT] cloudflared service exists but is not running.
        echo [HINT] Run in admin PowerShell: Start-Service cloudflared
    ) else (
        if errorlevel 1 (
            echo [HINT] cloudflared service not found.
            echo [HINT] If using named tunnel, install service once: cloudflared service install
        )
    )
    exit /b 1
)

set "TUNNEL_URL=%CURRENT_TRACK_DOMAIN%"
echo %TUNNEL_URL%>"%TUNNEL_URL_FILE%"
echo [Track] Fixed track_domain is healthy.
exit /b 0

:ReadCurrentTrackDomain
set "CURRENT_TRACK_DOMAIN="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "try{$v=(Invoke-RestMethod -Method Get -Uri 'http://localhost:8000/api/settings' -TimeoutSec 5).track_domain; if($null -ne $v){$v.ToString().Trim()}}catch{}"`) do (
    set "CURRENT_TRACK_DOMAIN=%%I"
)
exit /b 0

:IsFixedTrackDomain
set "TRACK_DOMAIN_INPUT=%~1"
if not defined TRACK_DOMAIN_INPUT exit /b 1
powershell -NoProfile -Command "$v=$env:TRACK_DOMAIN_INPUT; try { if([string]::IsNullOrWhiteSpace($v)){exit 1}; $uri=$null; if(-not [Uri]::TryCreate($v,[UriKind]::Absolute,[ref]$uri)){exit 1}; $domainHost=$uri.DnsSafeHost.ToLowerInvariant(); if($domainHost -eq 'localhost' -or $domainHost -eq '127.0.0.1'){exit 1}; if($domainHost -eq 'trycloudflare.com' -or $domainHost.EndsWith('.trycloudflare.com')){exit 1}; $ip=$null; if([System.Net.IPAddress]::TryParse($domainHost, [ref]$ip)){ if($ip.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork){ $b=$ip.GetAddressBytes(); if($b[0] -eq 10 -or $b[0] -eq 127){exit 1}; if($b[0] -eq 192 -and $b[1] -eq 168){exit 1}; if($b[0] -eq 172 -and $b[1] -ge 16 -and $b[1] -le 31){exit 1}; } }; exit 0 } catch { exit 1 }" >nul 2>&1
exit /b %errorlevel%

:CheckTrackDomainHealth
set "TRACK_DOMAIN_INPUT=%~1"
if not defined TRACK_DOMAIN_INPUT exit /b 1
powershell -NoProfile -Command "$base=$env:TRACK_DOMAIN_INPUT.Trim().TrimEnd('/'); if([string]::IsNullOrWhiteSpace($base)){exit 1}; $url=$base + '/api/track/open/ping-test'; try{$r=Invoke-WebRequest -UseBasicParsing -Method Get -Uri $url -TimeoutSec 10; if($r.StatusCode -eq 200){exit 0}else{exit 1}}catch{exit 1}" >nul 2>&1
exit /b %errorlevel%

:StartTunnelAndSyncTrackDomain
if "%ENABLE_QUICK_TUNNEL%"=="0" (
    echo [Tunnel] Auto quick tunnel disabled.
    exit /b 0
)

call :ResolveCloudflared
if errorlevel 1 (
    echo [WARN] cloudflared/cloudflare not found. Tracking domain will not auto-update.
    echo [WARN] Put cloudflared.exe ^(or cloudflare.exe^) in project root, %%USERPROFILE%%\Downloads, or PATH.
    exit /b 1
)

call :StopTunnel
(echo ===== [%date% %time%] tunnel start =====)>>"%TUNNEL_LOG%" 2>nul
echo [Tunnel] Launching cloudflared quick tunnel...
start "Email Tunnel" /MIN cmd /c """%CLOUDFLARED_EXE%"" tunnel --url http://localhost:8000 >> ""%TUNNEL_LOG%"" 2>&1"

call :WaitForTunnelUrl
if errorlevel 1 (
    echo [WARN] Could not get quick tunnel URL within %TUNNEL_START_TIMEOUT_SECONDS%s.
    echo [WARN] Check: %TUNNEL_LOG%
    exit /b 1
)

echo [Tunnel] URL: %TUNNEL_URL%
echo %TUNNEL_URL%>"%TUNNEL_URL_FILE%"

powershell -NoProfile -Command "$url='%TUNNEL_URL%'; $body=@{ track_domain=$url } | ConvertTo-Json; Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/api/settings' -ContentType 'application/json' -Body $body | Out-Null" >nul 2>&1
if errorlevel 1 (
    echo [WARN] Tunnel is up but failed to sync track_domain to backend settings.
    exit /b 1
)
echo [Tunnel] track_domain auto-updated.
exit /b 0

:ResolveCloudflared
if exist "%ROOT_DIR%\cloudflared.exe" (
    set "CLOUDFLARED_EXE=%ROOT_DIR%\cloudflared.exe"
    exit /b 0
)
if exist "%ROOT_DIR%\cloudflare.exe" (
    set "CLOUDFLARED_EXE=%ROOT_DIR%\cloudflare.exe"
    exit /b 0
)
if exist "%USERPROFILE%\Downloads\cloudflared.exe" (
    set "CLOUDFLARED_EXE=%USERPROFILE%\Downloads\cloudflared.exe"
    exit /b 0
)
if exist "%USERPROFILE%\Downloads\cloudflare.exe" (
    set "CLOUDFLARED_EXE=%USERPROFILE%\Downloads\cloudflare.exe"
    exit /b 0
)
for /f "usebackq delims=" %%I in (`where cloudflared 2^>nul`) do (
    set "CLOUDFLARED_EXE=%%I"
    exit /b 0
)
for /f "usebackq delims=" %%I in (`where cloudflare 2^>nul`) do (
    set "CLOUDFLARED_EXE=%%I"
    exit /b 0
)
exit /b 1

:StopTunnel
powershell -NoProfile -Command "$ErrorActionPreference='SilentlyContinue'; Get-CimInstance Win32_Process -Filter \"Name='cloudflared.exe' OR Name='cloudflare.exe'\" | Where-Object { $_.CommandLine -match 'tunnel\\s+--url\\s+http://localhost:8000' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
exit /b 0

:WaitForTunnelUrl
set "TUNNEL_URL="
set /a TUNNEL_COUNT=0

:WaitForTunnelUrlLoop
for /f "usebackq delims=" %%U in (`powershell -NoProfile -Command "$m = Select-String -Path '%TUNNEL_LOG%' -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -AllMatches | Select-Object -Last 1; if($m){$m.Matches[0].Value}"`) do (
    set "TUNNEL_URL=%%U"
)
if defined TUNNEL_URL exit /b 0
if !TUNNEL_COUNT! GEQ %TUNNEL_START_TIMEOUT_SECONDS% exit /b 1
set /a TUNNEL_COUNT+=1
timeout /t 1 /nobreak >nul
goto :WaitForTunnelUrlLoop

:EnsurePortFree
set "PORT=%~1"
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "$p = Get-NetTCPConnection -State Listen -LocalPort %PORT% -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess; if($p){$p}"`) do (
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
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "$p = Get-NetTCPConnection -State Listen -LocalPort %PORT% -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty OwningProcess; if($p){$p}"`) do (
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
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "Get-NetTCPConnection -State Listen -LocalPort %PORT% -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique"`) do (
    echo [INFO] Killing PID %%P on port %PORT%.
    taskkill /F /PID %%P >nul 2>&1
)
exit /b 0

:PrintFrontendNetworkInfo
set "HAS_FRONTEND_IP=0"
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$ips = Get-NetIPConfiguration -ErrorAction SilentlyContinue | ForEach-Object { $_.IPv4Address.IPAddress } | Where-Object { $_ -and $_ -ne '127.0.0.1' } | Sort-Object -Unique; $ips"`) do (
    set "HAS_FRONTEND_IP=1"
    echo [frontend]   -^> Network: http://%%I:5173/
)
if "%HAS_FRONTEND_IP%"=="0" (
    echo [frontend]   -^> Network: unavailable ^(no non-loopback IPv4 detected^)
)
exit /b 0

:ShowAccessPopup
if "%SHOW_ACCESS_POPUP%"=="0" exit /b 0
if "%DAEMON_MODE%"=="1" exit /b 0

powershell -NoProfile -Command ^
    "$ErrorActionPreference='Stop';" ^
    "$ips = Get-NetIPConfiguration -ErrorAction SilentlyContinue | ForEach-Object { $_.IPv4Address.IPAddress } | Where-Object { $_ -and $_ -ne '127.0.0.1' } | Sort-Object -Unique;" ^
    "$lines = @('Email Sender is ready.','', 'Open frontend URL:', '  http://localhost:5173');" ^
    "foreach($ip in $ips){ $lines += ('  http://' + $ip + ':5173') };" ^
    "if(Test-Path '%TUNNEL_URL_FILE%'){ $track = (Get-Content '%TUNNEL_URL_FILE%' -ErrorAction SilentlyContinue | Select-Object -First 1).Trim(); if($track){ $lines += ''; $lines += ('Track domain: ' + $track) } };" ^
    "$msg = $lines -join [Environment]::NewLine;" ^
    "Add-Type -AssemblyName System.Windows.Forms;" ^
    "[void][System.Windows.Forms.MessageBox]::Show($msg,'Email Sender Startup','OK','Information')" >nul 2>&1

exit /b 0
