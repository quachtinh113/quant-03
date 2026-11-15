# ==============================================================================
# ensure_mt5_gui.ps1
# Ensures MetaTrader 5 GUI is running with a valid graphical window handle (HWND).
# Kills any orphaned headless / background terminal64 instances.
# ==============================================================================

param (
    [string]$TerminalPath = "C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe",
    [string]$WorkingDirectory = "C:\Program Files\MetaTrader 5 EXNESS",
    [int]$MaxWaitSeconds = 15
)

$ErrorActionPreference = "SilentlyContinue"

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  MT5 PROCESS LIFECYCLE & GUI VALIDATOR" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

# 1. Inspect existing terminal64 processes
$existingProcs = Get-Process -Name terminal64 -ErrorAction SilentlyContinue

$headlessCount = 0
foreach ($p in $existingProcs) {
    if ($p.MainWindowHandle -eq 0) {
        Write-Host "⚠️ Found headless / hidden terminal64 (PID: $($p.Id)). Terminating to clear mutex..." -ForegroundColor Yellow
        Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
        $headlessCount++
    }
}

if ($headlessCount -gt 0) {
    Start-Sleep -Seconds 1
}

# 2. Check if a valid GUI instance is already running
$guiProcs = Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 }

if ($guiProcs) {
    $firstGui = $guiProcs[0]
    Write-Host "✅ MT5 GUI is already active (PID: $($firstGui.Id), HWND: $($firstGui.MainWindowHandle), Title: '$($firstGui.MainWindowTitle)')" -ForegroundColor Green
    exit 0
}

# 3. Launch MT5 GUI
if (-not (Test-Path $TerminalPath)) {
    Write-Host "❌ ERROR: Terminal executable not found at '$TerminalPath'" -ForegroundColor Red
    exit 1
}

Write-Host "🚀 Launching MT5 GUI: '$TerminalPath'..." -ForegroundColor Cyan
Start-Process -FilePath $TerminalPath -WorkingDirectory $WorkingDirectory

# 4. Wait for GUI window to initialize
$waited = 0
$foundGui = $false

while ($waited -lt $MaxWaitSeconds) {
    Start-Sleep -Seconds 1
    $waited++
    
    $checkProcs = Get-Process -Name terminal64 -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 }
    if ($checkProcs) {
        $guiInstance = $checkProcs[0]
        Write-Host "✅ MT5 GUI ready after $waited s (PID: $($guiInstance.Id), HWND: $($guiInstance.MainWindowHandle), Title: '$($guiInstance.MainWindowTitle)')" -ForegroundColor Green
        $foundGui = $true
        break
    }
}

if (-not $foundGui) {
    $anyProc = Get-Process -Name terminal64 -ErrorAction SilentlyContinue
    if ($anyProc) {
        Write-Host "⚠️ MT5 running (PID: $($anyProc[0].Id)) but MainWindowHandle not yet registered. Continuing..." -ForegroundColor Yellow
    } else {
        Write-Host "❌ Failed to start MT5 process." -ForegroundColor Red
        exit 1
    }
}

Write-Host "=======================================================" -ForegroundColor Cyan
exit 0
