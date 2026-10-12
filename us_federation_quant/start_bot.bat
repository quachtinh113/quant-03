@echo off
title US_Federation_Quant
color 0A

echo =======================================================
echo          US_Federation_Quant...
echo =======================================================
echo.

:: Ensure we are in the correct directory
cd /d "%~dp0"

:: Set utf-8 encoding for proper emoji display
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
:: Start MT5 GUI explicitly if not already visible
start "" "C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"
timeout /t 3 /nobreak > nul

:: Run the bot
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

:: Wait before restart (allows user to cancel)
timeout /t %RESTART_DELAY% /nobreak

goto start_loop
