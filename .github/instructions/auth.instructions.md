---
applyTo: "lib/auth/**/*.ts,lib/auth/**/*.tsx,app/api/auth/**/*.ts"
excludeAgent: ["code-review"]
---

# Authentication Instructions

These rules apply to authentication code under `lib/auth/` and `app/api/auth/`.

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Browser       │────▶│   Next.js       │────▶│   Entra ID      │
│   (Client)      │     │   (NextAuth)    │     │   (Azure AD)    │
└─────────────────┘     └────────┬────────┘     └─────────────────┘
                                 │
                                 ▼ OBO Flow
                        ┌─────────────────┐
                        │  Microsoft      │
                        │  Graph API      │
                        └─────────────────┘
```

## NextAuth Configuration

### Provider Setup

```typescript
// lib/auth/next-auth-config.ts
import NextAuth from 'next-auth';
import AzureADProvider from 'next-auth/providers/azure-ad';

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    AzureADProvider({
      clientId: process.env.AZURE_AD_CLIENT_ID!,
      clientSecret: process.env.AZURE_AD_CLIENT_SECRET!,
      issuer: `https://login.microsoftonline.com/${process.env.AZURE_AD_TENANT_ID}/v2.0`,
      authorization: {
        params: {
          scope: [
            'openid',
            'profile',
            'email',
            'offline_access',
            'User.Read',
            'Sites.Read.All',
            'Files.Read.All',
          ].join(' '),
        },
      },
    }),
  ],
  session: {
    strategy: 'jwt',
    maxAge: 8 * 60 * 60, // 8 hours
  },
  secret: process.env.NEXTAUTH_SECRET,
});
```

### Required Scopes

| Scope | Purpose |
|-------|---------|
| `openid` | OIDC authentication |
| `profile` | User profile info |
| `email` | User email |
| `offline_access` | Refresh tokens |
| `User.Read` | Read user profile from Graph |
| `Sites.Read.All` | Read SharePoint sites |
| `Files.Read.All` | Read files in SharePoint |

## Token Management

### JWT Callbacks

```typescript
callbacks: {
  async jwt({ token, account, profile }) {
    // Initial sign in — store tokens
    if (account && profile) {
      return {
        ...token,
        accessToken: account.access_token,
        refreshToken: account.refresh_token,
        expiresAt: account.expires_at,
      };
    }

    // Return cached token if not expired
    if (Date.now() < (token.expiresAt as number) * 1000) {
      return token;
    }

    // Token expired — refresh it
    return await refreshAccessToken(token);
  },
}
```

### Token Refresh

```typescript
async function refreshAccessToken(token: JWT): Promise<JWT> {
  try {
    const response = await fetch(
      `https://login.microsoftonline.com/${process.env.AZURE_AD_TENANT_ID}/oauth2/v2.0/token`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: new URLSearchParams({
          client_id: process.env.AZURE_AD_CLIENT_ID!,
          client_secret: process.env.AZURE_AD_CLIENT_SECRET!,
          grant_type: 'refresh_token',
          refresh_token: token.refreshToken as string,
        }),
      }
    );

    if (!response.ok) {
      throw new Error('Refresh failed');
    }

    const refreshed = await response.json();
    return {
      ...token,
      accessToken: refreshed.access_token,
      expiresAt: Math.floor(Date.now() / 1000 + refreshed.expires_in),
      refreshToken: refreshed.refresh_token ?? token.refreshToken,
    };
  } catch (error) {
    // Return token with error flag — UI should prompt re-login
    return { ...token, error: 'RefreshAccessTokenError' };
  }
}
```

## On-Behalf-Of (OBO) Flow

### When to Use OBO

Use OBO when you need to call downstream APIs (like Graph) with user-delegated permissions.

```typescript
// lib/auth/azure-ad-provider.ts

export async function getOBOAccessToken(
  userAccessToken: string,
  scopes: string[]
): Promise<string | null> {
  const response = await fetch(
    `https://login.microsoftonline.com/${process.env.AZURE_AD_TENANT_ID}/oauth2/v2.0/token`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({
        client_id: process.env.AZURE_AD_CLIENT_ID!,
        client_secret: process.env.AZURE_AD_CLIENT_SECRET!,
        grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
        assertion: userAccessToken,
        requested_token_use: 'on_behalf_of',
        scope: scopes.join(' '),
      }),
    }
  );

  if (!response.ok) return null;
  const data = await response.json();
  return data.access_token;
}
```

### Graph Token Helper

```typescript
export async function getGraphAccessToken(userAccessToken: string): Promise<string | null> {
  return getOBOAccessToken(userAccessToken, [
    'https://graph.microsoft.com/User.Read',
    'https://graph.microsoft.com/Sites.Read.All',
    'https://graph.microsoft.com/Files.Read.All',
  ]);
}
```

## Security Rules

### Never Expose Tokens

```typescript
// ✅ Good: Token stays server-side
export async function GET() {
  const session = await auth();
  const graphToken = await getGraphAccessToken(session.accessToken);
  const data = await fetchFromGraph(graphToken);
  return Response.json({ data });
}

// ❌ Bad: Token exposed to client
export async function GET() {
  const session = await auth();
  return Response.json({ token: session.accessToken }); // NEVER
}
```

### Never Log Tokens

```typescript
// ✅ Good: Log operation, not credentials
logger.info('User authenticated', { userId: session.user.id });

// ❌ Bad: Logging sensitive data
logger.info('Session', { accessToken, refreshToken }); // NEVER
```

### Session Cookie Security

```typescript
// Cookies should be:
cookies: {
  sessionToken: {
    name: 'next-auth.session-token',
    options: {
      httpOnly: true,    // Not accessible from JavaScript
      secure: true,      // HTTPS only
      sameSite: 'lax',   // CSRF protection
      path: '/',
    },
  },
}
```

## Error Handling

### Auth Error States

```typescript
// In session callback, propagate errors to client
async session({ session, token }) {
  return {
    ...session,
    error: token.error,  // 'RefreshAccessTokenError' if refresh failed
  };
}
```

### Client-Side Error Handling

```typescript
// In components, check for auth errors
const { data: session } = useSession();

if (session?.error === 'RefreshAccessTokenError') {
  // Force re-login
  signIn('azure-ad');
}
```

## Environment Variables

### Required Variables

| Variable | Description |
|----------|-------------|
| `AZURE_AD_CLIENT_ID` | Entra ID app registration client ID |
| `AZURE_AD_CLIENT_SECRET` | Entra ID app secret |
| `AZURE_AD_TENANT_ID` | Entra ID tenant ID |
| `NEXTAUTH_SECRET` | Random string for session encryption |
| `NEXTAUTH_URL` | Canonical app URL (e.g., https://app.azurewebsites.net) |

### Local Development

```bash
# .env.local (never commit)
AZURE_AD_CLIENT_ID=your-client-id
AZURE_AD_CLIENT_SECRET=your-secret
AZURE_AD_TENANT_ID=your-tenant-id
NEXTAUTH_SECRET=generate-with-openssl-rand-base64-32
NEXTAUTH_URL=http://localhost:3000
```

## Testing

### Mock Session for Tests

```typescript
// vitest.setup.ts
vi.mock('@/lib/auth/next-auth-config', () => ({
  auth: vi.fn(() => Promise.resolve({
    user: { id: 'test-user', name: 'Test User', email: 'test@example.com' },
    accessToken: 'mock-token',
  })),
}));
```

### E2E Mock Auth

See `tests/e2e/auth.setup.ts` for Playwright mock session setup.

## Module Structure

```
lib/auth/
├── next-auth-config.ts   # NextAuth setup, callbacks, session
├── azure-ad-provider.ts  # OBO flow, token exchange helpers
└── types.ts              # Extended session/token types (if needed)

app/api/auth/
└── [...nextauth]/
    └── route.ts          # NextAuth API handlers
```
