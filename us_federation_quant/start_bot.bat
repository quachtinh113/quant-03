@echo off
title US_Federation_Quant
color 0A

echo =======================================================
echo          US_Federation_Quant...
echo =======================================================
echo.

:: Ensure we are in the correct directory
cd /d "%~dp0"

:: Set utf-8 encoding for proper emoji and terminal display
chcp 65001 > nul
set PYTHONIOENCODING=utf-8

:: Auto-restart loop (max 50 restarts to prevent infinite crash loops)
set /a RESTART_COUNT=0
set MAX_RESTARTS=50
set RESTART_DELAY=30

:start_loop
set /a RESTART_COUNT+=1

if %RESTART_COUNT% GTR %MAX_RESTARTS% (
    echo.
    echo =======================================================
    echo  ERROR: Max restarts reached [%MAX_RESTARTS%]. Bot will NOT restart.
    echo  Please check logs and fix the issue manually.
    echo =======================================================
    pause > nul
    exit /b 1
)

echo.
echo =======================================================
echo  [STEP 1/2] Checking MT5 GUI Process Lifecycle...
echo =======================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "ensure_mt5_gui.ps1"
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] ensure_mt5_gui returned non-zero code. Attempting to proceed...
)

echo.
echo =======================================================
echo  [STEP 2/2] Launching US Federation Live Runner...
echo =======================================================
python live_federation_runner.py

:: Check exit code
set EXIT_CODE=%ERRORLEVEL%

if %EXIT_CODE% EQU 0 (
    echo.
    echo =======================================================
    echo  Bot stopped gracefully [exit code 0]. Not restarting.
    echo =======================================================
    pause > nul
    exit /b 0
)

echo.
echo =======================================================
echo  Bot crashed with exit code %EXIT_CODE%.
echo  Restarting in %RESTART_DELAY% seconds...
echo  (Press Ctrl+C to cancel restart)
echo =======================================================

:: Wait before restart without using timeout redirection bug
ping 127.0.0.1 -n 31 > nul

goto start_loop
