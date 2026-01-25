---
applyTo: "app/api/**/*.ts,app/api/**/*.tsx"
excludeAgent: ["code-review"]
---

# API Route Handler Instructions

These rules apply to all Next.js API route handlers under `app/api/`.

## Route Handler Structure

```typescript
// app/api/[resource]/route.ts

import { NextRequest } from 'next/server';
import { auth } from '@/lib/auth/next-auth-config';
import { logger } from '@/lib/utils/logger';
import { getOrCreateCorrelationId } from '@/lib/utils/correlation';
import { createSuccessResponse, createErrorResponse, ErrorCodes } from '@/lib/utils/api-helpers';
import { z } from 'zod';

// Input validation schema
const RequestSchema = z.object({
  query: z.string().min(1).max(500),
  locale: z.enum(['en', 'fr']).optional().default('en'),
});

export async function POST(request: NextRequest) {
  const correlationId = getOrCreateCorrelationId(request);
  logger.setContext({ correlationId });

  try {
    // 1. Authentication check
    const session = await auth();
    if (!session) {
      return createErrorResponse(ErrorCodes.UNAUTHORIZED, 'Authentication required', 401);
    }

    // 2. Parse and validate input
    const body = await request.json();
    const parsed = RequestSchema.safeParse(body);
    if (!parsed.success) {
      return createErrorResponse(ErrorCodes.VALIDATION_ERROR, parsed.error.message, 400);
    }

    // 3. Business logic
    const result = await doSomething(parsed.data);

    // 4. Return typed response
    return createSuccessResponse(result);

  } catch (error) {
    logger.error('Request failed', { error, correlationId });
    return createErrorResponse(ErrorCodes.INTERNAL_ERROR, 'An error occurred', 500);
  }
}
```

## Input Validation

- **Treat all inputs as untrusted**: Validate and sanitize query/body/params
- **Use Zod schemas**: Define explicit schemas for all request bodies
- **Enforce allow-lists**: For siteIds, driveIds, library paths — never accept arbitrary IDs

```typescript
// ✅ Good: Allow-list validation
const ALLOWED_SITES = ['site-a', 'site-b', 'site-c'];
if (!ALLOWED_SITES.includes(siteId)) {
  return createErrorResponse(ErrorCodes.FORBIDDEN, 'Invalid site', 403);
}

// ❌ Bad: Accepting any siteId
const siteId = body.siteId; // Never trust this directly
```

## Authentication & Authorization

- **Always check session**: Use `auth()` from `@/lib/auth/next-auth-config`
- **Use delegated access**: Access Microsoft Graph under user context (OBO flow)
- **Never return tokens**: Do not expose access tokens to the client

```typescript
// ✅ Good: Get user's Graph token server-side
const session = await auth();
const graphToken = await getGraphAccessToken(session.accessToken);
const results = await callGraph(graphToken); // Server-side only

// ❌ Bad: Returning tokens to client
return Response.json({ token: session.accessToken }); // NEVER do this
```

## Response Format

- **Use discriminated unions**: Success/error responses must be distinguishable

```typescript
// Success response
{ "success": true, "data": { ... } }

// Error response
{ "success": false, "error": { "code": "VALIDATION_ERROR", "message": "..." } }
```

- **Use correct HTTP status codes**:
  - `200` — Success
  - `400` — Validation error, bad request
  - `401` — Not authenticated
  - `403` — Forbidden (authenticated but not authorized)
  - `404` — Resource not found
  - `500` — Internal server error

## Logging & Correlation

- **Generate/read correlation ID**: Use `getOrCreateCorrelationId(request)`
- **Include in all logs**: Pass correlationId to logger context
- **Never log sensitive data**:

```typescript
// ✅ Good: Log operation metadata
logger.info('Search executed', { query: sanitized, resultCount: results.length, correlationId });

// ❌ Bad: Logging secrets or PII
logger.info('Request', { accessToken, userEmail, rawBody }); // NEVER
```

## Caching

- **Cache only public data**: Navigation structure, static content
- **Never cache user-specific results**: Permissioned search results, user preferences
- **Set appropriate headers**:

```typescript
// Public data — can cache
return new Response(JSON.stringify(data), {
  headers: { 'Cache-Control': 'public, max-age=300' }
});

// User-specific — no caching
return new Response(JSON.stringify(data), {
  headers: { 'Cache-Control': 'private, no-store' }
});
```

## Error Handling

- **Never expose stack traces**: Clients see generic messages only
- **Log full error server-side**: Include stack trace, context

```typescript
try {
  // operation
} catch (error) {
  // Log full details server-side
  logger.error('Operation failed', { 
    error: error instanceof Error ? error.stack : error,
    correlationId 
  });
  
  // Return safe message to client
  return createErrorResponse(ErrorCodes.INTERNAL_ERROR, 'An error occurred', 500);
}
```

## Existing API Routes Reference

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/auth/*` | GET/POST | NextAuth authentication handlers |
| `/api/search` | POST | Search content with filters |
| `/api/content/*` | GET | Fetch content metadata |
| `/api/contacts` | GET | Fetch AI Hub contacts |
| `/api/pages/*` | GET | Fetch page metadata |
| `/api/health` | GET | Health check endpoint |
