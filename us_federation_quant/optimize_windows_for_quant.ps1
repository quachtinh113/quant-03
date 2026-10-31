# =====================================================================
# US Federation Quant — Windows OS Institutional Optimization Script
# Run as Administrator to apply all low-latency & 24/7 reliability settings.
# =====================================================================

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  OPTIMIZING WINDOWS OS FOR 24/5 QUANT TRADING BOT" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

# 1. CẤU HÌNH NĂNG LƯỢNG (POWER & SLEEP - HIGH PERFORMANCE)
Write-Host "`n[1/4] Configuring Power & Sleep to Maximum Performance..." -ForegroundColor Yellow
try {
    # Activate High Performance Scheme (8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c)
    powercfg /setactive 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c
    
    # Disable Sleep / Standby timeout (AC & DC)
    powercfg /change standby-timeout-ac 0
    powercfg /change standby-timeout-dc 0
    
    # Disable Turn off Hard Disk timeout (AC & DC)
    powercfg /change disk-timeout-ac 0
    powercfg /change disk-timeout-dc 0
    
    # Disable Monitor Sleep (Optional, set to 0 to keep active or leave to user)
    powercfg /change monitor-timeout-ac 0
    
    # Disable Hibernation
    powercfg /hibernate off
    Write-Host "  ✅ Power Plan set to 'High Performance'. Sleep, Hibernation & Disk Off DISABLED." -ForegroundColor Green
} catch {
    Write-Host "  ⚠️ Powercfg notice: $_" -ForegroundColor DarkYellow
}

# 2. CHỐNG NGẮT KẾT NỐI CARD MẠNG (NETWORK ADAPTER POWER MANAGEMENT)
Write-Host "`n[2/4] Disabling Power Saving on Network Adapters..." -ForegroundColor Yellow
try {
    # Query physical network adapters
    $adapters = Get-NetAdapter | Where-Object { $_.HardwareInterface -eq $true }
    foreach ($adapter in $adapters) {
        $name = $adapter.Name
        Write-Host "  Configuring adapter: $name ($($adapter.InterfaceDescription))..."
        
        # Disable power saving via Registry / PnP properties
        $regPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}"
        $subKeys = Get-ChildItem -Path $regPath -ErrorAction SilentlyContinue
        foreach ($key in $subKeys) {
            $desc = (Get-ItemProperty -Path $key.PSPath -Name "DriverDesc" -ErrorAction SilentlyContinue).DriverDesc
            if ($desc -and $desc -eq $adapter.InterfaceDescription) {
                # PnPCapabilities: 24 (0x18) disables 'Allow the computer to turn off this device to save power'
                Set-ItemProperty -Path $key.PSPath -Name "PnPCapabilities" -Value 24 -Type DWord -Force -ErrorAction SilentlyContinue
                # Disable Green / Energy Efficient Ethernet if supported
                Set-ItemProperty -Path $key.PSPath -Name "*EEE" -Value 0 -Type String -Force -ErrorAction SilentlyContinue
                Write-Host "  ✅ Power management disabled for $name in Registry." -ForegroundColor Green
            }
        }
    }
} catch {
    Write-Host "  ⚠️ Network power management notice (requires Admin): $_" -ForegroundColor DarkYellow
}

# 3. KIỂM SOÁT WINDOWS UPDATE (CHỐNG TỰ ĐỘNG KHỞI ĐỘNG LẠI GIỮA PHIÊN)
Write-Host "`n[3/4] Configuring Windows Update Anti-Reboot Policies..." -ForegroundColor Yellow
try {
    $wuPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU"
    if (-not (Test-Path $wuPath)) {
        New-Item -Path $wuPath -Force | Out-Null
    }
    # NoAutoRebootWithLoggedOnUsers = 1 (Never auto-restart if a user is logged on)
    Set-ItemProperty -Path $wuPath -Name "NoAutoRebootWithLoggedOnUsers" -Value 1 -Type DWord -Force
    # AUOptions = 2 (Notify for download and notify for install - no surprise reboots)
    Set-ItemProperty -Path $wuPath -Name "AUOptions" -Value 2 -Type DWord -Force
    Write-Host "  ✅ Windows Update configured: 'No auto-restart with logged on users' ENABLED." -ForegroundColor Green
} catch {
    Write-Host "  ⚠️ Windows Update policy notice (requires Admin): $_" -ForegroundColor DarkYellow
}

# 4. TỰ PHỤC HỒI QUA STARTUP SHORTCUT & TASK SCHEDULER
Write-Host "`n[4/4] Ensuring Auto-Startup Watchdog is Active..." -ForegroundColor Yellow
$startupPath = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupPath "US_Federation_Quant.lnk"
if (Test-Path $shortcutPath) {
    Write-Host "  ✅ Auto-Startup Shortcut confirmed in Startup Folder: $shortcutPath" -ForegroundColor Green
} else {
    & powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Quant_03\us_federation_quant\create_startup_shortcut.ps1"
}

Write-Host "`n=======================================================" -ForegroundColor Cyan
Write-Host "  OPTIMIZATION COMPLETE! OS IS QUANT-READY 24/5" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan
