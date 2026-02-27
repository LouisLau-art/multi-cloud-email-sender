@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

set "EXPECTED_TRACK_DOMAIN=https://track-dev.louisliu.fun"

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
powershell -NoProfile -Command "try{$u=$env:OPEN_PING_URL;$r=Invoke-WebRequest -UseBasicParsing -Method GET -Uri $u -TimeoutSec 10; if($r.StatusCode -eq 200){exit 0}else{exit 1}}catch{exit 1}"
if errorlevel 1 (
    echo [FAIL] Endpoint not reachable: !OPEN_PING_URL!
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
