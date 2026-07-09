# healthcheck.ps1 - Remote Skills API watchdog
# Checks if the server is responding on port 3838.
# If not, logs the failure and restarts via start-service.bat.
# Designed to run as a scheduled task every 5 minutes.

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$LogFile   = Join-Path $ScriptDir "server.log"
$BatchFile = Join-Path $ScriptDir "start-service.bat"
$Url       = "http://127.0.0.1:3838/"
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

function Write-Log($msg) {
    Add-Content -Path $LogFile -Value "[$Timestamp] [Healthcheck] $msg"
}

# --- 1. Try HTTP health check ---
$healthy = $false
try {
    $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 10 -ErrorAction Stop
    if ($response.StatusCode -eq 200) {
        $healthy = $true
    } else {
        Write-Log "Non-200 status: $($response.StatusCode)"
    }
} catch {
    Write-Log "HTTP check failed: $($_.Exception.Message)"
}
if ($healthy) {
    # Server is fine - exit silently
    exit 0
}

# --- 2. Check if service is already starting ---
# Look for a cmd.exe window with the "Remote Skills API" title
$existing = Get-Process -Name "cmd" -ErrorAction SilentlyContinue |
    Where-Object { $_.MainWindowTitle -eq "Remote Skills API" }

if ($existing) {
    Write-Log "Server unhealthy but launcher process (PID $($existing.Id)) is already running -- skipping restart"
    exit 0
}

# Also check if node is running server.js (no window title match needed)
$nodeProcs = Get-Process -Name "node" -ErrorAction SilentlyContinue |
    Where-Object {
        try {
            $cmdLine = (Get-CimInstance Win32_Process -Filter "ProcessId=$($_.Id)" -ErrorAction SilentlyContinue).CommandLine
            $cmdLine -and $cmdLine -like "*remote-skills-api*server.js*"
        } catch { $false }
    }

if ($nodeProcs) {
    Write-Log "Server unhealthy but node process (PID $($nodeProcs[0].Id)) exists -- may be starting up. Skipping."
    exit 0
}

# --- 3. Restart the service ---
Write-Log "Server is DOWN -- launching start-service.bat"
Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$BatchFile`"" -WindowStyle Normal
Write-Log "Restart command issued"
exit 0
