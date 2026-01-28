# GitHub Actions Debugging Guide

## Common Workflow Failures

### Timeout Issues

**Error**: "The job running on runner has exceeded the maximum execution time"

**Cause**: Long-running builds, slow dependency installation, or stuck processes

**Solutions**:
```yaml
jobs:
  build:
    timeout-minutes: 30  # Set reasonable timeout (default: 360)
```

- Use dependency caching
- Run jobs in parallel
- Investigate slow steps with timing analysis

### Azure Authentication Failures

**Error**: "AADSTS70021: No matching federated identity record found"

**Cause**: Federated credential not configured or subject mismatch

**Solutions**:
1. Verify federated credential subject matches repository:
   ```powershell
   az ad app federated-credential list --id {APP_ID}
   ```

2. Check subject format:
   ```
   repo:YOUR_ORG/AI-HUB-Portal:ref:refs/heads/main
   ```

3. Ensure OIDC permissions:
   ```yaml
   permissions:
     id-token: write
     contents: read
   ```

### Docker Build Failures

**Error**: "ACR login failed: unauthorized"

**Cause**: Service principal lacks ACR permissions

**Solution**:
```powershell
az role assignment create \
  --assignee {CLIENT_ID} \
  --role AcrPush \
  --scope /subscriptions/{SUB}/resourceGroups/{RG}/providers/Microsoft.ContainerRegistry/registries/{ACR}
```

**Error**: "COPY failed: file not found"

**Cause**: .dockerignore or missing files

**Solution**: Check Dockerfile paths are relative to build context

### Test Failures in CI Only

**Error**: Tests pass locally but fail in CI

**Common causes**:
1. **Timezone issues**:
   ```yaml
   env:
     TZ: UTC  # Or your project's canonical timezone
   ```

2. **Environment variables**:
   ```yaml
   env:
     NODE_ENV: test
     CI: true
   ```

3. **Missing dependencies**:
   - Check `package.json` devDependencies
   - Verify `npm ci` vs `npm install`

4. **File system case sensitivity**:
   - Linux runners are case-sensitive
   - Windows/macOS are not

### npm install/ci Failures

**Error**: "EACCES: permission denied"

**Solution**:
```yaml
- run: npm ci --prefer-offline --no-audit
```

**Error**: "lockfile out of sync"

**Solution**: Ensure `package-lock.json` is committed and up-to-date

## Debugging Techniques

### Enable Debug Logging

Add repository variables:
- `ACTIONS_STEP_DEBUG`: `true`
- `ACTIONS_RUNNER_DEBUG`: `true`

### Verbose Bash Output

```yaml
- name: Debug script
  run: |
    set -x  # Enable verbose output
    echo "Current directory: $(pwd)"
    ls -la
    env | sort
```

### SSH into Runner (using tmate)

```yaml
- name: Setup tmate session
  if: failure()  # Only on failure
  uses: mxschmitt/action-tmate@v3
  timeout-minutes: 15
```

**Warning**: Don't use in public repos (security risk)

### Inspect Artifacts

```yaml
- name: Upload logs on failure
  if: failure()
  uses: actions/upload-artifact@v4
  with:
    name: logs
    path: |
      *.log
      test-results/
```

### Matrix Debugging

```yaml
strategy:
  fail-fast: false  # Don't cancel other matrix jobs on failure
  matrix:
    node-version: [18, 20, 22]
```

## Testing Locally with `act`

### Installation

```powershell
# Windows
winget install nektos.act

# Or via npm
npm install -g act
```

### Usage

```bash
# Run all workflows
act

# Run specific event
act pull_request

# Run specific job
act -j build-test

# Use specific event payload
act push --eventpath event.json

# Dry run (show what would run)
act -n
```

### Secrets for Local Testing

Create `.secrets` file:
```
AZURE_CLIENT_ID=test-client-id
AZURE_TENANT_ID=test-tenant-id
ACR_NAME=test-acr
```

Run with secrets:
```bash
act --secret-file .secrets
```

**Warning**: Never commit `.secrets` file

### Limitations

- Can't test OIDC authentication locally
- Some actions may not work in containers
- Performance may differ from GitHub runners

## Troubleshooting Checklist

When a workflow fails:

- [ ] Check status page: https://www.githubstatus.com
- [ ] Review workflow logs (expand all steps)
- [ ] Check if recent changes affected the workflow
- [ ] Verify all secrets are configured
- [ ] Test locally with `act` if possible
- [ ] Check for known issues in action repositories
- [ ] Review recent deployments (may affect Azure resources)
- [ ] Verify service principal permissions haven't changed
- [ ] Check quota limits (GitHub Actions minutes, Azure resources)
