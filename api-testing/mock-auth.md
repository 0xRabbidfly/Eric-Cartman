# Authentication Mocking Patterns

Patterns for mocking NextAuth.js authentication in API route tests.

## Mock Setup

```typescript
import { vi } from 'vitest';
import { getServerSession } from 'next-auth';

// Mock NextAuth module
vi.mock('next-auth', () => ({
  getServerSession: vi.fn()
}));
```

## Pattern 1: Authenticated User

```typescript
import { vi } from 'vitest';
import { getServerSession } from 'next-auth';

vi.mocked(getServerSession).mockResolvedValue({
  user: {
    id: 'test-user-123',
    email: 'test.user@example.com',
    name: 'Test User',
    image: null
  },
  expires: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString()
});
```

## Pattern 2: Unauthenticated (No Session)

```typescript
vi.mocked(getServerSession).mockResolvedValue(null);
```

## Pattern 3: User with Specific Roles

```typescript
vi.mocked(getServerSession).mockResolvedValue({
  user: {
    id: 'admin-user',
    email: 'admin@example.com',
    name: 'Admin User',
    roles: ['admin', 'editor']  // Custom roles
  },
  expires: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString()
});
```

## Pattern 4: Expired Session

```typescript
vi.mocked(getServerSession).mockResolvedValue({
  user: {
    id: 'test-user',
    email: 'test@example.com',
    name: 'Test User'
  },
  expires: new Date(Date.now() - 1000).toISOString()  // Expired
});
```

## Pattern 5: Per-Test Authentication

```typescript
describe('Protected API Route', () => {
  beforeEach(() => {
    // Default: authenticated user
    vi.mocked(getServerSession).mockResolvedValue({
      user: { id: '1', email: 'test@example.com', name: 'Test' },
      expires: new Date(Date.now() + 86400000).toISOString()
    });
  });

  it('should allow authenticated users', async () => {
    const response = await GET(request);
    expect(response.status).toBe(200);
  });

  it('should reject unauthenticated users', async () => {
    // Override for this test
    vi.mocked(getServerSession).mockResolvedValue(null);

    const response = await GET(request);
    expect(response.status).toBe(401);
  });
});
```

## Testing Authorization Logic

```typescript
// API route handler (example)
export async function POST(request: NextRequest) {
  const session = await getServerSession();

  if (!session) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 });
  }

  if (!session.user.roles?.includes('admin')) {
    return Response.json({ error: 'Forbidden' }, { status: 403 });
  }

  // ... admin-only logic
}

// Test
it('should reject non-admin users', async () => {
  vi.mocked(getServerSession).mockResolvedValue({
    user: {
      id: 'user-1',
      email: 'user@example.com',
      name: 'Regular User',
      roles: ['user']  // Not admin
    },
    expires: new Date(Date.now() + 86400000).toISOString()
  });

  const response = await POST(request);
  expect(response.status).toBe(403);
});
```

## Cleanup

```typescript
afterEach(() => {
  vi.clearAllMocks();
});
```

## Common Pitfalls

### ❌ Wrong: Mocking the wrong function

```typescript
vi.mock('next-auth/next', () => ({  // Incorrect path
  getServerSession: vi.fn()
}));
```

### ✅ Correct: Mock from main next-auth module

```typescript
vi.mock('next-auth', () => ({  // Correct
  getServerSession: vi.fn()
}));
```

### ❌ Wrong: Not using vi.mocked for type safety

```typescript
getServerSession.mockResolvedValue({ ... });  // No type checking
```

### ✅ Correct: Use vi.mocked for TypeScript

```typescript
vi.mocked(getServerSession).mockResolvedValue({ ... });  // Type-safe
```
