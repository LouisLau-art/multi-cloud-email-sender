@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "LOG_DIR=%ROOT_DIR%\logs"
set "DIAG_LOG=%LOG_DIR%\tracking_diagnostics_manual.log"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>&1

set "TRACK_DOMAIN=%~1"
if not defined TRACK_DOMAIN (
    for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "try{(Invoke-RestMethod 'http://localhost:8000/api/settings' -TimeoutSec 5).track_domain}catch{''}"`) do set "TRACK_DOMAIN=%%I"
)

echo ==========================================
echo     Tracking Diagnostics (Manual)
echo ==========================================
echo.

if not defined TRACK_DOMAIN (
    echo [FAIL] Cannot read track_domain from backend. Is backend running on localhost:8000?
    echo.
    pause
    exit /b 1
)

set "TRACK_PING_URL=%TRACK_DOMAIN%/api/track/open/ping-test"

echo [INFO] track_domain: %TRACK_DOMAIN%
echo [INFO] ping_url: %TRACK_PING_URL%
echo [INFO] log_file: %DIAG_LOG%
echo.

(echo ===== [%date% %time%] manual tracking diagnostics =====)>>"%DIAG_LOG%" 2>nul
(echo track_domain=%TRACK_DOMAIN%)>>"%DIAG_LOG%" 2>nul

echo [DIAG] 1/5 Local backend ping ^(localhost:8000^):
powershell -NoProfile -Command "try{$r=Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:8000/api/track/open/ping-test' -TimeoutSec 5; Write-Output ('StatusCode=' + $r.StatusCode)}catch{Write-Output ('Error=' + $_.Exception.Message)}"
powershell -NoProfile -Command "try{$r=Invoke-WebRequest -UseBasicParsing -Uri 'http://localhost:8000/api/track/open/ping-test' -TimeoutSec 5; 'StatusCode=' + $r.StatusCode}catch{'Error=' + $_.Exception.Message}" >>"%DIAG_LOG%" 2>&1
echo.

echo [DIAG] 2/5 DNS resolve:
powershell -NoProfile -Command "$u=$env:TRACK_DOMAIN; try{$h=([Uri]$u).DnsSafeHost}catch{$h=''}; if([string]::IsNullOrWhiteSpace($h)){Write-Output 'HostParseError'} else { nslookup $h 2>&1 }"
powershell -NoProfile -Command "$u=$env:TRACK_DOMAIN; try{$h=([Uri]$u).DnsSafeHost}catch{$h=''}; if([string]::IsNullOrWhiteSpace($h)){Write-Output 'HostParseError'} else { nslookup $h 2>&1 }" >>"%DIAG_LOG%" 2>&1
echo.

echo [DIAG] 3/5 TCP 443 connectivity:
powershell -NoProfile -Command "$u=$env:TRACK_DOMAIN; try{$h=([Uri]$u).DnsSafeHost}catch{$h=''}; if([string]::IsNullOrWhiteSpace($h)){Write-Output 'HostParseError'} else { try{$t=Test-NetConnection -ComputerName $h -Port 443 -WarningAction SilentlyContinue; Write-Output ('TcpTestSucceeded=' + $t.TcpTestSucceeded); if($t.RemoteAddress){Write-Output ('RemoteAddress=' + $t.RemoteAddress)}}catch{Write-Output ('Error=' + $_.Exception.Message)} }"
powershell -NoProfile -Command "$u=$env:TRACK_DOMAIN; try{$h=([Uri]$u).DnsSafeHost}catch{$h=''}; if([string]::IsNullOrWhiteSpace($h)){Write-Output 'HostParseError'} else { try{$t=Test-NetConnection -ComputerName $h -Port 443 -WarningAction SilentlyContinue; Write-Output ('TcpTestSucceeded=' + $t.TcpTestSucceeded); if($t.RemoteAddress){Write-Output ('RemoteAddress=' + $t.RemoteAddress)}}catch{Write-Output ('Error=' + $_.Exception.Message)} }" >>"%DIAG_LOG%" 2>&1
echo.

echo [DIAG] 4/5 Public HTTPS ping:
powershell -NoProfile -Command "try{[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12}catch{}; $u=$env:TRACK_PING_URL; try{$r=Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec 10; Write-Output ('StatusCode=' + $r.StatusCode)}catch{Write-Output ('Error=' + $_.Exception.Message)}"
powershell -NoProfile -Command "try{[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12}catch{}; $u=$env:TRACK_PING_URL; try{$r=Invoke-WebRequest -UseBasicParsing -Uri $u -TimeoutSec 10; Write-Output ('StatusCode=' + $r.StatusCode)}catch{Write-Output ('Error=' + $_.Exception.Message)}" >>"%DIAG_LOG%" 2>&1
echo.

echo [DIAG] 5/5 cloudflared service:
powershell -NoProfile -Command "try{$s=Get-Service cloudflared -ErrorAction Stop; Write-Output ('Status=' + $s.Status)}catch{Write-Output 'Status=NOT_FOUND'}"
powershell -NoProfile -Command "try{$s=Get-Service cloudflared -ErrorAction Stop; Write-Output ('Status=' + $s.Status)}catch{Write-Output 'Status=NOT_FOUND'}" >>"%DIAG_LOG%" 2>&1

echo.
echo [DONE] Diagnostics complete.
echo [DONE] Saved to: %DIAG_LOG%
echo.
pause
exit /b 0
