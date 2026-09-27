# Weekly Brain — Windows Task Scheduler Setup
#
# Runs locally on Sundays. It used to be a Claude Desktop scheduled task; on
# 2026-09-24 Desktop moved it to a cloud routine, where api.x.ai is blocked and
# the vault's Windows paths don't exist, so the first cloud run wrote nothing.
# Run this script as Administrator to register the scheduled task.

$wrapperPath = Join-Path $PSScriptRoot "run-scheduled.ps1"
$workingDir = (Get-Item $PSScriptRoot).Parent.Parent.Parent.Parent.FullName
$taskName = "WeeklyBrain"
$description = "Weekly brain digest - analyzes the Obsidian vault, writes Research/Reports/weekly-brain-*.md and the weekly cost ledger"

# Find python
$python = Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
if (-not $python) {
    $python = Get-Command python3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
}
if (-not $python) {
    Write-Error "Python not found in PATH. Install Python 3.10+ first."
    exit 1
}

Write-Host "Python:      $python"
Write-Host "Wrapper:     $wrapperPath"
Write-Host "Working dir: $workingDir"
Write-Host ""

# Create the scheduled task
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$wrapperPath`" -PythonPath `"$python`"" `
    -WorkingDirectory $workingDir

$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 8:00AM

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -WakeToRun `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 5)

$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType S4U `
    -RunLevel Highest

$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Updating existing task '$taskName'..."
} else {
    Write-Host "Creating new task '$taskName'..."
}

$principalUpdated = $false

try {
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -Description $description `
        -Force `
        -ErrorAction Stop | Out-Null
    $principalUpdated = $true
}
catch {
    if ($existing) {
        Write-Warning "Could not update task principal (likely needs elevation): $($_.Exception.Message)"
        Write-Host "Falling back to updating action, trigger, and settings only..."
        Set-ScheduledTask `
            -TaskName $taskName `
            -Action $action `
            -Trigger $trigger `
            -Settings $settings `
            -ErrorAction Stop | Out-Null
    }
    else {
        # Not elevated: register for the current user, run while logged on.
        # Re-run this script elevated later to switch to S4U (runs logged off).
        Write-Warning "Could not register with S4U (likely needs elevation): $($_.Exception.Message)"
        Write-Host "Registering for the current user instead (runs while you are logged on)..."
        $userPrincipal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
        Register-ScheduledTask `
            -TaskName $taskName `
            -Action $action `
            -Trigger $trigger `
            -Settings $settings `
            -Principal $userPrincipal `
            -Description $description `
            -Force `
            -ErrorAction Stop | Out-Null
    }
}

Write-Host ""
Write-Host "Done! Task '$taskName' is registered to run Sundays at 8:00 AM."
if ($principalUpdated) {
    Write-Host "It will wake the PC if needed, can run when you are not logged on, and writes logs to .github/skills/obsidian-weekly-brain/logs/."
}
else {
    Write-Warning "Task principal was not changed. Re-run this script elevated to enable background S4U execution."
    Write-Host "The task now uses the logging wrapper and updated wake/retry settings."
}
Write-Host ""
Write-Host "Verify: Get-ScheduledTask -TaskName '$taskName' | Format-List"
Write-Host "Test:   Start-ScheduledTask -TaskName '$taskName'"
Write-Host "Remove: Unregister-ScheduledTask -TaskName '$taskName'"
