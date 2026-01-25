---
name: ci-cd
description: GitHub Actions workflow creation, debugging, and optimization for CI/CD pipelines. Use when setting up automated builds, deployment pipelines, debugging workflow failures, or optimizing build performance.
version: 1.0.0
---

# CI/CD Skill

## Purpose

Guide the creation, debugging, and optimization of GitHub Actions workflows for continuous integration and continuous deployment (CI/CD) pipelines in the AI-HUB-Portal project.

## When to Use

- Creating new GitHub Actions workflows
- Debugging workflow failures or timeout issues
- Optimizing build performance and caching strategies
- Adding automated checks (tests, linting, security scans)
- Setting up deployment automation
- Configuring secrets and environment variables

## Quick Start

**See**: `workflow-templates/` for complete workflow examples

### Basic PR Check Workflow

```yaml
name: CI
on: [pull_request, push]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
      - run: npm ci
      - run: npm run lint
      - run: npm test
      - run: npm run build
```

### Deploy to Azure

```yaml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      id-token: write  # Required for OIDC
    steps:
      - uses: actions/checkout@v4
      - uses: azure/login@v1
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - run: |
          az acr login --name ${{ secrets.ACR_NAME }}
          docker build -t ${{ secrets.ACR_NAME }}.azurecr.io/ai-hub-portal:${{ github.sha }} .
          docker push ${{ secrets.ACR_NAME }}.azurecr.io/ai-hub-portal:${{ github.sha }}
```

## Required Secrets

Navigate to **Settings > Secrets and variables > Actions**

| Secret | Description |
|--------|-------------|
| `AZURE_CLIENT_ID` | Service Principal Client ID |
| `AZURE_TENANT_ID` | Azure AD Tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure Subscription ID |
| `ACR_NAME` | Container Registry name |
| `AZURE_RESOURCE_GROUP` | Resource Group name |
| `AZURE_APP_SERVICE` | App Service name |

**See**: `secrets-checklist.md` for complete setup instructions including OIDC configuration

## Common Tasks

### Enable Dependency Caching

```yaml
- uses: actions/setup-node@v4
  with:
    node-version: '20'
    cache: 'npm'  # Caches node_modules

- run: npm ci  # Use 'ci' for clean install
```

**Benefit**: 30-60% faster builds

### Run Jobs in Parallel

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps: [...]

  test:
    runs-on: ubuntu-latest
    steps: [...]

  type-check:
    runs-on: ubuntu-latest
    steps: [...]
```

### Conditional Execution

```yaml
- name: Run E2E tests
  if: github.ref == 'refs/heads/main'
  run: npm run test:e2e
```

## Debugging Workflows

### Reading Logs

1. Go to **Actions** tab
2. Select failed workflow
3. Click failed job → Expand failed step

### Common Failures

| Error | Cause | Solution |
|-------|-------|----------|
| Timeout | Long build, stuck process | Set `timeout-minutes: 30` on job |
| Permission denied (Azure) | Missing OIDC permissions | Add `permissions: id-token: write` |
| npm install fails | Permission issues | Use `npm ci --prefer-offline` |
| Tests pass locally, fail in CI | Environment differences | Set `env: CI: true, TZ: America/Toronto` |

**See**: `debugging.md` for detailed troubleshooting guide

### Testing Locally with `act`

```bash
# Install act
winget install nektos.act

# Run workflow locally
act pull_request

# Run specific job
act -j build-test
```

## Optimization Tips

- ✅ Use `npm ci` instead of `npm install`
- ✅ Cache dependencies with `cache: 'npm'`
- ✅ Run independent jobs in parallel
- ✅ Use Docker layer caching with buildx
- ✅ Set reasonable timeouts
- ✅ Skip unnecessary jobs with conditionals

**See**: `workflow-patterns.md` for advanced patterns (matrix builds, artifact sharing, etc.)

## Best Practices

### DO:
✅ Use OIDC federation (no stored credentials)
✅ Run quality checks (lint, test) in parallel
✅ Add health checks after deployment
✅ Tag Docker images with git SHA
✅ Use `workflow_dispatch` for manual triggers
✅ Store secrets in GitHub Secrets or Azure Key Vault

### DON'T:
❌ Commit secrets to repository
❌ Use `npm install` in CI (use `npm ci`)
❌ Deploy without protection rules
❌ Use `latest` as the only Docker tag
❌ Ignore workflow timeout limits

## Related Skills

- `testing` - Use for comprehensive test execution before deployment
- `deployment` - Use for manual Azure deployment procedures
- `monitoring` - Use to verify deployment health and track metrics
- `code-review` - Integrate automated checks into PR review process

## Workflow Integration

Typical development workflow:

1. **Create feature branch** → Work on feature
2. **Open pull request** → `ci-cd` skill triggers PR checks
3. **PR checks pass** → Use `code-review` skill for review
4. **Merge to main** → `ci-cd` skill triggers deployment
5. **Deployment completes** → Use `monitoring` skill to verify health
6. **Issues detected** → Use `deployment` skill for rollback if needed

## Supporting Files

- `workflow-templates/build-test.yml` - Complete PR check workflow
- `workflow-templates/deploy-azure.yml` - Complete deployment workflow
- `secrets-checklist.md` - Required secrets and OIDC setup
- `workflow-patterns.md` - Advanced patterns and optimizations
- `debugging.md` - Detailed troubleshooting guide
