# GitHub Actions Secrets Checklist

This document lists all required secrets and variables for GitHub Actions workflows in the AI-HUB-Portal project.

## Required Repository Secrets

Navigate to: **Settings > Secrets and variables > Actions > Repository secrets**

### Azure Authentication (OIDC)

| Secret Name | Description | How to Obtain | Required For |
|-------------|-------------|---------------|--------------|
| `AZURE_CLIENT_ID` | Service Principal Application (client) ID | Azure Portal > App Registrations > Application (client) ID | All Azure workflows |
| `AZURE_TENANT_ID` | Azure AD Tenant ID | Azure Portal > App Registrations > Directory (tenant) ID | All Azure workflows |
| `AZURE_SUBSCRIPTION_ID` | Azure Subscription ID | Azure Portal > Subscriptions > Subscription ID | All Azure workflows |

### Azure Resources

| Secret Name | Description | Example Value | Required For |
|-------------|-------------|---------------|--------------|
| `ACR_NAME` | Azure Container Registry name | `craihubprod` | Docker build/push |
| `AZURE_RESOURCE_GROUP` | Resource Group name | `rg-aihub-prod` | Deployment |
| `AZURE_APP_SERVICE` | App Service name | `app-aihub-prod` | Deployment |

## Optional Secrets

| Secret Name | Description | Use Case |
|-------------|-------------|----------|
| `SLACK_WEBHOOK_URL` | Slack webhook for notifications | Deployment notifications |
| `TEAMS_WEBHOOK_URL` | Microsoft Teams webhook | Deployment notifications |
| `SONAR_TOKEN` | SonarCloud token | Code quality scanning |

## Setting Up OIDC Authentication

### Prerequisites

1. Azure subscription with Owner or Contributor role
2. GitHub repository with Actions enabled

### Step 1: Create Service Principal

```powershell
# Login to Azure
az login

# Create service principal
az ad sp create-for-rbac \
  --name "github-actions-ai-hub" \
  --role Contributor \
  --scopes /subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP} \
  --sdk-auth
```

Note the output:
- `clientId` → `AZURE_CLIENT_ID`
- `tenantId` → `AZURE_TENANT_ID`
- `subscriptionId` → `AZURE_SUBSCRIPTION_ID`

### Step 2: Configure Federated Credentials

```powershell
# Get the Application ID
$APP_ID = az ad sp show --id {CLIENT_ID} --query appId -o tsv

# Add federated credential for main branch
az ad app federated-credential create \
  --id $APP_ID \
  --parameters '{
    "name": "github-actions-main",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:YOUR_ORG/AI-HUB-Portal:ref:refs/heads/main",
    "audiences": ["api://AzureADTokenExchange"]
  }'

# Add federated credential for pull requests
az ad app federated-credential create \
  --id $APP_ID \
  --parameters '{
    "name": "github-actions-pr",
    "issuer": "https://token.actions.githubusercontent.com",
    "subject": "repo:YOUR_ORG/AI-HUB-Portal:pull_request",
    "audiences": ["api://AzureADTokenExchange"]
  }'
```

### Step 3: Grant ACR Permissions

```powershell
# Grant service principal permission to push to ACR
az role assignment create \
  --assignee {CLIENT_ID} \
  --role AcrPush \
  --scope /subscriptions/{SUBSCRIPTION_ID}/resourceGroups/{RESOURCE_GROUP}/providers/Microsoft.ContainerRegistry/registries/{ACR_NAME}
```

### Step 4: Add Secrets to GitHub

1. Navigate to your repository
2. Go to **Settings > Secrets and variables > Actions**
3. Click **New repository secret**
4. Add each secret from the table above

## Verification

### Test OIDC Authentication

Create a test workflow:

```yaml
name: Test Azure OIDC

on: workflow_dispatch

jobs:
  test:
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read

    steps:
      - name: Azure Login
        uses: azure/login@v1
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

      - name: Verify access
        run: |
          az account show
          az acr login --name ${{ secrets.ACR_NAME }}
```

Run this workflow manually to verify all secrets are configured correctly.

## Environment-Specific Secrets

For multi-environment deployments (staging, production), use **Environment secrets**:

1. Navigate to **Settings > Environments**
2. Create environment (e.g., "production")
3. Add environment-specific secrets
4. Configure protection rules (required reviewers, branch restrictions)

### Environment Variables

| Environment | App Service Name | Resource Group |
|-------------|------------------|----------------|
| Production | `app-aihub-prod` | `rg-aihub-prod` |
| Staging | `app-aihub-staging` | `rg-aihub-staging` |
| Development | `app-aihub-dev` | `rg-aihub-dev` |

## Security Best Practices

✅ **DO**:
- Use OIDC federation instead of storing credentials
- Rotate service principal credentials regularly
- Use environment-specific secrets for sensitive values
- Limit service principal permissions to minimum required (least privilege)
- Enable environment protection rules for production
- Use GitHub's secret scanning feature

❌ **DON'T**:
- Commit secrets to repository (even in comments)
- Use the same secrets across multiple projects
- Grant service principals Owner role unless absolutely necessary
- Store production secrets in development environments
- Share secrets via insecure channels (email, chat)

## Troubleshooting

### Error: "AADSTS70021: No matching federated identity record found"

**Cause**: Federated credential not configured or subject mismatch

**Solution**: Verify federated credential subject matches your repository and branch:
```powershell
az ad app federated-credential list --id {APP_ID}
```

### Error: "ACR login failed: unauthorized"

**Cause**: Service principal lacks ACR permissions

**Solution**: Grant AcrPush role:
```powershell
az role assignment create \
  --assignee {CLIENT_ID} \
  --role AcrPush \
  --scope /subscriptions/{SUB_ID}/resourceGroups/{RG}/providers/Microsoft.ContainerRegistry/registries/{ACR_NAME}
```

### Error: "Secret not found"

**Cause**: Secret name mismatch or not added to repository

**Solution**: Verify secret name exactly matches (case-sensitive) in:
- Settings > Secrets and variables > Actions
- Workflow file (`${{ secrets.SECRET_NAME }}`)

## Additional Resources

- [GitHub OIDC Documentation](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [Azure Federated Credentials](https://learn.microsoft.com/en-us/azure/active-directory/develop/workload-identity-federation)
- [GitHub Actions Security Best Practices](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
