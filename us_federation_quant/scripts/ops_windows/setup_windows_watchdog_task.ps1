# =====================================================================
# US Federation Quant — Windows Task Scheduler Auto-Revival Setup Script
# Configures an institutional watchdog task that automatically launches
# the bot on Windows system startup and revives it if terminated.
# =====================================================================

param (
    [string]$TaskName = "US_Federation_Quant_Watchdog",
    [string]$BotPath = "C:\Quant_03\us_federation_quant\start_bot.bat"
)

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "  CONFIGURING WINDOWS TASK SCHEDULER WATCHDOG" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

if (-not (Test-Path $BotPath)) {
    Write-Host "❌ Error: Target script not found at '$BotPath'" -ForegroundColor Red
    exit 1
}

$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest
$Action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$BotPath`"" -WorkingDirectory (Split-Path $BotPath)
$TriggerStartup = New-ScheduledTaskTrigger -AtStartup
$TriggerLogon = New-ScheduledTaskTrigger -AtLogOn

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Days 0) `
    -RestartCount 999 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -Priority 4

# Unregister existing task if present
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "⚠️ Found existing task '$TaskName'. Replacing with updated config..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Principal $Principal `
    -Action $Action `
    -Trigger @($TriggerStartup, $TriggerLogon) `
    -Settings $Settings `
    -Description "US Federation Quant Institutional 24/7 Auto-Revival Watchdog" | Out-Null

Write-Host "✅ Scheduled Task '$TaskName' registered successfully!" -ForegroundColor Green
Write-Host "   - Triggers: At System Startup & At User Logon" -ForegroundColor Green
Write-Host "   - Target Action: $BotPath" -ForegroundColor Green
Write-Host "   - Auto-Revival: Restarts every 1 minute if terminated" -ForegroundColor Green
Write-Host "=======================================================" -ForegroundColor Cyan
