# Application Insights Alert Configuration Guide

Complete guide for setting up alerts in Azure Application Insights for the AI-HUB-Portal.

## Recommended Alerts

| Alert Name | Metric | Condition | Window | Frequency | Severity |
|------------|--------|-----------|--------|-----------|----------|
| High Error Rate | Request failure % | > 5% | 5 min | 1 min | Sev 2 |
| Slow Response Time | P95 duration | > 3s | 5 min | 1 min | Sev 3 |
| Graph API Failures | Dependency failures | > 10 failures | 5 min | 1 min | Sev 2 |
| Search Unavailable | Search requests | 0 successful | 5 min | 1 min | Sev 1 |
| Health Check Failed | Health endpoint | Non-200 response | 2 min | 1 min | Sev 1 |
| Very High Error Rate | Request failure % | > 20% | 5 min | 1 min | Sev 1 |
| Critical Exceptions | Exception count | > 50 | 5 min | 1 min | Sev 2 |

## Alert Severity Levels

| Severity | When to Use | Response Time |
|----------|-------------|---------------|
| Sev 0 | Critical outage affecting all users | Immediate (24/7) |
| Sev 1 | Service unavailable or major degradation | < 15 minutes |
| Sev 2 | Significant issue affecting some users | < 1 hour |
| Sev 3 | Minor issue or performance degradation | < 4 hours |
| Sev 4 | Informational, no immediate action needed | Next business day |

## Creating Alerts via Azure CLI

### Prerequisites

```bash
# Get Application Insights resource ID
AI_ID=$(az monitor app-insights component show \
  --app <APP_INSIGHTS_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --query id -o tsv)

# Get Action Group ID (for notifications)
ACTION_GROUP_ID=$(az monitor action-group show \
  --name <ACTION_GROUP_NAME> \
  --resource-group <RESOURCE_GROUP> \
  --query id -o tsv)
```

### Alert 1: High Error Rate

```bash
az monitor metrics alert create \
  --name "AI Hub - High Error Rate" \
  --resource-group <RESOURCE_GROUP> \
  --scopes $AI_ID \
  --condition "count requests > 100 where resultCode >= 500" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --action $ACTION_GROUP_ID \
  --severity 2 \
  --description "Request failure rate exceeds 5% in 5-minute window"
```

### Alert 2: Slow Response Time

```bash
az monitor metrics alert create \
  --name "AI Hub - Slow Response Time" \
  --resource-group <RESOURCE_GROUP> \
  --scopes $AI_ID \
  --condition "avg requests/duration > 3000" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --action $ACTION_GROUP_ID \
  --severity 3 \
  --description "P95 response time exceeds 3 seconds"
```

### Alert 3: Graph API Failures

```bash
az monitor metrics alert create \
  --name "AI Hub - Graph API Failures" \
  --resource-group <RESOURCE_GROUP> \
  --scopes $AI_ID \
  --condition "count dependencies > 10 where target contains 'graph.microsoft.com' and success == false" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --action $ACTION_GROUP_ID \
  --severity 2 \
  --description "More than 10 Graph API failures in 5 minutes"
```

### Alert 4: Health Check Failed

```bash
az monitor metrics alert create \
  --name "AI Hub - Health Check Failed" \
  --resource-group <RESOURCE_GROUP> \
  --scopes $AI_ID \
  --condition "count requests > 0 where name contains '/api/health' and resultCode != 200" \
  --window-size 2m \
  --evaluation-frequency 1m \
  --action $ACTION_GROUP_ID \
  --severity 1 \
  --description "Health check endpoint returning non-200 status"
```

### Alert 5: Search Unavailable

```bash
az monitor metrics alert create \
  --name "AI Hub - Search Unavailable" \
  --resource-group <RESOURCE_GROUP> \
  --scopes $AI_ID \
  --condition "count requests == 0 where name contains '/api/search' and success == true" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --action $ACTION_GROUP_ID \
  --severity 1 \
  --description "No successful search requests in 5 minutes"
```

## Creating Alerts via Azure Portal

### Step-by-Step

1. Navigate to Application Insights → Alerts
2. Click "+ Create" → "Alert rule"
3. **Scope**: Select Application Insights resource
4. **Condition**:
   - Signal: Choose metric (e.g., "Requests")
   - Operator: Greater than
   - Threshold: (e.g., 100 for error count)
   - Aggregation: Count
   - Time aggregation: 5 minutes
5. **Actions**: Select Action Group (email, SMS, webhook)
6. **Details**:
   - Severity: Choose appropriate level
   - Alert rule name: Descriptive name
   - Description: What the alert indicates
7. Review and create

## Action Groups

### Create Email Action Group

```bash
az monitor action-group create \
  --name "AI Hub Team Email" \
  --resource-group <RESOURCE_GROUP> \
  --short-name "AIHubTeam" \
  --email-receiver name="Team Email" email="team@example.com"
```

### Create Teams Webhook Action Group

```bash
az monitor action-group create \
  --name "AI Hub Teams Webhook" \
  --resource-group <RESOURCE_GROUP> \
  --short-name "AIHubTeams" \
  --webhook-receiver name="Teams Channel" service-uri="<TEAMS_WEBHOOK_URL>"
```

### Create SMS Action Group

```bash
az monitor action-group create \
  --name "AI Hub On-Call SMS" \
  --resource-group <RESOURCE_GROUP> \
  --short-name "AIHubSMS" \
  --sms-receiver name="On-Call Phone" country-code="1" phone-number="5551234567"
```

## Log-Based Alerts (Advanced)

For complex conditions not covered by metric alerts, use log-based alerts.

### Create Log Alert via CLI

```bash
az monitor scheduled-query create \
  --name "AI Hub - Repeated Exceptions" \
  --resource-group <RESOURCE_GROUP> \
  --scopes $AI_ID \
  --condition "count() > 10" \
  --condition-query "exceptions | where problemId == 'GraphAPITimeout' | summarize count()" \
  --description "More than 10 Graph API timeout exceptions" \
  --evaluation-frequency 5m \
  --window-size 15m \
  --severity 2 \
  --action-groups $ACTION_GROUP_ID
```

### Example: Anomaly Detection

```bash
az monitor scheduled-query create \
  --name "AI Hub - Request Rate Anomaly" \
  --resource-group <RESOURCE_GROUP> \
  --scopes $AI_ID \
  --condition "anomaly_rate > 2.0" \
  --condition-query "requests | summarize requestRate = count() by bin(timestamp, 5m) | where requestRate > (avg(requestRate) + 2*stdev(requestRate))" \
  --description "Request rate 2 standard deviations above normal" \
  --evaluation-frequency 5m \
  --window-size 1h \
  --severity 3 \
  --action-groups $ACTION_GROUP_ID
```

## Alert Management

### List All Alerts

```bash
az monitor metrics alert list \
  --resource-group <RESOURCE_GROUP> \
  --output table
```

### Update Alert

```bash
az monitor metrics alert update \
  --name "AI Hub - High Error Rate" \
  --resource-group <RESOURCE_GROUP> \
  --enabled true \
  --severity 1  # Upgrade severity
```

### Disable Alert (Maintenance Window)

```bash
az monitor metrics alert update \
  --name "AI Hub - High Error Rate" \
  --resource-group <RESOURCE_GROUP> \
  --enabled false
```

### Delete Alert

```bash
az monitor metrics alert delete \
  --name "AI Hub - High Error Rate" \
  --resource-group <RESOURCE_GROUP>
```

## Best Practices

### Alert Design
✅ Set thresholds based on historical baselines
✅ Use appropriate aggregation windows (5-15 minutes for most cases)
✅ Include clear descriptions and runbook links
✅ Test alerts in non-production environment first
✅ Use action groups for routing to appropriate teams

### Alert Fatigue Prevention
✅ Avoid overly sensitive thresholds
✅ Group related alerts
✅ Use severity levels appropriately
✅ Implement alert suppression for maintenance windows
✅ Review and tune alerts quarterly

### Notification Routing

| Alert Type | Recipients | Channels |
|------------|-----------|----------|
| Sev 1 | On-call engineer | SMS + Teams + Email |
| Sev 2 | Team lead | Teams + Email |
| Sev 3 | Development team | Email |
| Sev 4 | Automated logging | Log only (no notifications) |

## Troubleshooting Alerts

### Alert Not Firing

1. **Check alert is enabled**:
   ```bash
   az monitor metrics alert show --name "..." --resource-group "..." --query enabled
   ```

2. **Verify query returns data**:
   - Run alert query in Application Insights Logs
   - Check time range matches alert window

3. **Check action group**:
   ```bash
   az monitor action-group test-notifications create \
     --action-group <ACTION_GROUP_NAME> \
     --resource-group <RESOURCE_GROUP>
   ```

### Too Many Alerts Firing

1. Review thresholds (may be too sensitive)
2. Check for actual issues (alerts may be correct)
3. Increase aggregation window
4. Add additional conditions to filter noise

### Alert Delay

- Evaluation frequency determines check interval
- Minimum: 1 minute
- Increase window size for less sensitive alerts
- Use streaming alerts for near-real-time (< 1 minute)

## Alert Runbook Links

Add runbook links to alert descriptions:

```bash
az monitor metrics alert create \
  --name "AI Hub - High Error Rate" \
  --description "High error rate detected. Runbook: https://wiki.example.com/runbooks/high-error-rate" \
  ...other parameters...
```

## Example Alert Automation Script

```bash
#!/bin/bash
# setup-alerts.sh

RESOURCE_GROUP="rg-aihub-prod"
AI_NAME="appi-aihub-prod"
ACTION_GROUP="AI Hub Team"

AI_ID=$(az monitor app-insights component show --app $AI_NAME --resource-group $RESOURCE_GROUP --query id -o tsv)
ACTION_GROUP_ID=$(az monitor action-group show --name "$ACTION_GROUP" --resource-group $RESOURCE_GROUP --query id -o tsv)

# Create all alerts
alerts=(
  "High Error Rate|count requests > 100 where resultCode >= 500|5m|2"
  "Slow Response|avg requests/duration > 3000|5m|3"
  "Graph API Failures|count dependencies > 10 where target contains 'graph.microsoft.com'|5m|2"
)

for alert_config in "${alerts[@]}"; do
  IFS='|' read -r name condition window severity <<< "$alert_config"

  az monitor metrics alert create \
    --name "AI Hub - $name" \
    --resource-group $RESOURCE_GROUP \
    --scopes $AI_ID \
    --condition "$condition" \
    --window-size $window \
    --evaluation-frequency 1m \
    --action $ACTION_GROUP_ID \
    --severity $severity \
    --enabled true

  echo "Created alert: $name"
done
```

Make executable and run:
```bash
chmod +x setup-alerts.sh
./setup-alerts.sh
```
