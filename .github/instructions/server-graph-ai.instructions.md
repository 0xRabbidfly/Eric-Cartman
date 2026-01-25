---
applyTo: "lib/server/**/*.ts,lib/server/**/*.tsx"
excludeAgent: ["code-review"]
---

# Server Integrations (Graph / Search / AI) Instructions

These rules apply to all server-side integrations under `lib/server/`.

## Microsoft Graph SDK Patterns

### Client Initialization

```typescript
// lib/server/graph/client.ts
import { Client } from '@microsoft/microsoft-graph-client';

export function getGraphClient(accessToken: string): Client {
  return Client.init({
    authProvider: (done) => {
      done(null, accessToken);
    },
  });
}

// Usage in service modules
export async function getUserProfile(accessToken: string) {
  const client = getGraphClient(accessToken);
  return client.api('/me').get();
}
```

### On-Behalf-Of (OBO) Flow

```typescript
// Always use OBO to get Graph tokens — never use app-only permissions
import { getGraphAccessToken } from '@/lib/auth/azure-ad-provider';

export async function getSharePointContent(userAccessToken: string, siteId: string) {
  // Exchange user token for Graph token
  const graphToken = await getGraphAccessToken(userAccessToken);
  if (!graphToken) {
    throw new Error('Failed to acquire Graph token');
  }

  const client = getGraphClient(graphToken);
  return client.api(`/sites/${siteId}/lists`).get();
}
```

### Security Trimming

- **All queries run under user context**: Results are automatically permission-filtered
- **Never elevate to app-only**: Unless explicitly approved and audited
- **Validate site/drive IDs**: Use allow-lists for approved SharePoint sites

```typescript
// ✅ Good: User-context query (security-trimmed)
const results = await client.api('/me/drive/root/children').get();

// ❌ Bad: App-only query (sees everything)
// Never do this without explicit security review
```

## Search Service Patterns

### Service Module Structure

```typescript
// lib/server/search/azure-ai-search.ts

export interface SearchResult {
  id: string;
  title: string;
  snippet: string;
  url: string;  // Always include canonical SharePoint URL
  score: number;
}

export interface SearchResponse {
  results: SearchResult[];
  totalCount: number;
  facets?: Record<string, FacetValue[]>;
}

export async function searchContent(
  query: string,
  options: SearchOptions
): Promise<SearchResponse> {
  // Implementation
}
```

### Link-First Results

- **Always include canonical URLs**: Every result must link to SharePoint
- **Never duplicate content**: Results are pointers, not copies

```typescript
// ✅ Good: Result with SharePoint link
{
  id: 'doc-123',
  title: 'AI Playbook',
  snippet: 'Overview of AI capabilities...',
  url: 'https://cgi.sharepoint.com/sites/ai-hub/docs/playbook.pdf',
  type: 'document'
}

// ❌ Bad: Result without source link
{
  id: 'doc-123',
  title: 'AI Playbook',
  content: '... full document content ...'  // Don't embed full content
}
```

## AI / RAG Patterns (Future)

### Retrieval Constraints

- **Only retrieve from approved sources**: Indexed SharePoint content
- **Include citations**: Every AI response must cite sources
- **Content filtering**: Never send highly confidential content to LLM

```typescript
// Future RAG pattern
export interface RAGResponse {
  answer: string;
  citations: Citation[];  // Required — never answer without sources
  confidence: number;
}

export interface Citation {
  title: string;
  url: string;          // Canonical SharePoint URL
  snippet: string;      // Relevant excerpt
}
```

### Content Allow-List

```typescript
// Only retrieve from approved document libraries
const APPROVED_SOURCES = [
  'sites/ai-hub/Shared Documents',
  'sites/ai-hub/Policies',
  'sites/ai-hub/Use Cases',
];

// Validate source before including in RAG context
function isApprovedSource(url: string): boolean {
  return APPROVED_SOURCES.some(source => url.includes(source));
}
```

## Error Handling

### Typed Error Results

```typescript
// Use discriminated unions — don't throw across service boundaries
export type ServiceResult<T> = 
  | { success: true; data: T }
  | { success: false; error: ServiceError };

export interface ServiceError {
  code: 'NOT_FOUND' | 'FORBIDDEN' | 'GRAPH_ERROR' | 'SEARCH_ERROR';
  message: string;
  details?: unknown;  // For logging only — never expose to client
}

// Usage
export async function getDocument(id: string): Promise<ServiceResult<Document>> {
  try {
    const doc = await fetchDocument(id);
    return { success: true, data: doc };
  } catch (error) {
    return { 
      success: false, 
      error: { code: 'GRAPH_ERROR', message: 'Failed to fetch document' }
    };
  }
}
```

### Error Mapping for Graph API

```typescript
// Map Graph errors to safe client responses
function mapGraphError(error: GraphError): ServiceError {
  switch (error.statusCode) {
    case 401:
      return { code: 'UNAUTHORIZED', message: 'Session expired' };
    case 403:
      return { code: 'FORBIDDEN', message: 'Access denied' };
    case 404:
      return { code: 'NOT_FOUND', message: 'Resource not found' };
    default:
      // Log full error server-side, return generic message
      logger.error('Graph API error', { error });
      return { code: 'GRAPH_ERROR', message: 'Service unavailable' };
  }
}
```

## Testability

### Dependency Injection

```typescript
// ✅ Good: Accept dependencies as parameters
export async function searchContent(
  query: string,
  searchClient: SearchClient = defaultClient
): Promise<SearchResponse> {
  return searchClient.search(query);
}

// ❌ Bad: Global singleton
const client = new SearchClient();  // Hard to mock
export async function searchContent(query: string) {
  return client.search(query);
}
```

### Mock Providers

```typescript
// Use mock providers for testing/development
const searchClient = process.env.USE_MOCK_SEARCH === 'true'
  ? new MockSearchClient()
  : new AzureSearchClient();
```

## Module Organization

```
lib/server/
├── graph/
│   ├── client.ts       # Graph client initialization
│   ├── sites.ts        # SharePoint site operations
│   ├── drives.ts       # Drive/file operations
│   └── search.ts       # Graph Search API
├── search/
│   ├── azure-ai-search.ts  # Azure AI Search client
│   ├── indexer.ts          # Content indexing
│   └── types.ts            # Search types
└── ai/
    ├── rag.ts          # RAG retrieval (future)
    └── assistant.ts    # Assistant logic (future)
```
