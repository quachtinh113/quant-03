@echo off
title US Federation Quant — OS Optimization [Run as Admin]
color 0B

echo =======================================================
echo   US Federation Quant — OS Optimization (Admin)
echo =======================================================
echo.

:: Check for Administrative privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Script is NOT running as Administrator!
    echo Right-click this file and select "Run as administrator".
    echo.
    pause
    exit /b 1
)

cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "optimize_windows_for_quant.ps1"

echo.
echo =======================================================
echo   Optimization completed!
echo =======================================================
pause
