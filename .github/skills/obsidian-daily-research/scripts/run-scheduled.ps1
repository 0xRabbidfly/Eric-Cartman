param(
    [string]$PythonPath,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RunArgs
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$skillDir = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $scriptDir))
$runScript = Join-Path $scriptDir 'run.py'
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
$logFile = Join-Path $logsDir ("daily-research-$timestamp.log")
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

@(
    "[$(Get-Date -Format 'o')] Starting DailyResearchPipeline",
    "Python: $resolvedPython",
    "Script: $resolvedRunScript",
    "Repo:   $repoRoot",
    "Args:   $($RunArgs -join ' ')"
) | Out-File -FilePath $logFile -Encoding utf8

Push-Location $repoRoot
try {
    & $resolvedPython $resolvedRunScript @RunArgs 2>&1 |
        ForEach-Object {
            $line = $_.ToString()
            $asciiLine = Convert-ToAsciiSafe -Text $line
            $asciiLine
        } |
        Tee-Object -FilePath $logFile -Append
    $exitCode = if ($null -ne $LASTEXITCODE) { $LASTEXITCODE } else { 0 }
    "[$(Get-Date -Format 'o')] ExitCode: $exitCode" | Out-File -FilePath $logFile -Encoding utf8 -Append
    exit $exitCode
}
catch {
    "[$(Get-Date -Format 'o')] PowerShell wrapper failure: $($_ | Out-String)" | Out-File -FilePath $logFile -Encoding utf8 -Append
    throw
}
finally {
    Pop-Location
}