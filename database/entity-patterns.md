# Azure Table Storage Entity Design Patterns

## Pattern 1: Single Table with Entity Type Prefix (Recommended)

Use entity type as partition key prefix:

```typescript
// PortalPage entity
{
  partitionKey: 'page',
  rowKey: 'home',
  titleEn: 'Home',
  titleFr: 'Accueil',
  route: '/',
  // ...
}

// Pillar entity
{
  partitionKey: 'pillar',
  rowKey: 'people-enablement',
  nameEn: 'People Enablement',
  nameFr: 'Habilitation des personnes',
  // ...
}
```

**Pros**:
- Simple queries within entity type
- Single table to manage
- Clear entity type separation

**Cons**:
- Can't easily query across entity types
- All entities of same type in one partition

**Use when**: You primarily query by entity type

## Pattern 2: Hierarchical Partition Keys

Use parent ID as partition key:

```typescript
// Pillar (root)
{
  partitionKey: 'pillar',
  rowKey: 'people-enablement',
  // ...
}

// Subcategories under pillar
{
  partitionKey: 'people-enablement',  // pillar ID
  rowKey: 'training-literacy',
  pillarId: 'people-enablement',
  // ...
}
```

**Pros**:
- Efficient queries for all items under a parent
- Natural hierarchy representation
- Good for 1:N relationships

**Cons**:
- Partition size limits (max 20GB per partition)
- Hot partitions if one parent has many children

**Use when**: You frequently query all children of a parent

## Pattern 3: Composite Keys with Delimiters

Embed hierarchy in rowKey:

```typescript
{
  partitionKey: 'portal-config',
  rowKey: 'page:people-enablement:training-literacy',
  // ...
}
```

**Pros**:
- Flexible queries with prefix matching
- Single partition for all entities
- Can represent complex hierarchies

**Cons**:
- Requires parsing keys
- Less type-safe
- Harder to maintain

**Use when**: You need flexible querying across hierarchies

## Pattern 4: Time-Series with Reverse Timestamp

For time-series data:

```typescript
{
  partitionKey: 'user-activity',
  rowKey: `${userId}_${MAX_INT - Date.now()}`,  // Reverse chronological
  timestamp: new Date().toISOString(),
  // ...
}
```

**Pros**:
- Most recent items retrieved first
- Efficient range queries
- Good for logs/events

**Cons**:
- Complex rowKey generation
- Hot partitions if high write volume

**Use when**: You have time-series or event data

## Choosing a Pattern

| Requirement | Recommended Pattern |
|-------------|---------------------|
| Query by type frequently | Pattern 1 (Entity Type Prefix) |
| Parent-child relationships | Pattern 2 (Hierarchical) |
| Complex hierarchies | Pattern 3 (Composite Keys) |
| Time-series data | Pattern 4 (Reverse Timestamp) |
| Mixed queries | Pattern 1 + Secondary indices |

## Anti-Patterns

### ❌ Using sequential GUIDs as rowKey

```typescript
// Bad
rowKey: '00000001-0002-0003-0004-000000000005'
```

Creates hotspots as all inserts go to same partition range.

**Fix**: Use random GUIDs or meaningful identifiers

### ❌ Hot partitions

```typescript
// Bad: All users in one partition
{ partitionKey: 'user', rowKey: userId }
```

**Fix**: Distribute across partitions (hash-based partitioning)

### ❌ Large partition keys/row keys

Keys contribute to entity size (max 1MB total).

**Fix**: Keep keys concise, use references
