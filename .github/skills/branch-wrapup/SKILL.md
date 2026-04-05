---
name: branch-wrapup
description: Pre-PR quality gate that runs build, type-check, lint, test, security scans, and finishes with a conventional commit. Use before creating a PR, after completing features, or when wrapping up a branch.
user-invocable: true
disable-model-invocation: true
metadata:
  author: 0xrabbidfly
  version: "1.0.0"
---

# Branch Wrapup Skill

## Purpose

Run a comprehensive 10-phase verification and commit workflow before code is considered "ready" for pull request. Catches issues locally before they reach CI/CD, ensures constitutional compliance, runs an OWASP Top 10 security scan, performs an obvious code-smell review, and closes with a proper conventional commit summarizing all branch changes.

## When to Use

- Before creating a pull request
- After completing a feature or significant refactoring
- After merging main into your branch
- When you want to ensure all quality gates pass
- As a final check before deployment

---

## Quick Start

```
Run branch-wrapup before I create a PR.
```

Or invoke specific phases:

```
Run only the security scan phase of branch-wrapup.
```

---

## Verification Phases

### Phase 1: Build Verification

```powershell
npm run build 2>&1 | Select-Object -Last 30
```

**Must pass to continue.** Build failure = stop immediately.

**What it catches:**
- Broken imports
- Syntax errors
- Missing dependencies
- Next.js compilation issues

---

### Phase 2: Type Check

```powershell
npm run type-check 2>&1 | Select-Object -First 40
```

**Report all errors. Fix critical ones before continuing.**

**What it catches:**
- Type mismatches
- Missing properties on interfaces
- `any` type leaks (forbidden per constitution)
- Incorrect return types

---

### Phase 3: Lint Check

```powershell
npm run lint 2>&1 | Select-Object -First 40
```

**What it catches:**
- ESLint rule violations
- Unused variables/imports
- Code style issues
- React hooks violations

---

### Phase 4: Test Suite

```powershell
npm run test 2>&1 | Select-Object -Last 50
```

**Target: 80% coverage minimum.**

**Report:**
- Total tests: X
- Passed: X
- Failed: X
- Coverage: X%

---

### Phase 5: Constitutional Security Scan

Project-specific security checks based on [copilot-instructions.md](../../copilot-instructions.md):

```powershell
# 1. Check for forbidden localStorage/sessionStorage
Select-String -Path "app/**/*.ts","app/**/*.tsx","components/**/*.tsx","lib/**/*.ts" -Pattern "localStorage|sessionStorage" -Recurse | Select-Object -First 10

# 2. Check for exposed secrets
Select-String -Path "**/*.ts","**/*.tsx" -Pattern "sk-|api_key|password\s*=\s*['""]" -Recurse | Select-Object -First 10

# 3. Check for console.log in production code (should use structured logger)
Select-String -Path "app/**/*.ts","app/**/*.tsx","lib/**/*.ts" -Pattern "console\.(log|error|warn)" -Recurse | Select-Object -First 10

# 4. Check for hardcoded English strings (i18n violation)
Select-String -Path "components/**/*.tsx","app/**/*.tsx" -Pattern "<(h[1-6]|p|span|button|label)>[A-Z][a-z]+" -Recurse | Select-Object -First 10
```

**Constitutional violations (must fix):**
- ❌ `localStorage` / `sessionStorage` usage
- ❌ Hardcoded secrets or API keys
- ❌ `console.log` in production code
- ❌ Hardcoded English text (should use `useTranslations`)

---

### Phase 6: OWASP Security Review

**Composable skill call** — invoke the `owasp-security-review` skill to run a quick-scan against the OWASP Top 10:2025 checklist. The skill is tuned for React/TypeScript + Azure AD (Entra ID) + Azure App Service.

See: `.github/skills/owasp-security-review/SKILL.md`

**Gate behavior:**
- If the scan returns **FAIL** (any HIGH-severity finding): **stop the pipeline immediately.** Do not proceed to Phase 7. Report all findings to terminal.
- If the scan returns **PASS** (no HIGH findings): continue. MEDIUM and LOW findings are reported in the terminal and included in the verification report, but do not block.

**What it catches:**
- Broken access control (wildcard CORS, missing auth middleware, IDOR)
- Security misconfiguration (missing CSP, source maps in prod, HTTPS disabled)
- Supply chain risks (missing lockfile, `npm install` in CI)
- Cryptographic failures (secrets in code, tokens in localStorage)
- Injection escape hatches (`dangerouslySetInnerHTML`, `eval()`, `.innerHTML`)
- Auth failures (permissive tenant, implicit flow, missing token validation)
- Azure App Service misconfig (remote debugging, FTP, TLS version)

---

### Phase 7: Import & Style Hygiene

```powershell
# 1. Check for relative imports (should use @/ alias)
Select-String -Path "app/**/*.ts","app/**/*.tsx","components/**/*.tsx" -Pattern 'from\s+[''"]\.\./' -Recurse | Select-Object -First 10

# 2. Check for inline styles with magic numbers
Select-String -Path "components/**/*.tsx" -Pattern 'style=\{\{.*\d+.*\}\}' -Recurse | Select-Object -First 10

# 3. Check for missing ARIA labels on interactive elements
Select-String -Path "components/**/*.tsx" -Pattern '<(button|a|input)[^>]*(?<!aria-label)[^>]*>' -Recurse | Select-Object -First 5

# 4. Check stale .gitignore entries (paths that no longer exist)
Get-Content .gitignore | Where-Object { $_ -match '^[^#\s]' -and $_ -notmatch '[\*\?]' } |
  ForEach-Object { $p = $_.TrimEnd('/'); if (-not (Test-Path $p)) { "Stale: $_" } }

# 5. Check orphan scripts (scripts/ files not referenced in package.json)
$pkgJson = Get-Content package.json -Raw
Get-ChildItem scripts/*.ts | Where-Object { $pkgJson -notmatch $_.Name } |
  ForEach-Object { "Orphan: scripts/$($_.Name)" }
```

**Additional hygiene checks:**
- ⚠️ Stale `.gitignore` entries for deleted paths (vestigial clutter)
- ⚠️ Orphan scripts not wired into `package.json` (dev artifacts that should be deleted)

---

### Phase 8: Git Diff Review

```powershell
# Show what changed
git diff --stat

# List changed files
git diff HEAD~1 --name-only 2>$null || git diff --cached --name-only
```

**Review each changed file for:**
- Unintended changes
- Missing error handling
- Potential edge cases
- Files that shouldn't have been modified

---

### Phase 9: Code Smell Review (Obvious Smells)

Perform a quick static review for obvious refactoring opportunities and track them.

```powershell
# 1. Scan for obvious P0 smells (blockers)
Select-String -Path "app/**/*.ts","app/**/*.tsx","components/**/*.ts","components/**/*.tsx","lib/**/*.ts","lib/**/*.tsx" -Pattern "\beval\s*\(|\bnew\s+Function\s*\(" -Recurse

# 2. Scan for obvious refactoring opportunities
Select-String -Path "**/*.{ts,tsx,js,jsx}" -Pattern "TODO|FIXME|HACK|\?.*\?.*:" -Recurse | Select-Object -First 50

# 3. Write or refresh code smell tracker
# Output file: code-smells.md
```

**Gate behavior:**
- If any `P0` smell is found, **stop immediately**.
- If no `P0` smell is found, write refactoring opportunities to `code-smells.md`.

**`code-smells.md` must include:**
- Refactoring opportunities list (file + line)
- 1–2 creative feature ideas to keep momentum

---

### Phase 10: Commit

Only runs if all blocking phases passed. Stages all changes and creates a conventional commit summarizing the branch work.

```powershell
# Stage all changes
git add -A

# Generate commit message from branch diff
$branch = git rev-parse --abbrev-ref HEAD
$diffSummary = git diff --cached --stat
$filesChanged = git diff --cached --name-only

# Commit with conventional message
# Format: <type>(scope): summary of changes
# Body: list of changed files grouped by area
git commit -m "<type>(scope): <summary>" -m "<body with file list>"
```

**Commit message rules:**
- Use conventional commit format: `type(scope): description`
- Type from: `feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `style`
- Scope = primary area changed (e.g., `auth`, `search`, `infra`)
- Body lists key changes, not every file
- If branch name contains a ticket ID, include it

---

## Output Format

After running all phases, produce this verification report:

```
╔══════════════════════════════════════════════════════════════╗
║                    VERIFICATION REPORT                        ║
╠══════════════════════════════════════════════════════════════╣
║                                                               ║
║  Build:      [PASS/FAIL]                                     ║
║  Types:      [PASS/FAIL] (X errors)                          ║
║  Lint:       [PASS/FAIL] (X warnings, Y errors)              ║
║  Tests:      [PASS/FAIL] (X/Y passed, Z% coverage)           ║
║  Security:   [PASS/FAIL] (X constitutional violations)       ║
║  OWASP:      [PASS/FAIL] (X HIGH, Y MED, Z LOW)             ║
║  Hygiene:    [PASS/FAIL] (X issues)                          ║
║  Diff:       X files changed                                 ║
║  Smells:     [PASS/FAIL] (X P0, Y refactor opportunities)    ║
║  Commit:     [DONE / SKIPPED]                                ║
║                                                               ║
╠══════════════════════════════════════════════════════════════╣
║  Overall:    [COMMITTED / NOT READY] for PR                  ║
╚══════════════════════════════════════════════════════════════╝

Issues to Fix (by priority):

P0 - Constitutional Violations (must fix):
1. localStorage usage in lib/auth/session.ts:45
2. console.log in app/api/search/route.ts:23

P1 - Type/Build Errors:
3. Type error in components/Hero.tsx:12

P2 - Quality Issues:
4. Relative import in components/Footer.tsx:3
5. Missing ARIA label on button in components/SearchBar.tsx:28

Refactoring Opportunities (written to code-smells.md):
1. Nested ternary in components/Filters.tsx:44
2. Long parameter list in lib/search/buildQuery.ts:18
```

---

## Phase Gate Rules

| Phase | Blocking? | Rule |
|-------|-----------|------|
| 1. Build | ✅ Yes | Cannot proceed if build fails |
| 2. Types | ⚠️ Soft | Report errors, suggest fixes |
| 3. Lint | ⚠️ Soft | Report issues, allow override |
| 4. Tests | ✅ Yes | Cannot proceed if tests fail |
| 5. Security | ✅ Yes | Constitutional violations block PR |
| 6. OWASP | ✅ Yes (HIGH only) | Any HIGH finding = stop pipeline. MEDIUM/LOW = report and continue. |
| 7. Hygiene | ⚠️ Soft | Report for cleanup |
| 8. Diff | 📋 Info | Human review checkpoint |
| 9. Code Smells | ✅ Yes (P0 only) | Stop on any P0 smell; otherwise track refactors in code-smells.md |
| 10. Commit | ✅ Yes | Only runs if no P0/P1 blockers. Stages + commits all changes. |

---

## Continuous Mode

For long coding sessions, run verification at these checkpoints:

- ✅ After completing each component
- ✅ After finishing an API route
- ✅ Before switching to a different feature
- ✅ Every 30 minutes of active coding

```
Run a quick verification check (build + types + lint only).
```

Near the end of a full run, add 1–2 implementable app ideas in `code-smells.md` under a `Creative Implementation Ideas` section.

---

## Integration with Other Skills

| Skill | Relationship |
|-------|--------------|
| `owasp-security-review` | Called as Phase 6 (composable). HIGH findings kill the pipeline. |
| `code-review` | Branch-wrapup is tactical (pass/fail); code-review is strategic (architectural) |
| `testing` | Branch-wrapup runs tests; testing skill helps write them |
| `git-commit` | Branch-wrapup uses git-commit conventions for Phase 10 |
| `deployment` | Run branch-wrapup before deployment skill |
| `ci-cd` | Branch-wrapup is local preview of what CI will check |

---

## PowerShell Script

For automated runs, use the bundled script:

**See**: `verify.ps1` for standalone verification script

```powershell
# Run full wrapup (verify + commit)
.\.github\skills\branch-wrapup\verify.ps1

# Run specific phases
.\.github\skills\branch-wrapup\verify.ps1 -Phases Build,Types,Lint,OWASP

# Skip commit (verify only)
.\.github\skills\branch-wrapup\verify.ps1 -NoCommit
```

---

## Troubleshooting

### Build fails with "Module not found"

1. Delete `node_modules` and `.next`
2. Run `npm ci` (clean install)
3. Try build again

### Type check hangs

Check for circular imports:
```powershell
npx madge --circular --extensions ts,tsx app/ components/ lib/
```

### Security scan false positives

If a pattern is intentionally used (e.g., `localStorage` in a polyfill check):
1. Add `// verification-ignore: localStorage-check` comment
2. Document in PR description why it's acceptable

---

## Related Skills

- `owasp-security-review` - OWASP Top 10:2025 quick scan (Phase 6 of this skill)
- `code-review` - Deep constitutional analysis
- `testing` - Test creation and debugging
