---
name: monitoring
description: Application Insights monitoring and observability for the AI-HUB-Portal. Use when investigating errors, analyzing performance, or setting up alerts.
version: 1.0.0
---

# Monitoring Skill

## Purpose

Query Application Insights for error tracking, performance analysis, and operational health of the AI-HUB-Portal, with a focus on Graph API integration and search functionality.

## When to Use

- Investigating production errors or exceptions
- Analyzing page load and API response times
- Tracking Graph API failures and SharePoint access issues
- Setting up or reviewing alerts
- Debugging with correlation IDs
- Reviewing user journey analytics

## Performance Targets

From project requirements:

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Page Load Time | < 2s | > 3s |
| API Response (P95) | < 500ms | > 1s |
| Search Query Time | < 1s | > 2s |
| Error Rate | < 1% | > 5% |
| Availability | 99.5% | < 99% |

## Quick Start

### Access Application Insights

1. Azure Portal → Application Insights → AI-HUB-Portal
2. Navigate to **Logs** section
3. Run KQL queries in query editor

### Common Queries

**Recent Exceptions**:
```kql
exceptions
| where timestamp > ago(24h)
| order by timestamp desc
| take 100
```

**Graph API Failures**:
```kql
dependencies
| where timestamp > ago(24h)
| where target contains "graph.microsoft.com"
| where success == false
| order by timestamp desc
```

**Slow Page Loads**:
```kql
pageViews
| where timestamp > ago(24h)
| where duration > 2000  // > 2s
| summarize count() by name
```

**See**: `kql-queries.md` for complete query library organized by category

### Debug with Correlation ID

When a user reports an issue:

1. Get correlation ID from browser network tab (look for `operation_Id` header)
2. Run full trace query:
   ```kql
   union requests, dependencies, exceptions, traces
   | where operation_Id == "<CORRELATION_ID>"
   | order by timestamp asc
   | project timestamp, itemType, name, success, resultCode, message
   ```

## Troubleshooting Runbooks

### High Error Rate

1. Query recent exceptions:
   ```kql
   exceptions | where timestamp > ago(15m) | order by timestamp desc | take 50
   ```
2. Check if Graph API is failing (external dependency)
3. Check if Search service is healthy
4. Review recent deployments

### Slow Performance

1. Check P95 latency trend
2. Identify slow endpoints:
   ```kql
   requests | where timestamp > ago(1h) | where duration > 2000 | summarize count() by name
   ```
3. Check downstream dependencies (Graph, Search, Table Storage)
4. Review cold start frequency

### User Reports Issue

1. Get user's correlation ID from their browser network tab
2. Run full trace query with correlation ID (see above)
3. Identify failure point in request chain
4. Check user's permissions if Graph-related

## Alerts

### Recommended Alerts

| Alert | Condition | Severity |
|-------|-----------|----------|
| High Error Rate | > 5% requests failed in 5m | Sev 2 |
| Slow Response | P95 latency > 3s for 5m | Sev 3 |
| Graph API Failures | > 10 Graph failures in 5m | Sev 2 |
| Search Unavailable | 0 successful searches in 5m | Sev 1 |
| Health Check Failed | Health endpoint returns non-200 | Sev 1 |

**See**: `alert-configurations.md` for complete alert setup guide

### Create Alert via Azure CLI

```bash
az monitor metrics alert create \
  --name "High Error Rate" \
  --resource-group <RESOURCE_GROUP> \
  --scopes <APP_INSIGHTS_ID> \
  --condition "count requests > 100 where resultCode >= 500" \
  --window-size 5m \
  --evaluation-frequency 1m \
  --severity 2
```

## Dashboards

### Create Monitoring Dashboard

1. Navigate to Application Insights → Workbooks
2. Create new workbook with sections:
   - **Overview**: Request rate, error rate, response time
   - **Graph API**: Success rate, latency by endpoint
   - **Search**: Query volume, latency, error rate
   - **User Activity**: Active users, page views by page

### Key Metrics to Display

- Request Rate (last hour)
- Error Rate percentage
- P95 Response Time
- Graph API success rate
- Search query performance

**See**: `kql-queries.md` for dashboard query examples

## Log Levels

Application uses structured logging with these levels:

| Level | Use Case | Examples |
|-------|----------|----------|
| Error | Unexpected failures | Graph API 500, unhandled exceptions |
| Warning | Recoverable issues | Rate limiting, retry attempts |
| Info | Key operations | Search executed, user authenticated |
| Debug | Detailed tracing | Request/response payloads (non-prod only) |

Query by level:
```kql
traces
| where timestamp > ago(1h)
| where severityLevel >= 3  // Warning and above
| project timestamp, message, severityLevel, operation_Id
```

## Best Practices

### DO:
✅ Always include correlation IDs in error reports
✅ Use time filters in queries (e.g., `ago(24h)`)
✅ Set up proactive alerts for critical metrics
✅ Monitor Graph API and Search dependencies separately
✅ Review dashboards daily for trends
✅ Document incident investigations

### DON'T:
❌ Query without time filters (can be slow/expensive)
❌ Ignore warning-level logs (often precede errors)
❌ Set alert thresholds too sensitive (alert fatigue)
❌ Check only errors (monitor performance proactively)

## Related Skills

- `deployment` - Use after deployments to verify health
- `testing` - Use to identify test coverage gaps based on production errors
- `ci-cd` - Integrate health checks into deployment pipelines

## Workflow Integration

Typical monitoring workflow:

1. **Proactive**: Review dashboards daily for trends
2. **Alert fires** → Check runbook for that alert type
3. **Run diagnostic queries** → Identify root cause
4. **Fix issue** → Deploy fix using `deployment` skill
5. **Verify fix** → Monitor metrics return to normal
6. **Document** → Update runbook if new issue type

## Supporting Files

- `kql-queries.md` - Complete KQL query library organized by category
- `alert-configurations.md` - Detailed alert setup guide with Azure CLI commands
