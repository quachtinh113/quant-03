@echo off
title US_Federation_Quant [Auto-Revival Watchdog]
color 0A

echo =======================================================
echo     US_Federation_Quant -- AUTO-REVIVAL WATCHDOG
echo =======================================================
echo.

:: Ensure we are in the correct directory
cd /d "%~dp0"

:: Set utf-8 encoding for proper emoji and terminal display
chcp 65001 > nul
set PYTHONIOENCODING=utf-8

set /a RESTART_COUNT=0
set RESTART_DELAY=5

:start_loop
set /a RESTART_COUNT+=1

echo.
echo =======================================================
echo  [STEP 1/2] Kiem tra va Hoi sinh MT5 GUI Process...
echo =======================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "ensure_mt5_gui.ps1"
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] ensure_mt5_gui returned non-zero code. Attempting to proceed...
)

echo.
echo =======================================================
echo  [STEP 2/2] Kich hoat US Federation Live Runner...
echo  (Chu ky khoi chay #%RESTART_COUNT% luc %TIME%)
echo =======================================================
python live_federation_runner.py

:: Check exit code
set EXIT_CODE=%ERRORLEVEL%

echo.
echo =======================================================
if %EXIT_CODE% EQU 99 (
    echo  [BAO DONG DO] Nuclear Football da kich hoat!
    echo  Danh muc da duoc thanh ly ve 100%% Tien mat de bao toan von.
    echo  Bot tam dung tu dong de ban kiem tra tai khoan.
    echo =======================================================
    pause > nul
    exit /b 99
)

if %EXIT_CODE% EQU 0 (
    echo  [THONG BAO] Bot vua ket thuc mot chu ky [exit code 0].
    echo  [TU DONG KHOI PHUC] Se tu kich hoat lai sau %RESTART_DELAY% giay...
) else (
    echo  [CANH BAO] Bot bi vang san / loi he thong [exit code %EXIT_CODE%].
    echo  [TU DONG KHOI PHUC] Dang kich hoat lai MT5 GUI va Bot sau %RESTART_DELAY% giay...
)
echo  (Nhan Ctrl+C bat cu luc nao neu ban muon dung bot hoan toan)
echo =======================================================

:: Wait 5 seconds before immediate restart
ping 127.0.0.1 -n 6 > nul

goto start_loop
