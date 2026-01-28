# Azure Table Storage Complete Guide

## CRUD Operations

### Create (Insert)

```typescript
const entity = {
  partitionKey: 'page',
  rowKey: 'about',
  titleEn: 'About Us',
  titleFr: 'À propos de nous',
  route: '/about',
  displayOrder: 5,
  isPublished: true,
  lastModified: new Date().toISOString(),
};

await tableClient.createEntity(entity);
```

### Read (Query)

```typescript
// Get single entity
const entity = await tableClient.getEntity('page', 'about');

// List all entities in partition
const pages = tableClient.listEntities({
  queryOptions: { filter: `PartitionKey eq 'page'` }
});

for await (const page of pages) {
  console.log(page);
}

// Query with multiple filters
const publishedPages = tableClient.listEntities({
  queryOptions: {
    filter: `PartitionKey eq 'page' and isPublished eq true`,
    select: ['rowKey', 'titleEn', 'route']  // Only return specific properties
  }
});

// Top N results
const recentPages = tableClient.listEntities({
  queryOptions: {
    filter: `PartitionKey eq 'page'`,
    top: 10
  }
});
```

### Update

```typescript
// Merge (partial update)
await tableClient.updateEntity({
  partitionKey: 'page',
  rowKey: 'about',
  titleEn: 'About Our Project',  // Update this field
  lastModified: new Date().toISOString()
}, 'Merge');

// Replace (full update)
const entity = await tableClient.getEntity('page', 'about');
entity.titleEn = 'About Our Project';
entity.lastModified = new Date().toISOString();

await tableClient.updateEntity(entity, 'Replace');
```

### Update with Optimistic Concurrency

```typescript
const entity = await tableClient.getEntity('page', 'about');

// Modify entity
entity.titleEn = 'Updated Title';
entity.lastModified = new Date().toISOString();

// Update with ETag check
try {
  await tableClient.updateEntity(entity, 'Merge', { etag: entity.etag });
} catch (error) {
  if (error.statusCode === 412) {
    console.error('Concurrency conflict: Entity was modified by another process');
  }
}
```

### Delete

```typescript
await tableClient.deleteEntity('page', 'about');

// Delete with ETag check
await tableClient.deleteEntity('page', 'about', { etag: entity.etag });
```

## Batch Operations

Batch operations are atomic (all succeed or all fail) and limited to 100 operations.

**Important**: All entities in a batch must have the same partition key.

```typescript
import { TableTransaction } from '@azure/data-tables';

const transaction = new TableTransaction();

// Add operations to batch
transaction.createEntity({ partitionKey: 'page', rowKey: '1', titleEn: 'Page 1' });
transaction.createEntity({ partitionKey: 'page', rowKey: '2', titleEn: 'Page 2' });
transaction.updateEntity({ partitionKey: 'page', rowKey: '3', titleEn: 'Updated' }, 'Merge');
transaction.deleteEntity('page', '4');

// Submit batch
await tableClient.submitTransaction(transaction.actions);
```

### Batch with Error Handling

```typescript
try {
  await tableClient.submitTransaction(transaction.actions);
  console.log('Batch completed successfully');
} catch (error) {
  console.error('Batch failed:', error);
  // All operations rolled back
}
```

### Batching Large Sets

```typescript
async function batchInsert(entities: any[]) {
  // Group by partition key
  const grouped = entities.reduce((acc, entity) => {
    const key = entity.partitionKey;
    if (!acc[key]) acc[key] = [];
    acc[key].push(entity);
    return acc;
  }, {});

  // Batch each partition (max 100 per batch)
  for (const [partitionKey, partitionEntities] of Object.entries(grouped)) {
    // Chunk into batches of 100
    for (let i = 0; i < partitionEntities.length; i += 100) {
      const batch = partitionEntities.slice(i, i + 100);
      const transaction = new TableTransaction();

      batch.forEach(entity => transaction.createEntity(entity));
      await tableClient.submitTransaction(transaction.actions);
    }
  }
}
```

## Query Filters

### Filter Operators

| Operator | Example |
|----------|---------|
| `eq` | `PartitionKey eq 'page'` |
| `ne` | `isPublished ne false` |
| `gt` | `displayOrder gt 5` |
| `ge` | `displayOrder ge 5` |
| `lt` | `displayOrder lt 10` |
| `le` | `displayOrder le 10` |
| `and` | `PartitionKey eq 'page' and isPublished eq true` |
| `or` | `pillarId eq 'people' or pillarId eq 'sales'` |
| `not` | `not (isPublished eq false)` |

### String Functions

```typescript
// Starts with
filter: `startswith(titleEn, 'AI')`

// Substring
filter: `substringof('Hub', titleEn)`

// Combine with other filters
filter: `PartitionKey eq 'page' and startswith(route, '/people')`
```

### Common Query Patterns

```typescript
// Get all published pages
const query = {
  filter: `PartitionKey eq 'page' and isPublished eq true`
};

// Get pages in a specific pillar
const query = {
  filter: `PartitionKey eq 'page' and pillarId eq 'people-enablement'`
};

// Get recent items (if you have lastModified timestamp)
const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
const query = {
  filter: `PartitionKey eq 'content' and lastModified gt datetime'${yesterday}'`
};
```

## Error Handling

```typescript
import { RestError } from '@azure/core-rest-pipeline';

async function safeGetEntity(partitionKey: string, rowKey: string) {
  try {
    return await tableClient.getEntity(partitionKey, rowKey);
  } catch (error) {
    if (error instanceof RestError) {
      switch (error.statusCode) {
        case 404:
          console.log('Entity not found');
          return null;
        case 412:
          console.error('Concurrency conflict (ETag mismatch)');
          throw error;
        case 503:
          console.error('Service unavailable, retry');
          // Implement retry logic
          break;
        default:
          console.error(`Unexpected error: ${error.statusCode}`);
          throw error;
      }
    }
    throw error;
  }
}
```

## Retry Logic

```typescript
async function createEntityWithRetry(entity: any, maxRetries = 3) {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      await tableClient.createEntity(entity);
      return;
    } catch (error) {
      if (attempt === maxRetries) throw error;

      // Exponential backoff
      const delay = 1000 * Math.pow(2, attempt - 1);
      console.log(`Attempt ${attempt} failed, retrying in ${delay}ms...`);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
}
```

## Performance Tips

1. **Use partition key in queries**: Avoid full table scans
   ```typescript
   // Good
   filter: `PartitionKey eq 'page' and rowKey eq 'home'`

   // Bad (full table scan)
   filter: `rowKey eq 'home'`
   ```

2. **Select only needed properties**:
   ```typescript
   queryOptions: {
     filter: `PartitionKey eq 'page'`,
     select: ['rowKey', 'titleEn', 'route']  // Only get what you need
   }
   ```

3. **Use batch operations**: Up to 100x faster than individual operations

4. **Pagination for large result sets**:
   ```typescript
   const iterator = tableClient.listEntities({ queryOptions: { filter, top: 1000 } });
   for await (const page of iterator.byPage()) {
     for (const entity of page) {
       // Process entity
     }
   }
   ```

5. **Cache frequently accessed entities**: Store in memory or Redis
