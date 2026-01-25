---
name: database
description: Azure Table Storage operations, schema validation, and data seeding for the AI-HUB-Portal. Use when working with data models, writing data access layer tests, seeding development data, or debugging data issues.
version: 1.0.0
---

# Database Skill

## Purpose

Guide data layer development using Azure Table Storage, including entity design, schema validation, data seeding, and testing patterns for the AI-HUB-Portal.

## When to Use

- Creating or modifying data model entities
- Writing data access layer tests
- Seeding test or development data
- Debugging data access issues
- Validating entity schema compliance
- Setting up local development environment with Azurite

## Key Entities

Based on `specs/001-portal-mvp/data-model.md`:

1. **PortalPage** - Navigation pages (home, pillar landing, subcategories)
2. **Pillar** - Four main content pillars (People, Sales, IP, Partnerships)
3. **Subcategory** - Topic areas within each pillar
4. **ContentItem** - Searchable content metadata from SharePoint/Graph

**See**: `schema-validation.ts` for complete type definitions and validation

## Quick Start

### Initialize Table Client

```typescript
import { TableClient } from '@azure/data-tables';

const connectionString = process.env.AZURE_STORAGE_CONNECTION_STRING;
const tableClient = TableClient.fromConnectionString(connectionString, 'PortalConfig');
```

### Create Entity

```typescript
const entity = {
  partitionKey: 'page',
  rowKey: 'home',
  titleEn: 'Home',
  titleFr: 'Accueil',
  route: '/',
  displayOrder: 0,
  isPublished: true,
  lastModified: new Date().toISOString(),
};

await tableClient.createEntity(entity);
```

### Query Entities

```typescript
// Get all pages
const pages = tableClient.listEntities({
  queryOptions: { filter: `PartitionKey eq 'page'` }
});

for await (const page of pages) {
  console.log(page);
}

// Get specific entity
const page = await tableClient.getEntity('page', 'home');
```

## Entity Design Pattern

**Recommended**: Use entity type as partition key prefix

```typescript
{
  partitionKey: 'page',       // Entity type
  rowKey: 'home',             // Unique ID
  // ... entity properties
}
```

**Benefits**: Simple queries, single table to manage

**See**: `entity-patterns.md` for alternative patterns (hierarchical, composite keys)

## Schema Validation

Use Zod schemas for runtime validation:

```typescript
import { validatePortalPage } from './schema-validation';

try {
  const page = validatePortalPage(entityFromTable);
  console.log('Valid page:', page);
} catch (error) {
  console.error('Invalid entity:', error);
}
```

**See**: `schema-validation.ts` for all entity schemas and validation functions

## Testing with Azurite

### Start Local Emulator

```powershell
# Install Azurite
npm install -D azurite

# Start emulator
npx azurite --location ./azurite-data --silent

# Use emulator connection string
AZURE_STORAGE_CONNECTION_STRING="UseDevelopmentStorage=true"
```

### Integration Test Example

```typescript
import { TableClient } from '@azure/data-tables';

describe('PortalPage Data Access', () => {
  let tableClient: TableClient;

  beforeAll(async () => {
    tableClient = TableClient.fromConnectionString(
      'UseDevelopmentStorage=true',
      'PortalConfigTest'
    );
    await tableClient.createTable();
  });

  afterAll(async () => {
    await tableClient.deleteTable();
  });

  it('should create a portal page', async () => {
    await tableClient.createEntity({
      partitionKey: 'page',
      rowKey: 'test',
      titleEn: 'Test Page',
      titleFr: 'Page de test',
      route: '/test',
      displayOrder: 1,
      isPublished: false,
      lastModified: new Date().toISOString(),
    });

    const retrieved = await tableClient.getEntity('page', 'test');
    expect(retrieved.titleEn).toBe('Test Page');
  });
});
```

**See**: `table-storage-guide.md` for complete CRUD examples and batch operations

## Data Seeding

### Seed Development Data

```typescript
import seedData from './seed-data/sample-content.json';

async function seedDatabase() {
  for (const pillar of seedData.pillars) {
    await tableClient.createEntity({ partitionKey: 'pillar', ...pillar });
  }

  for (const page of seedData.pages) {
    await tableClient.createEntity({ partitionKey: 'page', ...page });
  }
}
```

### Seed Scripts

```powershell
# Seed local Azurite
npm run db:seed:local

# Seed development environment
npm run db:seed:dev
```

**See**: `seed-data/sample-content.json` for sample data structure

## Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Connection string invalid | Missing/malformed env var | Use `UseDevelopmentStorage=true` for local |
| Table does not exist | Table not created | `await tableClient.createTable()` |
| Query returns no results | Incorrect filter syntax | Use `eq` not `==`, `and` not `&&` |
| Batch operation fails | Different partition keys | Group by partition key before batching |

## Best Practices

### DO:
✅ Use Azurite for local development and testing
✅ Validate entity schema before storage operations
✅ Use batch operations for multiple entities in same partition
✅ Implement optimistic concurrency with ETags for updates
✅ Seed development data with realistic content
✅ Use Zod or similar for runtime type validation

### DON'T:
❌ Store large binary data in Table Storage (use Blob Storage)
❌ Exceed 1MB per entity (hard limit)
❌ Use sequential GUIDs as row keys (creates hotspots)
❌ Store sensitive data unencrypted
❌ Query without partition key filter (full table scan)
❌ Use spaces or special characters in partition/row keys

## Related Skills

- `testing` - Use for comprehensive data layer testing
- `api-testing` - Use for testing API routes that access Table Storage
- `deployment` - Use for configuring Table Storage connection in Azure

## Workflow Integration

Typical data layer workflow:

1. **Define entity schema** → Document in `specs/001-portal-mvp/data-model.md`
2. **Create type definitions** → Use `schema-validation.ts`
3. **Write data access code** → Implement CRUD operations
4. **Write tests** → Use `testing` skill with Azurite
5. **Seed development data** → Use seed scripts
6. **Test API integration** → Use `api-testing` skill
7. **Deploy** → Use `deployment` skill for Azure configuration

## Supporting Files

- `schema-validation.ts` - Zod schemas and type guards for all entities
- `seed-data/sample-content.json` - Sample data for development/testing
- `entity-patterns.md` - Entity design patterns and trade-offs
- `table-storage-guide.md` - Complete CRUD operations and batch processing
