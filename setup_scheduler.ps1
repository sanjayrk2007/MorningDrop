# ============================================================
# setup_scheduler.ps1
# Run this ONCE as Administrator to schedule The Morning Drop
# at 7:00 AM every day.
# ============================================================

$TaskName    = "MorningDropNewsBot"
$BatFile     = "C:\Users\rksan_amz5yv3\morning-bot\run_morning_drop.bat"
$TriggerTime = "07:00"

# Remove existing task if it exists (for re-runs / updates)
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# Build the trigger: daily at 7:00 AM
$trigger = New-ScheduledTaskTrigger -Daily -At $TriggerTime

# Build the action: run the batch file directly
$action = New-ScheduledTaskAction -Execute $BatFile

# Settings: run even if on battery, wake the PC if sleeping, restart on failure
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 5) `
    -StartWhenAvailable `
    -WakeToRun `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

# Register the task to run as the current user (S4U runs whether logged in or not)
$principal = New-ScheduledTaskPrincipal `
    -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) `
    -LogonType S4U `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Trigger $trigger `
    -Action $action `
    -Settings $settings `
    -Principal $principal `
    -Description "The Morning Drop: Automated daily news email at 7 AM." `
    -Force

Write-Host ""
Write-Host "✅ Task '$TaskName' registered successfully!" -ForegroundColor Green
Write-Host "   Runs daily at $TriggerTime" -ForegroundColor Cyan
Write-Host "   Logs saved to: C:\Users\rksan_amz5yv3\morning-bot\logs\" -ForegroundColor Cyan
Write-Host ""
Write-Host "To verify, open Task Scheduler and look for '$TaskName'."
Write-Host "To test right now: schtasks /run /tn `"$TaskName`""
