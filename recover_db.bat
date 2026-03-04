@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

echo ==========================================
echo      SQLite Database Recovery (Windows)
echo ==========================================

set "ROOT_DIR=%~dp0"
if "%ROOT_DIR:~-1%"=="\" set "ROOT_DIR=%ROOT_DIR:~0,-1%"
set "BACKEND_DIR=%ROOT_DIR%\backend"
set "DB_DIR=%BACKEND_DIR%"
set "DB_NAME=email_app.db"
set "SQLITE3_EXE="

if not exist "%BACKEND_DIR%" (
    echo [ERROR] backend directory not found: "%BACKEND_DIR%"
    pause
    exit /b 1
)

if not exist "%DB_DIR%\%DB_NAME%" (
    if exist "%ROOT_DIR%\%DB_NAME%" (
        set "DB_DIR=%ROOT_DIR%"
    ) else (
        echo [ERROR] Cannot find "%DB_NAME%" under:
        echo         "%BACKEND_DIR%"
        echo         "%ROOT_DIR%"
        pause
        exit /b 1
    )
)

echo [INFO] Working directory: "%DB_DIR%"
echo [INFO] Stopping running services...
if exist "%ROOT_DIR%\start.bat" (
    call "%ROOT_DIR%\start.bat" -s >nul 2>&1
)

set "TS=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "TS=%TS: =0%"
set "RECOVERY_DIR=%DB_DIR%\recovery"
if not exist "%RECOVERY_DIR%" mkdir "%RECOVERY_DIR%"

echo [STEP 1/6] Backup raw database files...
copy /Y "%DB_DIR%\%DB_NAME%" "%RECOVERY_DIR%\%DB_NAME%.raw.%TS%.bak" >nul
if exist "%DB_DIR%\%DB_NAME%-wal" copy /Y "%DB_DIR%\%DB_NAME%-wal" "%RECOVERY_DIR%\%DB_NAME%-wal.raw.%TS%.bak" >nul
if exist "%DB_DIR%\%DB_NAME%-shm" copy /Y "%DB_DIR%\%DB_NAME%-shm" "%RECOVERY_DIR%\%DB_NAME%-shm.raw.%TS%.bak" >nul

echo [STEP 2/6] Check sqlite3 availability...
if exist "%ROOT_DIR%\sqlite3.exe" (
    set "SQLITE3_EXE=%ROOT_DIR%\sqlite3.exe"
) else if exist "%BACKEND_DIR%\sqlite3.exe" (
    set "SQLITE3_EXE=%BACKEND_DIR%\sqlite3.exe"
) else (
    for /f "usebackq delims=" %%I in (`where sqlite3 2^>nul`) do (
        set "SQLITE3_EXE=%%I"
        goto :sqlite_found
    )
)
:sqlite_found
if not defined SQLITE3_EXE (
    echo [ERROR] sqlite3.exe not found.
    echo [HINT] Put sqlite3.exe in project root:
    echo        "%ROOT_DIR%\sqlite3.exe"
    echo [HINT] Or install SQLite CLI and ensure sqlite3 is in PATH.
    pause
    exit /b 1
)
echo [INFO] Using sqlite3: "%SQLITE3_EXE%"

echo [STEP 3/6] Select source file for recovery...
set "SOURCE_FILE="
for /f "usebackq delims=" %%F in (`powershell -NoProfile -Command "$f = Get-ChildItem -Path '%DB_DIR%' -Filter '%DB_NAME%*.corrupt' -File -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '\.corrupt$' } | Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty Name; if($f){$f}"`) do (
    set "SOURCE_FILE=%%F"
)
if not defined SOURCE_FILE (
    set "SOURCE_FILE=%DB_NAME%"
)
echo [INFO] Recovery source: "%DB_DIR%\%SOURCE_FILE%"

set "RECOVER_SQL=%RECOVERY_DIR%\recovered_%TS%.sql"
set "RECOVER_DB=%RECOVERY_DIR%\recovered_%TS%.db"

echo [STEP 4/6] Run .recover...
pushd "%DB_DIR%"
"%SQLITE3_EXE%" "%SOURCE_FILE%" ".recover" > "%RECOVER_SQL%"
if errorlevel 1 (
    popd
    echo [ERROR] sqlite3 .recover failed.
    echo [INFO] Check source file and sqlite3 version.
    pause
    exit /b 1
)

"%SQLITE3_EXE%" "%RECOVER_DB%" < "%RECOVER_SQL%"
if errorlevel 1 (
    popd
    echo [ERROR] Failed to rebuild recovered database from SQL dump.
    pause
    exit /b 1
)

set "INTEGRITY_RESULT="
for /f "usebackq delims=" %%I in (`"%SQLITE3_EXE%" "%RECOVER_DB%" "PRAGMA integrity_check;"`) do (
    set "INTEGRITY_RESULT=%%I"
)
echo [INFO] integrity_check: !INTEGRITY_RESULT!
if /I not "!INTEGRITY_RESULT!"=="ok" (
    popd
    echo [ERROR] Recovered DB integrity check is not OK.
    pause
    exit /b 1
)

echo [STEP 5/6] Replace online DB with recovered DB...
copy /Y "%DB_NAME%" "%RECOVERY_DIR%\%DB_NAME%.before_replace.%TS%.bak" >nul
if exist "%DB_NAME%-wal" del /f /q "%DB_NAME%-wal"
if exist "%DB_NAME%-shm" del /f /q "%DB_NAME%-shm"
copy /Y "%RECOVER_DB%" "%DB_NAME%" >nul
if errorlevel 1 (
    popd
    echo [ERROR] Failed to replace active DB file.
    pause
    exit /b 1
)
popd

echo [STEP 6/6] Done.
echo [OK] Recovery completed.
echo [INFO] Recovered DB: "%RECOVER_DB%"
echo [INFO] Active DB:    "%DB_DIR%\%DB_NAME%"
echo [INFO] Backups:      "%RECOVERY_DIR%"
echo.
echo Next:
echo   1) Start system: "%ROOT_DIR%\start.bat --no-tunnel"
echo   2) Verify campaigns/templates/contacts in UI.
echo.
pause
exit /b 0
