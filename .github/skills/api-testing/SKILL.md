---
name: api-testing
description: Next.js API route testing patterns for the AI-HUB-Portal. Use when testing API endpoints, debugging route handlers, validating request/response contracts, or setting up integration tests.
version: 1.0.0
---

# API Testing Skill

## Purpose

Guide testing of Next.js App Router API routes, including mock authentication, request validation, and integration testing patterns.

## When to Use

- Testing new API route handlers (in app/api/ directory)
- Debugging API endpoint failures
- Validating request/response contracts
- Setting up integration tests with database
- Testing authentication and authorization

## Quick Start

**See**: `api-test-template.ts` for complete test template

```typescript
import { POST } from '@/app/api/example/route';
import { NextRequest } from 'next/server';

describe('API Route: /api/example', () => {
  it('should return 200 with valid data', async () => {
    const request = new NextRequest('http://localhost:3000/api/example', {
      method: 'POST',
      body: JSON.stringify({ name: 'Test' })
    });

    const response = await POST(request);
    expect(response.status).toBe(200);

    const data = await response.json();
    expect(data).toHaveProperty('success', true);
  });
});
```

## API Route Patterns

### Pattern 1: GET with Query Parameters

```typescript
// app/api/pages/route.ts
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const pillarId = searchParams.get('pillarId');

  // Query database...
  return Response.json({ pages });
}

// Test
const request = new NextRequest('http://localhost:3000/api/pages?pillarId=people-enablement');
const response = await GET(request);
```

### Pattern 2: POST with Body Validation

```typescript
// Test with valid body
const response = await POST(new NextRequest(url, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ title: 'Test', route: '/test' })
}));

expect(response.status).toBe(201);
```

### Pattern 3: Protected Route (Auth Required)

**See**: `mock-auth.md` for authentication mocking patterns

```typescript
import { getServerSession } from 'next-auth';

vi.mock('next-auth', () => ({
  getServerSession: vi.fn()
}));

// Mock authenticated user
vi.mocked(getServerSession).mockResolvedValue({
  user: { email: 'test@example.com', name: 'Test User' }
});

const response = await GET(request);
expect(response.status).toBe(200);
```

## Testing Checklist

- [ ] Valid request returns 200/201
- [ ] Invalid request returns 400 with error message
- [ ] Unauthorized request returns 401
- [ ] Missing required fields returns 400
- [ ] Database errors return 500
- [ ] Response matches expected schema

## Common Assertions

```typescript
// Status codes
expect(response.status).toBe(200);

// Response body
const data = await response.json();
expect(data).toMatchObject({ success: true });

// Headers
expect(response.headers.get('Content-Type')).toBe('application/json');

// Error messages
expect(data.error).toBe('Invalid input');
```

## Integration with Database

```typescript
import { TableClient } from '@azure/data-tables';

let tableClient: TableClient;

beforeAll(() => {
  tableClient = TableClient.fromConnectionString(
    'UseDevelopmentStorage=true',
    'TestTable'
  );
});

afterEach(async () => {
  // Clean up test data
  const entities = tableClient.listEntities();
  for await (const entity of entities) {
    await tableClient.deleteEntity(entity.partitionKey, entity.rowKey);
  }
});
```

## Related Skills

- `testing` - Use for overall testing strategy
- `database` - Use for Table Storage testing patterns
- `deployment` - Use for API endpoint health checks

## Supporting Files

- `api-test-template.ts` - Complete test template for API routes
- `mock-auth.md` - Authentication and authorization mocking patterns
