---
name: deployment
description: Azure App Service deployment workflow for the AI-HUB-Portal. Use when deploying to production, troubleshooting deployment issues, or managing Azure resources.
version: 1.0.0
---

# Deployment Skill

## Purpose

Guide direct-to-production deployment of the AI-HUB-Portal to Azure App Service using Docker containers, with health validation and rollback procedures.

## When to Use

- Deploying new releases to production
- Troubleshooting deployment failures
- Managing Azure App Service configuration
- Rolling back failed deployments
- Updating environment variables or secrets

## Deployment Architecture

```
GitHub (main branch)
    │
    ▼ (GitHub Actions)
┌─────────────────────┐
│  Build Docker Image │
│  (Node.js 20 Alpine)│
└─────────────────────┘
    │
    ▼ (Push to ACR)
┌─────────────────────┐
│  Azure Container    │
│  Registry (ACR)     │
└─────────────────────┘
    │
    ▼ (Deploy)
┌─────────────────────┐
│  Azure App Service  │
│  (Linux Container)  │
└─────────────────────┘
    │
    ▼ (Verify)
┌─────────────────────┐
│  Health Check       │
│  /api/health        │
└─────────────────────┘
```

## Pre-Deployment Checklist

Before deploying, ensure all checks pass:

```powershell
# 1. Lint check
npm run lint

# 2. Type check
npm run type-check

# 3. Run tests
npm run test

# 4. Build successfully
npm run build

# 5. (Optional) Test Docker build locally
docker build -t ai-hub-portal:local .
docker run -p 3000:3000 ai-hub-portal:local
```

## Manual Deployment Commands

### Build and Push Docker Image

```powershell
# Login to Azure
az login

# Login to Azure Container Registry
az acr login --name <ACR_NAME>

# Build and tag image
docker build -t <ACR_NAME>.azurecr.io/ai-hub-portal:latest .
docker build -t <ACR_NAME>.azurecr.io/ai-hub-portal:$(git rev-parse --short HEAD) .

# Push to ACR
docker push <ACR_NAME>.azurecr.io/ai-hub-portal:latest
docker push <ACR_NAME>.azurecr.io/ai-hub-portal:$(git rev-parse --short HEAD)
```

### Deploy to App Service

```powershell
# Deploy specific image tag
az webapp config container set \
  --resource-group <RESOURCE_GROUP> \
  --name <APP_SERVICE_NAME> \
  --container-image-name <ACR_NAME>.azurecr.io/ai-hub-portal:$(git rev-parse --short HEAD)

# Restart app service (if needed)
az webapp restart \
  --resource-group <RESOURCE_GROUP> \
  --name <APP_SERVICE_NAME>
```

### Verify Deployment

```powershell
# Check health endpoint
curl https://<APP_SERVICE_NAME>.azurewebsites.net/api/health

# Check logs
az webapp log tail \
  --resource-group <RESOURCE_GROUP> \
  --name <APP_SERVICE_NAME>

# Check container logs
az webapp log download \
  --resource-group <RESOURCE_GROUP> \
  --name <APP_SERVICE_NAME> \
  --log-file logs.zip
```

## Rollback Procedures

### Quick Rollback (Previous Image)

```powershell
# List recent image tags
az acr repository show-tags \
  --name <ACR_NAME> \
  --repository ai-hub-portal \
  --orderby time_desc \
  --top 10

# Rollback to previous version
az webapp config container set \
  --resource-group <RESOURCE_GROUP> \
  --name <APP_SERVICE_NAME> \
  --container-image-name <ACR_NAME>.azurecr.io/ai-hub-portal:<PREVIOUS_TAG>
```

### Rollback via Git

```powershell
# Revert commit and push (triggers new deployment)
git revert HEAD
git push origin main
```

## Environment Configuration

### Required Environment Variables

Set these in Azure App Service Configuration:

| Variable | Source | Description |
|----------|--------|-------------|
| `NEXTAUTH_URL` | Direct | App URL (https://...) |
| `NEXTAUTH_SECRET` | Key Vault | Session encryption key |
| `AZURE_AD_CLIENT_ID` | Key Vault | Entra ID app client ID |
| `AZURE_AD_CLIENT_SECRET` | Key Vault | Entra ID app secret |
| `AZURE_AD_TENANT_ID` | Key Vault | Entra ID tenant |
| `AZURE_SEARCH_ENDPOINT` | Key Vault | AI Search endpoint |
| `AZURE_SEARCH_KEY` | Key Vault | AI Search admin key |
| `AZURE_STORAGE_CONNECTION_STRING` | Key Vault | Table Storage connection |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Key Vault | App Insights connection |

### Key Vault References

Use Key Vault references in App Service settings:

```
@Microsoft.KeyVault(SecretUri=https://<VAULT_NAME>.vault.azure.net/secrets/<SECRET_NAME>/)
```

### Update Environment Variable

```powershell
# Set single variable
az webapp config appsettings set \
  --resource-group <RESOURCE_GROUP> \
  --name <APP_SERVICE_NAME> \
  --settings "VARIABLE_NAME=value"

# Set Key Vault reference
az webapp config appsettings set \
  --resource-group <RESOURCE_GROUP> \
  --name <APP_SERVICE_NAME> \
  --settings "SECRET_NAME=@Microsoft.KeyVault(SecretUri=https://<VAULT>.vault.azure.net/secrets/<SECRET>/)"
```

## Health Check Endpoint

The `/api/health` endpoint validates:

```json
{
  "status": "healthy",
  "timestamp": "2026-01-24T10:30:00Z",
  "version": "1.0.0",
  "checks": {
    "database": "ok",
    "search": "ok",
    "graph": "ok"
  }
}
```

Configure App Service health check:

```powershell
az webapp config set \
  --resource-group <RESOURCE_GROUP> \
  --name <APP_SERVICE_NAME> \
  --generic-configurations '{"healthCheckPath": "/api/health"}'
```

## Troubleshooting

### Container Fails to Start

1. Check container logs:
   ```powershell
   az webapp log tail --resource-group <RG> --name <APP>
   ```

2. Common causes:
   - Missing environment variables
   - Port mismatch (ensure `WEBSITES_PORT=3000`)
   - Memory limit exceeded

### Health Check Fails

1. Verify endpoint locally:
   ```powershell
   docker run -p 3000:3000 <IMAGE>
   curl http://localhost:3000/api/health
   ```

2. Check App Service logs for dependency errors (DB, Search, Graph)

### Slow Cold Start

1. Enable Always On:
   ```powershell
   az webapp config set \
     --resource-group <RG> \
     --name <APP> \
     --always-on true
   ```

2. Consider warming up with scheduled pings

### Permission Denied (Key Vault)

1. Verify App Service managed identity:
   ```powershell
   az webapp identity show --resource-group <RG> --name <APP>
   ```

2. Grant Key Vault access:
   ```powershell
   az keyvault set-policy \
     --name <VAULT> \
     --object-id <MANAGED_IDENTITY_OBJECT_ID> \
     --secret-permissions get list
   ```

## Resource Naming Convention

| Resource | Name Pattern | Example |
|----------|--------------|---------|
| Resource Group | `rg-aihub-<env>` | `rg-aihub-prod` |
| App Service | `app-aihub-<env>` | `app-aihub-prod` |
| Container Registry | `craihub<env>` | `craihubprod` |
| Key Vault | `kv-aihub-<env>` | `kv-aihub-prod` |
| App Insights | `appi-aihub-<env>` | `appi-aihub-prod` |

## CI/CD Integration

Deployment is automated via GitHub Actions (`.github/workflows/deploy.yml`):

1. Push to `main` triggers deployment
2. CI workflow must pass first (lint, test, build)
3. Uses OIDC federation for Azure auth (no stored secrets)
4. Automatic health check after deployment

## Related Skills

- `ci-cd` - Use for GitHub Actions workflow setup and debugging
- `testing` - Run tests before deploying to validate changes
- `code-review` - Use for pre-deployment code validation
- `monitoring` - Use after deployment to verify health and track metrics
- `database` - Use when deploying database schema changes

## Workflow Integration

Typical deployment workflow:

1. **Code complete** → Use `code-review` for validation
2. **Tests pass** → Use `testing` skill to verify
3. **Deploy** → Use this skill for Azure deployment
4. **Verify** → Use `monitoring` skill to check health
5. **Rollback if needed** → Use rollback procedures in this skill
