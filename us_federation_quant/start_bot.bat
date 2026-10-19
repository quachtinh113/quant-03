@echo off
title US_Federation_Quant [Auto-Revival Watchdog]
color 0A

echo =======================================================
echo     US_Federation_Quant — AUTO-REVIVAL WATCHDOG
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
echo  [STEP 1/2] Kiểm tra & Hồi sinh MT5 GUI Process...
echo =======================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "ensure_mt5_gui.ps1"
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] ensure_mt5_gui returned non-zero code. Attempting to proceed...
)

echo.
echo =======================================================
echo  [STEP 2/2] Kích hoạt US Federation Live Runner...
echo  (Chu kỳ khởi chạy #%RESTART_COUNT% lúc %TIME%)
echo =======================================================
python live_federation_runner.py

:: Check exit code
set EXIT_CODE=%ERRORLEVEL%

echo.
echo =======================================================
if %EXIT_CODE% EQU 99 (
    echo  🚨 [BÁO ĐỘNG ĐỎ] Nuclear Football đã kích hoạt!
    echo  Danh mục đã được thanh lý về 100%% Tiền mặt để bảo toàn vốn.
    echo  Bot tạm dừng tự động để bạn kiểm tra tài khoản.
    echo =======================================================
    pause > nul
    exit /b 99
)

if %EXIT_CODE% EQU 0 (
    echo  [THÔNG BÁO] Bot vừa kết thúc một chu kỳ [exit code 0].
    echo  🚀 [TỰ ĐỘNG KHÔI PHỤC] Sẽ tự kích hoạt lại sau %RESTART_DELAY% giây...
) else (
    echo  ⚠️ [CẢNH BÁO] Bot bị văng sàn / lỗi hệ thống [exit code %EXIT_CODE%].
    echo  🚀 [TỰ ĐỘNG KHÔI PHỤC] Đang kích hoạt lại MT5 GUI và Bot sau %RESTART_DELAY% giây...
)
echo  (Nhấn Ctrl+C bất cứ lúc nào nếu bạn muốn dừng bot hoàn toàn)
echo =======================================================

:: Wait 5 seconds before immediate restart
ping 127.0.0.1 -n 6 > nul

goto start_loop
