# setup-resilience.ps1 — Create scheduled task + startup shortcut
# Run once to set up resilience infrastructure.

$ScriptDir = "Z:\Projects\Eric-Cartman\.github\skills\remote-skills-api"
$HealthcheckPath = Join-Path $ScriptDir "healthcheck.ps1"
$BatchPath = Join-Path $ScriptDir "start-service.bat"
$StartupDir = "C:\Users\nuno_\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup"

# --- 1. Create Scheduled Task via XML ---
Write-Host "Creating scheduled task..."

$taskXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.3" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Checks Remote Skills API health every 5 minutes and restarts if down</Description>
  </RegistrationInfo>
  <Triggers>
    <TimeTrigger>
      <Repetition>
        <Interval>PT1H</Interval>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
      <StartBoundary>2025-01-01T00:00:00</StartBoundary>
      <Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>RABBIDFLY-PC\nuno_</UserId>
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>false</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <ExecutionTimeLimit>PT1M</ExecutionTimeLimit>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>powershell.exe</Command>
      <Arguments>-ExecutionPolicy Bypass -WindowStyle Hidden -File "$HealthcheckPath"</Arguments>
    </Exec>
  </Actions>
</Task>
"@

$xmlPath = Join-Path $env:TEMP "remote-skills-healthcheck-task.xml"
$taskXml | Out-File -FilePath $xmlPath -Encoding Unicode

try {
    schtasks /create /tn "Remote Skills API Healthcheck" /xml $xmlPath /f
    Write-Host "Scheduled task created successfully"
} catch {
    Write-Host "ERROR creating scheduled task: $_"
}
Remove-Item $xmlPath -ErrorAction SilentlyContinue

# --- 2. Create Startup Shortcut ---
Write-Host "Creating startup shortcut..."

try {
    $ws = New-Object -ComObject WScript.Shell
    $shortcutPath = Join-Path $StartupDir "Remote Skills API.lnk"
    $sc = $ws.CreateShortcut($shortcutPath)
    $sc.TargetPath = $BatchPath
    $sc.WorkingDirectory = $ScriptDir
    $sc.Description = "Auto-start Remote Skills API server"
    $sc.Save()
    Write-Host "Startup shortcut created at: $shortcutPath"
} catch {
    Write-Host "ERROR creating shortcut: $_"
}

Write-Host "Done! Resilience setup complete."

