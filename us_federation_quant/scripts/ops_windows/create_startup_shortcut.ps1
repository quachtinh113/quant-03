$wsh = New-Object -ComObject WScript.Shell
$startupPath = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupPath "US_Federation_Quant.lnk"

$sc = $wsh.CreateShortcut($shortcutPath)
$sc.TargetPath = "C:\Quant_03\us_federation_quant\start_bot.bat"
$sc.WorkingDirectory = "C:\Quant_03\us_federation_quant"
$sc.Description = "US Federation Quant Auto-Revival Watchdog"
if (Test-Path "C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe") {
    $sc.IconLocation = "C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe,0"
}
$sc.Save()

Write-Host "✅ Created Windows Startup Shortcut:" $shortcutPath -ForegroundColor Green
