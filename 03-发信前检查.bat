@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

set "EXPECTED_TRACK_DOMAIN=https://track-dev.louisliu.fun"
set "LOG_DIR=%~dp0logs"
set "DIAG_LOG=%LOG_DIR%\precheck_diagnostics.log"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1

echo ==========================================
echo     Pre-Send Health Check (Double Click)
echo ==========================================
echo.

echo [1/5] Check backend: http://localhost:8000
powershell -NoProfile -Command "try{$r=Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:8000/api/settings' -TimeoutSec 5; if($r.StatusCode -eq 200){exit 0}else{exit 1}}catch{exit 1}"
if errorlevel 1 (
    echo [FAIL] Backend is not ready. Run the start script first.
    echo.
    pause
    exit /b 1
)
echo [OK] Backend is running.
echo.

echo [2/5] Read current track_domain...
set "TRACK_DOMAIN="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "try{(Invoke-RestMethod 'http://localhost:8000/api/settings' -TimeoutSec 5).track_domain}catch{''}"`) do set "TRACK_DOMAIN=%%I"
if not defined TRACK_DOMAIN (
    echo [FAIL] track_domain is empty.
    echo.
    pause
    exit /b 1
)
echo [INFO] track_domain: !TRACK_DOMAIN!
echo.

echo [3/5] Check track_domain value...
if /I not "!TRACK_DOMAIN!"=="%EXPECTED_TRACK_DOMAIN%" (
    echo [FAIL] track_domain mismatch.
    echo [MUST] %EXPECTED_TRACK_DOMAIN%
    echo [NOW ] !TRACK_DOMAIN!
    echo.
    pause
    exit /b 1
)
echo [OK] track_domain is correct.
echo.

echo [4/5] Check public open tracking endpoint...
set "OPEN_PING_URL=!TRACK_DOMAIN!/api/track/open/ping-test"
powershell -NoProfile -Command "try{[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12}catch{}; try{$u=$env:OPEN_PING_URL;$r=Invoke-WebRequest -UseBasicParsing -Method GET -Uri $u -TimeoutSec 10; if($r.StatusCode -eq 200){exit 0}else{exit 1}}catch{exit 1}"
if errorlevel 1 (
    echo [FAIL] Endpoint not reachable: !OPEN_PING_URL!
    echo [HINT] If your PowerShell is old, force TLS1.2 and retry:
    echo        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    call :PrintTrackingDiagnostics "!TRACK_DOMAIN!"
    echo.
    pause
    exit /b 1
)
echo [OK] Public endpoint is reachable (200).
echo.

echo [5/5] Check cloudflared service...
powershell -NoProfile -Command "try{$s=Get-Service cloudflared -ErrorAction Stop; if($s.Status -eq 'Running'){exit 0}else{exit 2}}catch{exit 1}"
if errorlevel 2 (
    echo [FAIL] cloudflared service is installed but not running.
    echo.
    pause
    exit /b 1
)
if errorlevel 1 (
    echo [FAIL] cloudflared service not found.
    echo.
    pause
    exit /b 1
)
echo [OK] cloudflared service is running.
echo.

echo ==========================================
echo PASS: Safe to send campaigns.
echo ==========================================
echo.
pause
exit /b 0

:PrintTrackingDiagnostics
set "DIAG_DOMAIN=%~1"
set "DIAG_URL=%DIAG_DOMAIN%/api/track/open/ping-test"
echo.
echo [DIAG] ===== Tracking Diagnostics =====
echo [DIAG] expected_track_domain: %EXPECTED_TRACK_DOMAIN%
echo [DIAG] current_track_domain: %DIAG_DOMAIN%
echo [DIAG] ping_url: %DIAG_URL%
echo [DIAG] log_file: %DIAG_LOG%
(echo ===== [%date% %time%] pre-send diagnostics =====)>>"%DIAG_LOG%" 2>nul
(echo expected=%EXPECTED_TRACK_DOMAIN%)>>"%DIAG_LOG%" 2>nul
(echo current=%DIAG_DOMAIN%)>>"%DIAG_LOG%" 2>nul

echo [DIAG] 1/5 Local backend ping ^(localhost:8000^):
powershell -NoProfile -Command "try{$r=Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:8000/api/track/open/ping-test' -TimeoutSec 5; Write-Output ('StatusCode=' + $r.StatusCode)}catch{Write-Output ('Error=' + $_.Exception.Message)}"
powershell -NoProfile -Command "try{$r=Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:8000/api/track/open/ping-test' -TimeoutSec 5; 'StatusCode=' + $r.StatusCode}catch{'Error=' + $_.Exception.Message}" >>"%DIAG_LOG%" 2>&1

echo [DIAG] 2/5 DNS resolve:
powershell -NoProfile -Command "$u=$env:DIAG_DOMAIN; try{$h=([Uri]$u).DnsSafeHost}catch{$h=''}; if([string]::IsNullOrWhiteSpace($h)){Write-Output 'HostParseError'} else { nslookup $h 2>&1 }"
powershell -NoProfile -Command "$u=$env:DIAG_DOMAIN; try{$h=([Uri]$u).DnsSafeHost}catch{$h=''}; if([string]::IsNullOrWhiteSpace($h)){Write-Output 'HostParseError'} else { nslookup $h 2>&1 }" >>"%DIAG_LOG%" 2>&1

echo [DIAG] 3/5 TCP 443 connectivity:
powershell -NoProfile -Command "$u=$env:DIAG_DOMAIN; try{$h=([Uri]$u).DnsSafeHost}catch{$h=''}; if([string]::IsNullOrWhiteSpace($h)){Write-Output 'HostParseError'} else { try{$t=Test-NetConnection -ComputerName $h -Port 443 -WarningAction SilentlyContinue; Write-Output ('TcpTestSucceeded=' + $t.TcpTestSucceeded); if($t.RemoteAddress){Write-Output ('RemoteAddress=' + $t.RemoteAddress)}}catch{Write-Output ('Error=' + $_.Exception.Message)} }"
powershell -NoProfile -Command "$u=$env:DIAG_DOMAIN; try{$h=([Uri]$u).DnsSafeHost}catch{$h=''}; if([string]::IsNullOrWhiteSpace($h)){Write-Output 'HostParseError'} else { try{$t=Test-NetConnection -ComputerName $h -Port 443 -WarningAction SilentlyContinue; Write-Output ('TcpTestSucceeded=' + $t.TcpTestSucceeded); if($t.RemoteAddress){Write-Output ('RemoteAddress=' + $t.RemoteAddress)}}catch{Write-Output ('Error=' + $_.Exception.Message)} }" >>"%DIAG_LOG%" 2>&1

echo [DIAG] 4/5 Public HTTPS ping:
powershell -NoProfile -Command "try{[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12}catch{}; $u=$env:DIAG_URL; try{$r=Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec 10; Write-Output ('StatusCode=' + $r.StatusCode)}catch{Write-Output ('Error=' + $_.Exception.Message)}"
powershell -NoProfile -Command "try{[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12}catch{}; $u=$env:DIAG_URL; try{$r=Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec 10; Write-Output ('StatusCode=' + $r.StatusCode)}catch{Write-Output ('Error=' + $_.Exception.Message)}" >>"%DIAG_LOG%" 2>&1

echo [DIAG] 5/5 cloudflared service:
powershell -NoProfile -Command "try{$s=Get-Service cloudflared -ErrorAction Stop; Write-Output ('Status=' + $s.Status)}catch{Write-Output 'Status=NOT_FOUND'}"
powershell -NoProfile -Command "try{$s=Get-Service cloudflared -ErrorAction Stop; Write-Output ('Status=' + $s.Status)}catch{Write-Output 'Status=NOT_FOUND'}" >>"%DIAG_LOG%" 2>&1

echo [DIAG] ===== End Diagnostics =====
echo.
exit /b 0
