# Application Insights KQL Query Library

Complete reference of Kusto Query Language (KQL) queries for monitoring the AI-HUB-Portal.

## Error Investigation

### Recent Exceptions

```kql
exceptions
| where timestamp > ago(24h)
| order by timestamp desc
| project timestamp, problemId, outerMessage, innermostMessage,
          operation_Id, user_AuthenticatedId
| take 100
```

### Exceptions by Type

```kql
exceptions
| where timestamp > ago(7d)
| summarize count() by problemId
| order by count_ desc
| take 20
```

### Exception with Full Stack Trace

```kql
exceptions
| where operation_Id == "<CORRELATION_ID>"
| project timestamp, problemId, outerMessage, innermostMessage,
          details, customDimensions
```

### Exception Trend Over Time

```kql
exceptions
| where timestamp > ago(7d)
| summarize count() by bin(timestamp, 1h), problemId
| render timechart
```

## Graph API Monitoring

### Graph API Failures

```kql
dependencies
| where timestamp > ago(24h)
| where target contains "graph.microsoft.com"
| where success == false
| project timestamp, name, resultCode, duration, operation_Id,
          customDimensions.correlationId
| order by timestamp desc
```

### Graph API Latency (P50, P95, P99)

```kql
dependencies
| where timestamp > ago(1h)
| where target contains "graph.microsoft.com"
| summarize
    p50 = percentile(duration, 50),
    p95 = percentile(duration, 95),
    p99 = percentile(duration, 99),
    count = count()
  by bin(timestamp, 5m)
| render timechart
```

### Graph API by Endpoint

```kql
dependencies
| where timestamp > ago(24h)
| where target contains "graph.microsoft.com"
| extend endpoint = tostring(split(name, " ")[1])
| summarize
    calls = count(),
    failures = countif(success == false),
    avgDuration = avg(duration)
  by endpoint
| order by calls desc
```

### Graph API Success Rate

```kql
dependencies
| where timestamp > ago(24h)
| where target contains "graph.microsoft.com"
| summarize
    total = count(),
    failures = countif(success == false),
    successRate = round(100.0 * countif(success == true) / count(), 2)
  by bin(timestamp, 15m)
| render timechart
```

## Search Performance

### Search Query Performance

```kql
requests
| where timestamp > ago(24h)
| where name contains "/api/search"
| summarize
    p50 = percentile(duration, 50),
    p95 = percentile(duration, 95),
    count = count()
  by bin(timestamp, 15m)
| render timechart
```

### Slow Search Queries

```kql
requests
| where timestamp > ago(24h)
| where name contains "/api/search"
| where duration > 2000  // > 2 seconds
| project timestamp, duration, operation_Id,
          customDimensions.query
| order by duration desc
```

### Search Error Rate

```kql
requests
| where timestamp > ago(24h)
| where name contains "/api/search"
| summarize
    total = count(),
    errors = countif(resultCode >= 400),
    errorRate = round(100.0 * countif(resultCode >= 400) / count(), 2)
  by bin(timestamp, 1h)
| render timechart
```

### Search Query Distribution

```kql
requests
| where timestamp > ago(24h)
| where name contains "/api/search"
| extend query = tostring(customDimensions.query)
| summarize count() by query
| order by count_ desc
| take 20
```

## Page Performance

### Page Load Times

```kql
pageViews
| where timestamp > ago(24h)
| summarize
    p50 = percentile(duration, 50),
    p95 = percentile(duration, 95),
    count = count()
  by name
| order by count desc
```

### Slow Page Loads (> 2s target)

```kql
pageViews
| where timestamp > ago(24h)
| where duration > 2000
| summarize count() by name
| order by count_ desc
```

### Page Views by User

```kql
pageViews
| where timestamp > ago(24h)
| summarize pageViews = count(), uniquePages = dcount(name)
  by user_AuthenticatedId
| order by pageViews desc
| take 50
```

## Correlation ID Tracing

### Full Request Trace

```kql
union requests, dependencies, exceptions, traces
| where operation_Id == "<CORRELATION_ID>"
| order by timestamp asc
| project timestamp, itemType, name, success, resultCode, message
```

### User Session Trace

```kql
union requests, pageViews, dependencies
| where user_Id == "<USER_ID>"
| where timestamp > ago(1d)
| order by timestamp asc
| project timestamp, itemType, name, url, duration
```

### Request with All Dependencies

```kql
let operationId = "<CORRELATION_ID>";
requests
| where operation_Id == operationId
| join kind=leftouter (
    dependencies
    | where operation_Id == operationId
) on operation_Id
| project timestamp, requestName = name, requestDuration = duration,
          dependencyName = name1, dependencyDuration = duration1, dependencySuccess = success1
```

## Availability & Health

### Health Check Status

```kql
requests
| where timestamp > ago(24h)
| where name contains "/api/health"
| summarize
    total = count(),
    failures = countif(success == false),
    availability = round(100.0 * countif(success == true) / count(), 2)
  by bin(timestamp, 5m)
| render timechart
```

### Overall Availability

```kql
requests
| where timestamp > ago(24h)
| summarize
    total = count(),
    failures = countif(success == false),
    availability = round(100.0 * countif(success == true) / count(), 2)
```

### Failed Requests by Endpoint

```kql
requests
| where timestamp > ago(24h)
| where success == false
| summarize count() by name, resultCode
| order by count_ desc
```

## User Analytics

### Active Users

```kql
pageViews
| where timestamp > ago(24h)
| summarize uniqueUsers = dcount(user_AuthenticatedId)
  by bin(timestamp, 1h)
| render timechart
```

### Top Pages

```kql
pageViews
| where timestamp > ago(7d)
| summarize views = count(), uniqueUsers = dcount(user_AuthenticatedId)
  by name
| order by views desc
| take 20
```

### User Journey Analysis

```kql
pageViews
| where timestamp > ago(24h)
| where user_AuthenticatedId != ""
| order by user_AuthenticatedId, timestamp asc
| project user_AuthenticatedId, timestamp, name
```

## Dashboard Queries

### Request Rate (Last Hour)

```kql
requests
| where timestamp > ago(1h)
| summarize count() by bin(timestamp, 1m)
| render timechart
```

### Error Rate Percentage

```kql
requests
| where timestamp > ago(1h)
| summarize errorRate = round(100.0 * countif(success == false) / count(), 2)
```

### P95 Response Time

```kql
requests
| where timestamp > ago(1h)
| summarize percentile(duration, 95)
```

### Dependency Health

```kql
dependencies
| where timestamp > ago(1h)
| summarize
    calls = count(),
    failures = countif(success == false),
    successRate = round(100.0 * countif(success == true) / count(), 2)
  by target
| order by calls desc
```

## Custom Logs

### Query by Severity Level

```kql
traces
| where timestamp > ago(1h)
| where severityLevel >= 3  // Warning and above (0=Verbose, 1=Info, 2=Warning, 3=Error, 4=Critical)
| project timestamp, message, severityLevel, operation_Id, customDimensions
| order by timestamp desc
```

### Custom Dimension Query

```kql
traces
| where timestamp > ago(24h)
| extend userId = tostring(customDimensions.userId)
| extend action = tostring(customDimensions.action)
| where action == "search"
| summarize count() by userId
| order by count_ desc
```

## Performance Optimization

### Slowest Operations

```kql
requests
| where timestamp > ago(24h)
| top 100 by duration desc
| project timestamp, name, duration, url, resultCode, operation_Id
```

### Operations Exceeding SLA

```kql
requests
| where timestamp > ago(24h)
| extend slaTarget = case(
    name contains "/api/", 500,  // API: 500ms
    name contains "/search", 1000,  // Search: 1s
    2000  // Pages: 2s
)
| where duration > slaTarget
| summarize count() by name, bin(timestamp, 1h)
| render timechart
```
