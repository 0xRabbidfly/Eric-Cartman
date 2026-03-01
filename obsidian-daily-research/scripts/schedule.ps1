# Daily Research Pipeline — Windows Task Scheduler Setup
# Run this script as Administrator to register the scheduled task.

$scriptPath = Join-Path $PSScriptRoot "run.py"
$workingDir = (Get-Item $PSScriptRoot).Parent.Parent.Parent.FullName

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
Write-Host "Script:      $scriptPath"
Write-Host "Working dir: $workingDir"
Write-Host ""

# Create the scheduled task
$action = New-ScheduledTaskAction `
    -Execute $python `
    -Argument "`"$scriptPath`"" `
    -WorkingDirectory $workingDir

$trigger = New-ScheduledTaskTrigger -Daily -At 7:00AM

$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -DontStopOnIdleEnd `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 60) `
    -RestartCount 2 `
    -RestartInterval (New-TimeSpan -Minutes 5)

# Register (or update if exists)
$taskName = "DailyResearchPipeline"
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if ($existing) {
    Write-Host "Updating existing task '$taskName'..."
    Set-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings
} else {
    Write-Host "Creating new task '$taskName'..."
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description "Daily AI research pipeline - scans Reddit + X, writes to Obsidian vault"
}

Write-Host ""
Write-Host "Done! Task '$taskName' is registered to run daily at 7:00 AM."
Write-Host ""
Write-Host "Verify: Get-ScheduledTask -TaskName '$taskName' | Format-List"
Write-Host "Test:   Start-ScheduledTask -TaskName '$taskName'"
Write-Host "Remove: Unregister-ScheduledTask -TaskName '$taskName'"
