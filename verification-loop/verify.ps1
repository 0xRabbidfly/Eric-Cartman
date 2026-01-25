<# 
.SYNOPSIS
    AI-HUB-Portal Verification Loop - Pre-PR Quality Gate
    
.DESCRIPTION
    Runs 7-phase verification against project constitution before PR creation.
    
.PARAMETER Phases
    Specific phases to run. Default: all phases.
    Valid values: Build, Types, Lint, Tests, Security, Hygiene, Diff
    
.PARAMETER Quick
    Run only Build, Types, Lint (faster iteration)
    
.PARAMETER Strict
    Fail on any warning (not just errors)
    
.EXAMPLE
    .\verify.ps1
    # Runs all phases
    
.EXAMPLE
    .\verify.ps1 -Quick
    # Runs Build, Types, Lint only
    
.EXAMPLE
    .\verify.ps1 -Phases Build,Tests
    # Runs only Build and Tests phases
#>

param(
    [ValidateSet('Build', 'Types', 'Lint', 'Tests', 'Security', 'Hygiene', 'Diff')]
    [string[]]$Phases = @('Build', 'Types', 'Lint', 'Tests', 'Security', 'Hygiene', 'Diff'),
    
    [switch]$Quick,
    
    [switch]$Strict
)

# Colors for output
$colors = @{
    Pass = 'Green'
    Fail = 'Red'
    Warn = 'Yellow'
    Info = 'Cyan'
    Header = 'Magenta'
}

# Results tracking
$results = @{
    Build = $null
    Types = $null
    Lint = $null
    Tests = $null
    Security = $null
    Hygiene = $null
    Diff = $null
}

$issues = @{
    P0 = @()  # Constitutional violations
    P1 = @()  # Type/Build errors
    P2 = @()  # Quality issues
}

# Quick mode overrides phases
if ($Quick) {
    $Phases = @('Build', 'Types', 'Lint')
}

function Write-Phase {
    param([string]$Name, [string]$Status, [string]$Details = "")
    
    $icon = switch ($Status) {
        'PASS' { '✅' }
        'FAIL' { '❌' }
        'WARN' { '⚠️' }
        'SKIP' { '⏭️' }
        default { '🔄' }
    }
    
    $color = switch ($Status) {
        'PASS' { $colors.Pass }
        'FAIL' { $colors.Fail }
        'WARN' { $colors.Warn }
        default { $colors.Info }
    }
    
    Write-Host "$icon " -NoNewline
    Write-Host "$Name`: " -NoNewline -ForegroundColor $colors.Header
    Write-Host "[$Status]" -ForegroundColor $color -NoNewline
    if ($Details) {
        Write-Host " $Details" -ForegroundColor Gray
    } else {
        Write-Host ""
    }
}

function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host "═" * 60 -ForegroundColor $colors.Header
    Write-Host " $Text" -ForegroundColor $colors.Header
    Write-Host "═" * 60 -ForegroundColor $colors.Header
}

# Navigate to project root
$projectRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
Push-Location $projectRoot

try {
    Write-Header "VERIFICATION LOOP - AI-HUB-Portal"
    Write-Host "Running phases: $($Phases -join ', ')" -ForegroundColor Gray
    Write-Host ""

    # ═══════════════════════════════════════════════════════════
    # PHASE 1: BUILD
    # ═══════════════════════════════════════════════════════════
    if ($Phases -contains 'Build') {
        Write-Host "`n🔨 Phase 1: Build Verification" -ForegroundColor $colors.Header
        
        $buildOutput = npm run build 2>&1
        $buildExitCode = $LASTEXITCODE
        
        if ($buildExitCode -eq 0) {
            $results.Build = 'PASS'
            Write-Phase "Build" "PASS"
        } else {
            $results.Build = 'FAIL'
            Write-Phase "Build" "FAIL" "Build failed - see output above"
            $issues.P1 += "Build failed"
            
            # Show last 20 lines of build output
            $buildOutput | Select-Object -Last 20 | ForEach-Object { Write-Host $_ -ForegroundColor Red }
            
            Write-Host "`n❌ Build failed. Cannot continue verification." -ForegroundColor Red
            exit 1
        }
    }

    # ═══════════════════════════════════════════════════════════
    # PHASE 2: TYPE CHECK
    # ═══════════════════════════════════════════════════════════
    if ($Phases -contains 'Types') {
        Write-Host "`n📘 Phase 2: Type Check" -ForegroundColor $colors.Header
        
        $typeOutput = npm run type-check 2>&1
        $typeExitCode = $LASTEXITCODE
        
        # Count errors
        $errorCount = ($typeOutput | Select-String -Pattern "error TS\d+" | Measure-Object).Count
        
        if ($typeExitCode -eq 0) {
            $results.Types = 'PASS'
            Write-Phase "Types" "PASS" "(0 errors)"
        } else {
            $results.Types = 'FAIL'
            Write-Phase "Types" "FAIL" "($errorCount errors)"
            $issues.P1 += "TypeScript errors: $errorCount"
            
            # Show first 30 lines of type errors
            $typeOutput | Select-Object -First 30 | ForEach-Object { Write-Host $_ -ForegroundColor Yellow }
        }
    }

    # ═══════════════════════════════════════════════════════════
    # PHASE 3: LINT CHECK
    # ═══════════════════════════════════════════════════════════
    if ($Phases -contains 'Lint') {
        Write-Host "`n🔍 Phase 3: Lint Check" -ForegroundColor $colors.Header
        
        $lintOutput = npm run lint 2>&1
        $lintExitCode = $LASTEXITCODE
        
        # Count warnings and errors
        $warningCount = ($lintOutput | Select-String -Pattern "warning" | Measure-Object).Count
        $lintErrorCount = ($lintOutput | Select-String -Pattern "error" | Measure-Object).Count
        
        if ($lintExitCode -eq 0) {
            $results.Lint = 'PASS'
            Write-Phase "Lint" "PASS" "($warningCount warnings)"
        } else {
            $results.Lint = 'FAIL'
            Write-Phase "Lint" "FAIL" "($lintErrorCount errors, $warningCount warnings)"
            $issues.P2 += "Lint issues: $lintErrorCount errors, $warningCount warnings"
            
            # Show first 30 lines
            $lintOutput | Select-Object -First 30 | ForEach-Object { Write-Host $_ -ForegroundColor Yellow }
        }
    }

    # ═══════════════════════════════════════════════════════════
    # PHASE 4: TESTS
    # ═══════════════════════════════════════════════════════════
    if ($Phases -contains 'Tests') {
        Write-Host "`n🧪 Phase 4: Test Suite" -ForegroundColor $colors.Header
        
        $testOutput = npm run test 2>&1
        $testExitCode = $LASTEXITCODE
        
        if ($testExitCode -eq 0) {
            $results.Tests = 'PASS'
            Write-Phase "Tests" "PASS"
        } else {
            $results.Tests = 'FAIL'
            Write-Phase "Tests" "FAIL"
            $issues.P1 += "Tests failed"
            
            # Show last 40 lines of test output
            $testOutput | Select-Object -Last 40 | ForEach-Object { Write-Host $_ -ForegroundColor Red }
        }
    }

    # ═══════════════════════════════════════════════════════════
    # PHASE 5: SECURITY SCAN (Constitutional)
    # ═══════════════════════════════════════════════════════════
    if ($Phases -contains 'Security') {
        Write-Host "`n🔒 Phase 5: Constitutional Security Scan" -ForegroundColor $colors.Header
        
        $securityIssues = @()
        
        # 5a. localStorage/sessionStorage (FORBIDDEN)
        $storageMatches = Get-ChildItem -Path "app", "components", "lib" -Recurse -Include "*.ts", "*.tsx" -ErrorAction SilentlyContinue | 
            Select-String -Pattern "localStorage|sessionStorage" -ErrorAction SilentlyContinue
        
        if ($storageMatches) {
            foreach ($match in $storageMatches | Select-Object -First 5) {
                $securityIssues += "localStorage/sessionStorage: $($match.Path):$($match.LineNumber)"
                $issues.P0 += "localStorage usage in $($match.Path):$($match.LineNumber)"
            }
        }
        
        # 5b. Hardcoded secrets
        $secretMatches = Get-ChildItem -Path "app", "components", "lib" -Recurse -Include "*.ts", "*.tsx" -ErrorAction SilentlyContinue | 
            Select-String -Pattern 'sk-[a-zA-Z0-9]+|api[_-]?key\s*[:=]\s*[''"][^''"]+|password\s*[:=]\s*[''"][^''"]+' -ErrorAction SilentlyContinue
        
        if ($secretMatches) {
            foreach ($match in $secretMatches | Select-Object -First 5) {
                $securityIssues += "Potential secret: $($match.Path):$($match.LineNumber)"
                $issues.P0 += "Hardcoded secret in $($match.Path):$($match.LineNumber)"
            }
        }
        
        # 5c. console.log (should use structured logger)
        $consoleMatches = Get-ChildItem -Path "app", "lib" -Recurse -Include "*.ts", "*.tsx" -ErrorAction SilentlyContinue | 
            Select-String -Pattern "console\.(log|error|warn|info)" -ErrorAction SilentlyContinue |
            Where-Object { $_.Path -notmatch "test|spec|\.test\.|\.spec\." }
        
        if ($consoleMatches) {
            foreach ($match in $consoleMatches | Select-Object -First 5) {
                $securityIssues += "console.* usage: $($match.Path):$($match.LineNumber)"
                $issues.P0 += "console.log in $($match.Path):$($match.LineNumber)"
            }
        }
        
        if ($securityIssues.Count -eq 0) {
            $results.Security = 'PASS'
            Write-Phase "Security" "PASS" "(0 constitutional violations)"
        } else {
            $results.Security = 'FAIL'
            Write-Phase "Security" "FAIL" "($($securityIssues.Count) constitutional violations)"
            
            foreach ($issue in $securityIssues) {
                Write-Host "  ❌ $issue" -ForegroundColor Red
            }
        }
    }

    # ═══════════════════════════════════════════════════════════
    # PHASE 6: HYGIENE
    # ═══════════════════════════════════════════════════════════
    if ($Phases -contains 'Hygiene') {
        Write-Host "`n🧹 Phase 6: Import & Style Hygiene" -ForegroundColor $colors.Header
        
        $hygieneIssues = @()
        
        # 6a. Relative imports (should use @/ alias)
        $relativeImports = Get-ChildItem -Path "app", "components" -Recurse -Include "*.ts", "*.tsx" -ErrorAction SilentlyContinue | 
            Select-String -Pattern "from\s+['""]\.\./" -ErrorAction SilentlyContinue
        
        if ($relativeImports) {
            foreach ($match in $relativeImports | Select-Object -First 5) {
                $hygieneIssues += "Relative import: $($match.Path):$($match.LineNumber)"
                $issues.P2 += "Relative import in $($match.Path):$($match.LineNumber)"
            }
        }
        
        # 6b. Hardcoded strings in JSX (i18n violation) - simplified check
        $hardcodedStrings = Get-ChildItem -Path "components", "app" -Recurse -Include "*.tsx" -ErrorAction SilentlyContinue | 
            Select-String -Pattern ">\s*[A-Z][a-z]{3,}\s+[a-z]+\s*<" -ErrorAction SilentlyContinue |
            Where-Object { $_.Line -notmatch "className|aria-|data-|href=" }
        
        if ($hardcodedStrings) {
            foreach ($match in $hardcodedStrings | Select-Object -First 3) {
                $hygieneIssues += "Possible hardcoded string: $($match.Path):$($match.LineNumber)"
                $issues.P2 += "Hardcoded string in $($match.Path):$($match.LineNumber)"
            }
        }
        
        if ($hygieneIssues.Count -eq 0) {
            $results.Hygiene = 'PASS'
            Write-Phase "Hygiene" "PASS" "(0 issues)"
        } else {
            $results.Hygiene = 'WARN'
            Write-Phase "Hygiene" "WARN" "($($hygieneIssues.Count) issues)"
            
            foreach ($issue in $hygieneIssues) {
                Write-Host "  ⚠️ $issue" -ForegroundColor Yellow
            }
        }
    }

    # ═══════════════════════════════════════════════════════════
    # PHASE 7: DIFF REVIEW
    # ═══════════════════════════════════════════════════════════
    if ($Phases -contains 'Diff') {
        Write-Host "`n📋 Phase 7: Git Diff Review" -ForegroundColor $colors.Header
        
        $diffStat = git diff --stat 2>&1
        $changedFiles = git diff --name-only 2>&1
        
        if ($changedFiles) {
            $fileCount = ($changedFiles | Measure-Object -Line).Lines
            $results.Diff = "$fileCount files"
            Write-Phase "Diff" "INFO" "($fileCount files changed)"
            
            Write-Host "`nChanged files:" -ForegroundColor Gray
            $changedFiles | ForEach-Object { Write-Host "  • $_" -ForegroundColor Gray }
        } else {
            $results.Diff = "0 files"
            Write-Phase "Diff" "INFO" "(no uncommitted changes)"
        }
    }

    # ═══════════════════════════════════════════════════════════
    # FINAL REPORT
    # ═══════════════════════════════════════════════════════════
    Write-Header "VERIFICATION REPORT"
    
    $allPassed = $true
    $hasP0 = $issues.P0.Count -gt 0
    $hasP1 = $issues.P1.Count -gt 0
    
    foreach ($phase in @('Build', 'Types', 'Lint', 'Tests', 'Security', 'Hygiene')) {
        if ($results[$phase]) {
            $status = $results[$phase]
            $color = switch ($status) {
                'PASS' { $colors.Pass }
                'FAIL' { $colors.Fail }
                'WARN' { $colors.Warn }
                default { $colors.Info }
            }
            
            if ($status -eq 'FAIL') { $allPassed = $false }
            
            Write-Host "  $phase`: " -NoNewline
            Write-Host "[$status]" -ForegroundColor $color
        }
    }
    
    if ($results.Diff) {
        Write-Host "  Diff: [$($results.Diff)]" -ForegroundColor Gray
    }
    
    Write-Host ""
    
    # Print issues by priority
    if ($issues.P0.Count -gt 0) {
        Write-Host "P0 - Constitutional Violations (MUST FIX):" -ForegroundColor Red
        $issues.P0 | ForEach-Object { Write-Host "  ❌ $_" -ForegroundColor Red }
        Write-Host ""
    }
    
    if ($issues.P1.Count -gt 0) {
        Write-Host "P1 - Type/Build Errors:" -ForegroundColor Yellow
        $issues.P1 | ForEach-Object { Write-Host "  ⚠️ $_" -ForegroundColor Yellow }
        Write-Host ""
    }
    
    if ($issues.P2.Count -gt 0) {
        Write-Host "P2 - Quality Issues:" -ForegroundColor Cyan
        $issues.P2 | ForEach-Object { Write-Host "  💡 $_" -ForegroundColor Cyan }
        Write-Host ""
    }
    
    # Overall status
    Write-Host "═" * 60 -ForegroundColor $colors.Header
    
    if ($hasP0) {
        Write-Host "❌ NOT READY for PR - Constitutional violations must be fixed" -ForegroundColor Red
        exit 1
    } elseif ($hasP1) {
        Write-Host "⚠️ NOT READY for PR - Type/build errors must be fixed" -ForegroundColor Yellow
        exit 1
    } elseif ($allPassed) {
        Write-Host "✅ READY for PR - All checks passed!" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "⚠️ READY for PR with warnings - Consider fixing P2 issues" -ForegroundColor Yellow
        exit 0
    }
    
} finally {
    Pop-Location
}
