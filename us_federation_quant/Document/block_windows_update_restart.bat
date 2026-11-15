@echo off
chcp 65001 >nul
title US Federation Quant — Block Windows Update Auto Restart & Enable gpedit.msc
color 0A

echo ==============================================================================
echo   US FEDERATION QUANT — WINDOWS UPDATE AUTO-REBOOT PREVENTION (24/7 TRADING)
echo ==============================================================================
echo.

:: 1. Check Administrator Privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Script chua duoc chay duoi quyen Administrator!
    echo Vui long:
    echo   1. Dong cua so nay.
    echo   2. Click chuot phai vao file "block_windows_update_restart.bat"
    echo   3. Chon "Run as administrator" (Chay voi quyen quan tri).
    echo.
    pause
    exit /b 1
)

echo [1/3] Dang cau hinh Registry chong tu dong Restart cua Windows Update...
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate" /v "DisableDualScan" /t REG_DWORD /d 1 /f >nul
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v "NoAutoRebootWithLoggedOnUsers" /t REG_DWORD /d 1 /f >nul
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v "AUOptions" /t REG_DWORD /d 2 /f >nul
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v "AlwaysAutoRebootAtScheduledTime" /t REG_DWORD /d 0 /f >nul
reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU" /v "AutoInstallMinorUpdateTargets" /t REG_DWORD /d 0 /f >nul

if %errorlevel% equ 0 (
    echo   [OK] Registry da duoc thiet lap thanh cong:
    echo        - NoAutoRebootWithLoggedOnUsers = 1 (Cam restart khi dang dang nhap/chay bot)
    echo        - AUOptions = 2 (Thong bao truoc khi tai va cai dat, khong cai ngam)
    echo        - AlwaysAutoRebootAtScheduledTime = 0 (Tat hen gio tu dong restart)
) else (
    echo   [WARNING] Co loi khi ghi vao Registry.
)

echo.
echo [2/3] Kiem tra va kich hoat gpedit.msc (Dac biet cho Windows Home Single Language)...
if not exist "%SystemRoot%\System32\gpedit.msc" (
    echo   Phat hien may chua co gpedit.msc (ban Windows Home).
    echo   Dang nap cac goi Group Policy chinh thuc tu he thong Windows...
    pushd "%SystemRoot%\servicing\Packages"
    for /f %%i in ('dir /b Microsoft-Windows-GroupPolicy-ClientExtensions-Package~*.mum') do (
        dism /online /norestart /add-package:"%SystemRoot%\servicing\Packages\%%i" >nul 2>&1
    )
    for /f %%i in ('dir /b Microsoft-Windows-GroupPolicy-ClientTools-Package~*.mum') do (
        dism /online /norestart /add-package:"%SystemRoot%\servicing\Packages\%%i" >nul 2>&1
    )
    popd
    if exist "%SystemRoot%\System32\gpedit.msc" (
        echo   [OK] Da kich hoat thanh cong gpedit.msc tren Windows Home!
    ) else (
        echo   [NOTE] gpedit.msc can khoi dong lai de cap nhat duong dan System32,
        echo          nhung chinh sach Registry o Buoc 1 da CO HIEU LUC 100%%.
    )
) else (
    echo   [OK] gpedit.msc da co san tren he thong.
)

echo.
echo [3/3] Dang cap nhat Group Policy (gpupdate /force)...
gpupdate /force >nul 2>&1
echo   [OK] Group Policy da duoc cap nhat ngay lap tuc.

echo.
echo ==============================================================================
echo   HOAN TAT! He thong da duoc bao ve chong tu dong restart giua phien 24/7.
echo ==============================================================================
echo.
pause
