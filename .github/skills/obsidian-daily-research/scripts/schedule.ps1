# Daily Research Pipeline — Windows Task Scheduler Setup
# Run this script as Administrator to register the scheduled task.

$wrapperPath = Join-Path $PSScriptRoot "run-scheduled.ps1"
$workingDir = (Get-Item $PSScriptRoot).Parent.Parent.Parent.Parent.FullName
$taskName = "DailyResearchPipeline"
$description = "Daily AI research pipeline - scans Reddit + X, writes to Obsidian vault"

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

$trigger = New-ScheduledTaskTrigger -Daily -At 1:00AM

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
        throw
    }
}

Write-Host ""
Write-Host "Done! Task '$taskName' is registered to run daily at 1:00 AM."
if ($principalUpdated) {
    Write-Host "It will wake the PC if needed, can run when you are not logged on, and writes logs to .github/skills/obsidian-daily-research/logs/."
}
else {
    Write-Warning "Task principal was not changed. Re-run this script elevated to enable background S4U execution."
    Write-Host "The task now uses the logging wrapper and updated wake/retry settings."
}
Write-Host ""
Write-Host "Verify: Get-ScheduledTask -TaskName '$taskName' | Format-List"
Write-Host "Test:   Start-ScheduledTask -TaskName '$taskName'"
Write-Host "Remove: Unregister-ScheduledTask -TaskName '$taskName'"
