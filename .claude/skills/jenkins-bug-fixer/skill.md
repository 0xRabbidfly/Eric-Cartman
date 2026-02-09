# jenkins-bug-fixer

Automatically detects, triages, diagnoses, and fixes bugs from Jenkins CI/CD failures.

**Pattern:** @m13v_'s Omi Desktop approach - Claude Code agent with full codebase context + artifact-driven analysis.

**Workflow:** Jenkins failure → Fetch artifacts → Triage → Diagnose → Write reproduction test → Generate fix → Validate → Submit PR

---

## Overview

This skill implements an automated bug detection and fixing pipeline for Jenkins CI/CD failures. It operates without direct access to the testing machine by analyzing Jenkins artifacts (JUnit XML, logs, console output) combined with full codebase context.

**Key Features:**
- ✅ Artifact-driven analysis (no testing machine access needed)
- ✅ Test-first reproduction (@nbaschez pattern - 7.6K likes)
- ✅ Validation loop (ensures fix actually works)
- ✅ Incident memory (learns from past failures)
- ✅ Human review gate (agents draft, humans approve)

---

## Prerequisites

Before using this skill, ensure:

1. **Jenkins API Access:**
   ```bash
   # Set environment variables
   export JENKINS_URL="https://jenkins.example.com"
   export JENKINS_USER="your-username"
   export JENKINS_TOKEN="your-api-token"
   ```

2. **GitHub/GitLab Token:**
   ```bash
   export GITHUB_TOKEN="ghp_xxxxxxxxxxxx"
   # or for GitLab:
   export GITLAB_TOKEN="glpat-xxxxxxxxxxxx"
   ```

3. **Log Aggregation (Optional but Recommended):**
   ```bash
   export SENTRY_DSN="https://xxxxx@sentry.io/xxxxx"
   # or
   export POSTHOG_API_KEY="phc_xxxxxxxxxxxx"
   ```

4. **Incident Memory Database:**
   ```bash
   # SQLite database (auto-created)
   export INCIDENT_DB_PATH="$HOME/.jenkins-bug-fixer/incidents.db"
   ```

5. **Fix Flaky Tests First:**
   - Audit your test suite for flaky tests
   - Remove or fix them before deploying this skill
   - Flaky tests will cause false positives and reduce effectiveness

---

## Quick Start

### 1. Install & Configure

```bash
# Create config directory
mkdir -p ~/.jenkins-bug-fixer

# Copy the configuration template (see Configuration section below)
# Edit with your settings
nano ~/.jenkins-bug-fixer/config.yaml
```

### 2. Test with a Manual Trigger

```bash
# Analyze a specific Jenkins failure
claude "Analyze this Jenkins failure: https://jenkins.example.com/job/main/123/"
```

### 3. Set Up Jenkins Webhook (for automatic triggering)

Add to your Jenkinsfile:
```groovy
post {
    failure {
        httpRequest(
            url: 'http://your-server:8080/webhook/jenkins-failure',
            httpMode: 'POST',
            contentType: 'APPLICATION_JSON',
            requestBody: """
            {
                "build_url": "${env.BUILD_URL}",
                "job_name": "${env.JOB_NAME}",
                "build_number": "${env.BUILD_NUMBER}",
                "git_commit": "${env.GIT_COMMIT}",
                "git_branch": "${env.GIT_BRANCH}"
            }
            """
        )
    }
}
```

---

## Configuration

Create `~/.jenkins-bug-fixer/config.yaml`:

```yaml
# Jenkins Configuration
jenkins:
  url: "${JENKINS_URL}"
  user: "${JENKINS_USER}"
  token: "${JENKINS_TOKEN}"
  # Jobs to monitor (supports wildcards)
  monitored_jobs:
    - "*/main"
    - "*/develop"
    - "pr-*"

# Repository Configuration
repository:
  type: "github"  # or "gitlab"
  owner: "your-org"
  repo: "your-repo"
  base_branch: "main"

# Agent Behavior
agent:
  # Confidence threshold for auto-submitting PRs (0.0-1.0)
  # Below this, agent will create draft PR and request human review
  auto_submit_threshold: 0.75

  # Maximum attempts to fix a bug before giving up
  max_fix_attempts: 3

  # Whether to run tests locally before submitting PR
  validate_locally: true

  # Test-first reproduction (highly recommended)
  write_reproduction_test: true

# Incident Memory
incident_memory:
  enabled: true
  database_path: "${INCIDENT_DB_PATH}"
  # Consider bugs similar if error signature matches >= this threshold
  similarity_threshold: 0.85

# Notifications (optional)
notifications:
  slack:
    enabled: false
    webhook_url: "${SLACK_WEBHOOK_URL}"
  email:
    enabled: false
    recipients: ["team@example.com"]

# Log Aggregation (optional)
log_aggregation:
  sentry:
    enabled: false
    dsn: "${SENTRY_DSN}"
  posthog:
    enabled: false
    api_key: "${POSTHOG_API_KEY}"
```

---

## How It Works

### 7-Phase Workflow

When a Jenkins failure is detected, the skill executes:

#### Phase 1: **Detection & Artifact Collection**
- Fetches Jenkins build data via API (console output, JUnit XML, artifacts)
- Gathers log aggregation data (Sentry, Posthog)
- Parses and structures failure information

#### Phase 2: **Triage**
- Classifies failure type (test failure, build failure, runtime error)
- Determines severity (blocking, high, medium, low)
- Checks incident memory for similar past failures
- Decides confidence level and action plan

#### Phase 3: **Diagnosis**
- Loads full codebase context with Claude Code
- Traces execution path from test to failure point
- Identifies root cause
- Determines what changed (git diff)

#### Phase 4: **Test Reproduction** (@nbaschez pattern - 7.6K likes)
- Writes a test that reproduces the bug
- **Critical:** Test FAILS with current code
- This creates a validation loop
- Test becomes regression protection

#### Phase 5: **Fix Generation**
- Generates code fix based on root cause
- Runs reproduction test in loop
- Iterates until test passes (max 3 attempts)
- Validates no regressions in full test suite

#### Phase 6: **PR Submission**
- Creates branch: `fix/jenkins-{build-number}-{error-type}`
- Commits: (1) reproduction test, (2) fix
- Submits PR with full context
- Auto-submit if high confidence, draft PR if medium

#### Phase 7: **Incident Memory Update**
- Stores error signature, root cause, fix
- Links to similar past incidents
- Tracks success metrics
- Enables learning over time

---

## Example Output

### When analyzing a failure:

```
🔍 Analyzing Jenkins build #123 failure...

TRIAGE:
├─ Type: Test Failure (authentication)
├─ Severity: HIGH (main branch)
├─ Error: AssertionError: Expected 200, got 401
└─ Similar incidents: 1 found (87% match)

DIAGNOSIS:
├─ Location: src/auth/jwt_handler.py:45
├─ Issue: JWT token refresh logic missing
├─ Root cause: Token expires without auto-refresh
└─ Introduced by: Commit abc123 (2026-02-08)

REPRODUCTION TEST:
✓ Created tests/test_jwt_refresh.py
✓ Test fails as expected (401 error)

FIX GENERATION:
├─ Attempt 1: Implement auto-refresh logic
├─ Running test... ✓ PASSED
├─ Running full suite... ✓ 45 tests passed
└─ No regressions detected

PR SUBMISSION:
├─ Branch: fix/jenkins-123-jwt-token-refresh
├─ Commits: 2 (test + fix)
├─ Confidence: 89% (HIGH)
└─ PR #456 created: https://github.com/your-org/your-repo/pull/456

INCIDENT MEMORY:
✓ Stored error signature
✓ Linked to similar incident #550e8400
✓ Success rate for this pattern: 100% (3/3 fixes)

✅ Fix complete! Review PR #456 and merge when ready.
```

---

## Best Practices

### 1. **Fix Flaky Tests First** (r/devops consensus - 206 upvotes)
> "Nothing to be done here until tests behave deterministically"

Before deploying:
- Audit test suite for flaky tests
- Fix or remove them
- Flaky tests cause false positives

### 2. **Test-First Reproduction** (@nbaschez - 7,647 likes)
> "When I report a bug, don't start by trying to fix it. First write a test that reproduces the bug."

Always enable:
```yaml
agent:
  write_reproduction_test: true  # Don't disable!
```

### 3. **Fast CI** (@matanSF - 351 likes)
> "No pre-commit hooks = agent waits 10 min for CI instead of 5 sec"

Optimize CI:
- Use pre-commit hooks
- Parallelize tests
- Cache dependencies

### 4. **Humans Review Fixes** (@NabbilKhan)
> "Humans review the fix, not the bug discovery"

Configure for oversight:
```yaml
agent:
  auto_submit_threshold: 0.75  # High confidence still needs review
```

### 5. **Document Everything** (@matanSF)
> "Undocumented env vars = agent guesses, fails, guesses again"

Maintain docs:
- Environment variables
- Build requirements
- Test setup

---

## Advanced Features

### Flaky Test Detection

```yaml
flaky_test_detection:
  enabled: true
  retry_count: 10
  pass_threshold: 1  # If passes once, it's flaky
```

**Behavior:**
- Runs test 10 times
- If inconsistent results → Label as flaky, don't attempt fix
- Creates issue for QA team instead

### Auto-Rollback on Regression

```yaml
auto_rollback:
  enabled: true
  regression_threshold: 1  # Rollback if even 1 test breaks
```

**Behavior:**
- Runs full test suite after fix
- If new failures → Rollback, create issue instead of PR
- Prevents making things worse

### Batch Processing

```bash
# Process all recent failures
claude "Analyze all Jenkins failures from the last 24 hours"

# Process specific job
claude "Fix all failures in the main branch from last week"
```

### Dry Run Mode

```bash
# Diagnose only, don't create PR
claude "Analyze this failure but don't create a PR: https://jenkins.example.com/job/main/123/"
```

---

## Monitoring & Metrics

Track these metrics for continuous improvement:

```sql
-- Success Rate (target: >70%)
SELECT
    COUNT(*) FILTER (WHERE fix_validated = 1) * 100.0 / COUNT(*) as success_rate
FROM incidents
WHERE timestamp > (unixepoch('now') - 30*24*60*60);

-- Average Time to Fix (target: <10 minutes)
SELECT
    AVG(time_to_pr_minutes) as avg_time_to_fix
FROM incidents
WHERE fix_pr_url IS NOT NULL;

-- Most Common Error Types
SELECT
    failure_type,
    COUNT(*) as count
FROM incidents
GROUP BY failure_type
ORDER BY count DESC;
```

---

## Troubleshooting

### Issue: Fixes don't work

**Solutions:**
1. Check reproduction test quality:
   ```bash
   # Run manually
   pytest tests/test_reproduction.py -v
   ```
2. Ensure local validation is enabled:
   ```yaml
   agent:
     validate_locally: true
   ```
3. Increase confidence threshold:
   ```yaml
   agent:
     auto_submit_threshold: 0.90
   ```

### Issue: Too many false positives

**Solutions:**
1. Enable flaky test detection
2. Fix flaky tests first
3. Increase severity threshold:
   ```yaml
   agent:
     minimum_severity: "high"
   ```

### Issue: Insufficient context

**Solutions:**
1. Enable log aggregation (Sentry/Posthog)
2. Archive more Jenkins artifacts
3. Ensure full repo access

---

## ROI Calculation

**Assumptions:**
- 10 Jenkins failures per week
- Manual fix time: 30 min/failure
- Agent fix time: 10 min average
- Engineer hourly rate: $100/hr

**Manual:** 10 × 30 min × $100/hr = $500/week = **$26,000/year**

**Agent:** 10 × 10 min × $100/hr + 10 × $0.30 API = $170/week = **$8,840/year**

**Savings: $17,160/year** (66% reduction)

**Plus:**
- Faster feedback (minutes vs hours)
- Reduced context switching
- Engineers focus on high-value work

---

## References

- [@m13v_'s Omi Desktop pipeline](https://x.com/m13v_/status/2020355795414839710) - Original pattern
- [@nbaschez's test-first approach](https://x.com/nbaschez/status/2018027072720130090) - 7.6K likes
- [@avansledright's Jenkins tool](https://x.com/avansledright/status/2020244636326064239) - Incident memory
- [r/devops: Flaky tests](https://www.reddit.com/r/devops/comments/1qr00b5/) - Fix flaky tests first
- [Full implementation report](./implementation-report.md)
- [Research data](./research.md)

---

## Next Steps

1. **Review this skill.md** - Customize for your needs
2. **Set up prerequisites** - API tokens, config.yaml
3. **Run proof of concept** - Test with one failure
4. **Deploy webhook** - Automate for all failures
5. **Monitor metrics** - Track success rate and improve

---

**v1.0.0** (2026-02-09) - Based on @m13v_'s pattern + community research

<sub>🤖 This skill implements automated bug fixing for Jenkins CI/CD failures.</sub>
