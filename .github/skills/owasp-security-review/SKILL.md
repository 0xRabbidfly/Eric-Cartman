---
name: owasp-security-review
description: >
  Quick-scan security code review against the OWASP Top 10:2025 for React/TypeScript apps
  using Azure AD (Entra ID) OAuth and deployed as Azure App Service. Reports findings by
  severity (HIGH / MEDIUM / LOW) with recommended fixes. Use this skill when asked for a
  security review, OWASP scan, security audit, vulnerability check, or when running
  /branch-wrapup (it is called automatically as Phase 6).
user-invocable: true
metadata:
  author: 0xrabbidfly
  version: "1.0.0"
  owasp-version: "2025"
---

# OWASP Security Review

## Purpose

Run a fast, pattern-based security scan against the **OWASP Top 10:2025** checklist, tuned
for a React/TypeScript stack with Azure AD (Entra ID) authentication and Azure App Service
deployment. Produces a terminal report grouped by severity so developers can triage quickly.

This is a quick scan, not a full penetration test. It catches the low-hanging fruit that
static analysis can detect by reading source code and configuration files.

## When to Use

- Explicitly: "run an OWASP security review", "check for vulnerabilities", "security scan"
- Automatically: called by `/branch-wrapup` as Phase 6

## Composability

When invoked from another skill (e.g., branch-wrapup), this skill returns a structured
result the caller can act on:

- **Exit: PASS** — no HIGH findings. Caller may continue.
- **Exit: FAIL** — one or more HIGH findings. Caller should stop the pipeline.

The caller decides what to do with MEDIUM and LOW findings (typically: report and continue).

---

## Scan Procedure

### Step 1: Identify scan targets

Determine which directories contain application source. Typical React/TS layout:

```
src/        or  app/
components/
lib/        or  utils/
pages/      or  routes/
api/        or  server/
```

Also locate configuration files:
- `web.config`, `staticwebapp.config.json`, `azure-pipelines.yml`, `.github/workflows/*.yml`
- `.env`, `.env.production`, `.env.local`
- `package.json`, `package-lock.json`, `.npmrc`
- MSAL / auth configuration files (search for `@azure/msal-browser`, `@azure/msal-react`)

### Step 2: Run checks by OWASP category

For each category below, run the listed grep/search patterns. Not every check will apply
to every project — skip checks that target files or patterns that don't exist. Don't waste
time on false leads.

---

#### A01:2025 — Broken Access Control

Why this matters: the #1 vulnerability. Client-side route guards without server enforcement
are the most common gap in React SPAs.

| ID | Check | Pattern / Command |
|----|-------|-------------------|
| A01-1 | Wildcard CORS | Grep for `Access-Control-Allow-Origin` with `*` in server code and config |
| A01-2 | CORS + credentials | Grep for `credentials: true` alongside dynamic or reflected origin |
| A01-3 | Missing auth middleware | Grep API route handlers — each should reference auth middleware (`requireAuth`, `isAuthenticated`, `authorize`, `withAuth`) |
| A01-4 | IDOR — user IDs in queries | Grep for `req.params.id` or `req.query.id` used directly in DB lookups without ownership validation |
| A01-5 | JWT decode without verify | Grep for `jwt.decode` (should be `jwt.verify`); `jsonwebtoken` decode-only usage |
| A01-6 | Missing CSRF protection | Grep POST/PUT/DELETE handlers for CSRF token validation |

**Severity guide:** A01-1 with credentials = HIGH. Missing auth middleware on sensitive routes = HIGH. Others = MEDIUM.

---

#### A02:2025 — Security Misconfiguration

| ID | Check | Pattern / Command |
|----|-------|-------------------|
| A02-1 | Missing Content-Security-Policy | Grep server config / middleware for `Content-Security-Policy` header — absence = finding |
| A02-2 | Missing security headers | Check for `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security` |
| A02-3 | Source maps in production | Grep for `GENERATE_SOURCEMAP=true` in `.env.production` or `devtool: 'source-map'` in webpack/vite prod config |
| A02-4 | HTTPS redirect disabled | Check `web.config` or App Service config for `httpsOnly` — should be `true` |
| A02-5 | Verbose error responses | Grep for `err.stack` or `error.stack` returned in HTTP responses |
| A02-6 | Debug mode in production | Grep for `NODE_ENV` checks that might leave debug features on |

**Severity guide:** Missing CSP = MEDIUM. Source maps in prod = HIGH (exposes full source). HTTPS disabled = HIGH.

---

#### A03:2025 — Software Supply Chain Failures

This is new in 2025 — expanded from "Vulnerable Components" to cover the full supply chain.

| ID | Check | Pattern / Command |
|----|-------|-------------------|
| A03-1 | Missing lockfile | Check for `package-lock.json` or `yarn.lock` at repo root |
| A03-2 | `npm install` in CI | Grep CI configs for `npm install` — should be `npm ci` for reproducible builds |
| A03-3 | No `ignore-scripts` | Check `.npmrc` for `ignore-scripts=true` |
| A03-4 | Unpinned dependencies | Grep `package.json` dependencies for `^` or `~` (loose semver ranges) |
| A03-5 | Missing scope on internal packages | Grep for internal packages not using `@org/` prefix (dependency confusion risk) |

**Severity guide:** Missing lockfile = HIGH. `npm install` in CI = MEDIUM. Others = LOW.

---

#### A04:2025 — Cryptographic Failures

| ID | Check | Pattern / Command |
|----|-------|-------------------|
| A04-1 | Secrets in source | Grep for `password\s*=`, `secret\s*=`, `apiKey`, `connectionString`, hardcoded UUIDs matching Azure patterns |
| A04-2 | Tokens in localStorage | Grep for `localStorage.setItem` with token/auth keys; check MSAL config for `cacheLocation: "localStorage"` |
| A04-3 | HTTP in API calls | Grep for `http://` in fetch/axios calls (not `https://`) |
| A04-4 | MSAL cache in localStorage | Grep MSAL config for `cacheLocation` — should be `sessionStorage` or `memoryStorage`, not `localStorage` |
| A04-5 | Sensitive data in URLs | Grep for tokens or secrets appended as query parameters |

**Severity guide:** Secrets in source = HIGH. Tokens in localStorage = HIGH. HTTP calls = MEDIUM.

---

#### A05:2025 — Injection

React's JSX auto-escapes by default, which is great — but there are escape hatches.

| ID | Check | Pattern / Command |
|----|-------|-------------------|
| A05-1 | `dangerouslySetInnerHTML` | Grep for `dangerouslySetInnerHTML` — every hit needs manual audit. Check if DOMPurify is used. |
| A05-2 | `eval()` / `new Function()` | Grep for `eval(`, `new Function(`, `setTimeout(` with string argument |
| A05-3 | `.innerHTML` assignment | Grep for `.innerHTML =` in TypeScript/JavaScript files |
| A05-4 | SQL template literals | Grep for template literal SQL: `` `SELECT.*\$\{` `` (if backend is co-located) |
| A05-5 | Unvalidated `window.open` / `href` | Grep for `window.open(` or `href={` with dynamic user input — open redirect risk |
| A05-6 | `document.write()` | Grep for `document.write(` |

**Severity guide:** `eval()` = HIGH. `dangerouslySetInnerHTML` without sanitizer = HIGH. Others = MEDIUM.

---

#### A06:2025 — Insecure Design

Harder to grep for — these are architectural patterns.

| ID | Check | Pattern / Command |
|----|-------|-------------------|
| A06-1 | No rate limiting | Check API middleware for rate-limiting (`express-rate-limit`, Azure API Management throttling) — absence on auth endpoints = finding |
| A06-2 | Unbounded input | Grep for API handlers accepting string inputs without length/type validation (no Zod, Yup, or joi) |

**Severity guide:** No rate limiting on auth = MEDIUM. Unbounded input = LOW.

---

#### A07:2025 — Authentication Failures

This is where Azure AD / Entra ID specifics matter most.

| ID | Check | Pattern / Command |
|----|-------|-------------------|
| A07-1 | Permissive tenant | Grep MSAL authority for `login.microsoftonline.com/common` or `/organizations` — should be tenant-specific for enterprise apps |
| A07-2 | Missing audience validation | Grep token verification middleware for `audience` or `aud` claim validation |
| A07-3 | Missing issuer validation | Grep for `iss` claim validation against `https://login.microsoftonline.com/{tenantId}/v2.0` |
| A07-4 | Implicit flow | Grep MSAL config — `responseType` should NOT be `token` or `id_token` alone. Should use auth code flow with PKCE. |
| A07-5 | Refresh tokens in client code | Grep for refresh token handling in client-side (browser) code |
| A07-6 | Missing logout invalidation | Grep logout handlers — should call `logoutRedirect`/`logoutPopup` AND clear server session |

**Severity guide:** Permissive tenant (`/common`) in enterprise app = HIGH. Implicit flow = HIGH. Missing aud/iss validation = HIGH. Others = MEDIUM.

---

#### A08:2025 — Software or Data Integrity Failures

| ID | Check | Pattern / Command |
|----|-------|-------------------|
| A08-1 | Missing SRI on CDN scripts | Grep `index.html` for `<script src=` from external CDNs without `integrity=` attribute |
| A08-2 | Unsafe deserialization | Grep for `JSON.parse()` on user-controlled input without schema validation |

**Severity guide:** Missing SRI = MEDIUM. Unvalidated deserialization = MEDIUM.

---

#### A09:2025 — Security Logging and Alerting Failures

| ID | Check | Pattern / Command |
|----|-------|-------------------|
| A09-1 | No Application Insights | Check `package.json` for `@microsoft/applicationinsights-web` or `applicationinsights` — absence = finding |
| A09-2 | Auth events not logged | Grep login/logout/token-refresh handlers for structured log emissions |
| A09-3 | Sensitive data in logs | Grep for `console.log` or logger calls that might include tokens, passwords, PII |
| A09-4 | `console.log` in production | Grep non-test source files for `console.log` |

**Severity guide:** No monitoring at all = MEDIUM. Sensitive data in logs = HIGH. Others = LOW.

---

#### A10:2025 — Mishandling of Exceptional Conditions

New in 2025 — replaces SSRF (which merged into A01).

| ID | Check | Pattern / Command |
|----|-------|-------------------|
| A10-1 | Empty catch blocks | Grep for `catch\s*\(.*\)\s*\{[\s]*\}` — swallowed errors |
| A10-2 | Fail-open auth | Grep for catch blocks in auth/permission code that return success on failure (e.g., `catch { return true }`) |
| A10-3 | Missing error boundaries | Grep for `ErrorBoundary` or `componentDidCatch` — should exist at top level |
| A10-4 | Stack traces in responses | Grep for `err.stack` or `error.stack` in API response bodies |

**Severity guide:** Fail-open auth = HIGH. Empty catch in auth paths = HIGH. Others = MEDIUM.

---

### Step 3: Check Azure App Service deployment config

Scan deployment configuration for common misconfigurations:

| ID | Check | Where to look |
|----|-------|---------------|
| AZ-1 | HTTPS only | `web.config` → `<httpRedirect>`, or ARM template for `httpsOnly: true` |
| AZ-2 | TLS version | Should be 1.2+ — check `minTlsVersion` in ARM/Bicep templates |
| AZ-3 | Managed Identity | Check if app uses managed identity for Azure resource access instead of connection strings |
| AZ-4 | App Settings secrets | Check if secrets are in App Settings vs Key Vault references (`@Microsoft.KeyVault(...)`) |
| AZ-5 | CORS config | Check `allowedOrigins` in App Service CORS — should not be `*` |
| AZ-6 | Remote debugging | Should be disabled in production — check for `remoteDebuggingEnabled: true` |
| AZ-7 | FTP deployment | Should be disabled — check for `ftpsState: "AllAllowed"` |

**Severity guide:** Remote debugging enabled = HIGH. FTP enabled = HIGH. No HTTPS = HIGH. Others = MEDIUM.

---

### Step 4: Produce the terminal report

Group findings by severity. Use this exact format:

```
╔══════════════════════════════════════════════════════════════╗
║              OWASP TOP 10:2025 SECURITY SCAN                ║
╠══════════════════════════════════════════════════════════════╣
║  Categories scanned:  10/10                                 ║
║  Azure config checked: Yes/No                               ║
║  Findings:  X HIGH  |  Y MEDIUM  |  Z LOW                  ║
║  Result:    PASS / FAIL                                     ║
╚══════════════════════════════════════════════════════════════╝

--- HIGH (must fix before merge) ---

[A04-1] Secrets in source code
  File: src/lib/api-client.ts:23
  Found: apiKey = "sk-proj-abc123..."
  Fix: Move to Azure Key Vault. Reference via App Settings:
       @Microsoft.KeyVault(SecretUri=https://your-vault.vault.azure.net/secrets/api-key)

[A07-1] Permissive tenant configuration
  File: src/auth/msalConfig.ts:8
  Found: authority: "https://login.microsoftonline.com/common"
  Fix: Replace with tenant-specific authority:
       https://login.microsoftonline.com/{your-tenant-id}

--- MEDIUM (fix before PR if practical) ---

[A02-1] Missing Content-Security-Policy header
  File: (not found in server config)
  Fix: Add CSP header in middleware or web.config. Start with:
       default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'

--- LOW (track for future cleanup) ---

[A03-4] Unpinned dependencies
  File: package.json
  Found: 12 dependencies using ^ or ~ ranges
  Fix: Consider pinning exact versions for reproducible builds

--- No findings in: A06, A08 ---
```

### Step 5: Return result to caller

If invoked standalone, the terminal report is the final output.

If invoked as part of another skill (branch-wrapup), return:

- **PASS** if zero HIGH findings → caller continues
- **FAIL** if any HIGH findings → caller should abort the pipeline

Always report MEDIUM and LOW findings in the terminal regardless of pass/fail status.

---

## Rules

1. **Don't hallucinate findings.** Only report what you actually found in the code. If a grep returns nothing, that check is clean — move on.
2. **Skip inapplicable checks.** No backend code in the repo? Skip SQL injection checks. No `web.config`? Skip Azure config checks. State what was skipped and why at the bottom of the report.
3. **One finding per issue.** Don't report the same `dangerouslySetInnerHTML` on 15 lines as 15 separate findings — group them as one finding with a count.
4. **Recommended fixes must be actionable.** Don't just say "fix this" — show what the fix looks like for this specific stack (React/TS, Azure AD, App Service).
5. **Time-box the scan.** This is a quick scan. Spend ~2-3 minutes per category, not 20. If a pattern search is taking too long, note it and move on.
6. **False positive escape hatch.** If a file contains `// owasp-ignore: <ID>` (e.g., `// owasp-ignore: A05-1`), skip that line and note it as "acknowledged" in the report.
