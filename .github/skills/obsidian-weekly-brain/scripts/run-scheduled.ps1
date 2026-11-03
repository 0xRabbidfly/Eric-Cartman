# Weekly Brain - logging wrapper for the scheduled task (see schedule.ps1).
# Same shape as obsidian-daily-research's wrapper: each run writes
# logs/weekly-brain-<timestamp>.log, including the run's cost line.
param(
    [string]$PythonPath,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RunArgs
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillDir = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $scriptDir))
$runScript = Join-Path $scriptDir 'brain.py'
$logsDir = Join-Path $skillDir 'logs'

if (-not $PythonPath) {
    $PythonPath = Get-Command python -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
}
if (-not $PythonPath) {
    $PythonPath = Get-Command python3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
}
if (-not $PythonPath) {
    throw 'Python not found in PATH. Install Python 3.10+ first.'
}

New-Item -ItemType Directory -Path $logsDir -Force | Out-Null

$timestamp = Get-Date -Format 'yyyy-MM-dd_HHmmss'
$logFile = Join-Path $logsDir ("weekly-brain-$timestamp.log")
$resolvedPython = (Resolve-Path $PythonPath).Path
$resolvedRunScript = (Resolve-Path $runScript).Path

# Normalize console output to ASCII-safe text so PowerShell terminals do not
# show mojibake for symbols like arrows/hearts.
function Convert-ToAsciiSafe {
    param([string]$Text)

    if ($null -eq $Text) {
        return ''
    }

    $normalized = $Text
    $normalized = $normalized.Replace([string][char]0x2192, '->')
    $normalized = $normalized.Replace([string][char]0x2014, '-')
    $normalized = $normalized.Replace([string][char]0x2013, '-')
    $normalized = $normalized.Replace([string][char]0x2026, '...')
    $normalized = $normalized.Replace([string][char]0x2019, "'")
    $normalized = $normalized.Replace([string][char]0x201C, '"')
    $normalized = $normalized.Replace([string][char]0x201D, '"')
    $normalized = $normalized.Replace([string][char]0x2764, '<3')
    $normalized = $normalized.Replace([string][char]0xFE0F, '')

    # Replace any remaining non-ASCII chars to keep output stable.
    return ($normalized -replace '[^\u0009\u000A\u000D\u0020-\u007E]', '?')
}

# Who started us. Some Sundays get a second run ~3 minutes into the first,
# with nothing in Task Scheduler to explain it; this names the launcher.
function Get-Launcher {
    try {
        $self = Get-CimInstance Win32_Process -Filter "ProcessId=$PID"
        $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$($self.ParentProcessId)"
        if ($parent) { return "$($parent.Name) (pid $($parent.ProcessId)): $($parent.CommandLine)" }
        return "pid $($self.ParentProcessId) (exited)"
    }
    catch {
        return "unknown ($($_.Exception.Message))"
    }
}

# Out-File/Add-Content with -Encoding utf8 on every write. Tee-Object -Append
# on Windows PowerShell 5.1 writes UTF-16, which is what spaced out old logs.
function Write-Log {
    param([string]$Text)
    Add-Content -Path $logFile -Value $Text -Encoding utf8
}

@(
    "[$(Get-Date -Format 'o')] Starting WeeklyBrain",
    "Launcher: $(Get-Launcher)",
    "Python: $resolvedPython",
    "Script: $resolvedRunScript",
    "Repo:   $repoRoot",
    "Args:   $($RunArgs -join ' ')"
) | Out-File -FilePath $logFile -Encoding utf8

# One run at a time: a second copy started while one is going would rewrite
# the same report and ledger row.
$mutex = New-Object System.Threading.Mutex($false, 'Global\EricCartman-WeeklyBrain')
$haveLock = $false
try {
    $haveLock = $mutex.WaitOne(0)
}
catch [System.Threading.AbandonedMutexException] {
    $haveLock = $true
}
if (-not $haveLock) {
    Write-Log "[$(Get-Date -Format 'o')] Another WeeklyBrain run holds the lock; exiting without running."
    $mutex.Dispose()
    exit 0
}

# Python writes UTF-8 and PowerShell reads it as UTF-8, so em dashes and
# arrows reach Convert-ToAsciiSafe intact instead of arriving as '?'.
$env:PYTHONIOENCODING = 'utf-8'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Push-Location $repoRoot
try {
    # Stderr lines arrive as error records; under 'Stop' the first one would
    # abort the wrapper while Python keeps running.
    $ErrorActionPreference = 'Continue'
    & $resolvedPython $resolvedRunScript @RunArgs 2>&1 |
        ForEach-Object {
            $asciiLine = Convert-ToAsciiSafe -Text $_.ToString()
            Write-Log $asciiLine
            $asciiLine
        }
    $exitCode = if ($null -ne $LASTEXITCODE) { $LASTEXITCODE } else { 0 }
    Write-Log "[$(Get-Date -Format 'o')] ExitCode: $exitCode"
    exit $exitCode
}
catch {
    Write-Log "[$(Get-Date -Format 'o')] PowerShell wrapper failure: $($_ | Out-String)"
    throw
}
finally {
    Pop-Location
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}