---
applyTo: "app/**/*.tsx,components/**/*.tsx,src/**/*.tsx"
excludeAgent: ["code-review"]
---

# UI (React/Next.js) Instructions

These rules apply to all React components in the portal.

## Component Structure

### Server Component (Default)

```tsx
// components/content/PillarCard.tsx
import { Text, Card } from '@fluentui/react-components';
import { useTranslations } from 'next-intl';
import styles from './PillarCard.module.css';

interface PillarCardProps {
  pillar: 'people' | 'sales' | 'ip' | 'partnerships';
  href: string;
}

export function PillarCard({ pillar, href }: PillarCardProps) {
  const t = useTranslations('pillars');
  
  return (
    <Card className={styles.card} as="article">
      <Text as="h3" weight="semibold">{t(`${pillar}.title`)}</Text>
      <Text as="p">{t(`${pillar}.description`)}</Text>
      <a href={href} className={styles.link}>{t('explore')}</a>
    </Card>
  );
}
```

### Client Component (Only When Needed)

```tsx
// components/search/SearchInput.tsx
'use client';

import { useState, useCallback } from 'react';
import { Input, Button } from '@fluentui/react-components';
import { Search24Regular } from '@fluentui/react-icons';
import { useTranslations } from 'next-intl';
import styles from './SearchInput.module.css';

interface SearchInputProps {
  onSearch: (query: string) => void;
}

export function SearchInput({ onSearch }: SearchInputProps) {
  const [query, setQuery] = useState('');
  const t = useTranslations('search');

  const handleSubmit = useCallback(() => {
    if (query.trim()) {
      onSearch(query.trim());
    }
  }, [query, onSearch]);

  return (
    <div className={styles.container}>
      <Input
        value={query}
        onChange={(e, data) => setQuery(data.value)}
        placeholder={t('placeholder')}
        contentBefore={<Search24Regular />}
        aria-label={t('ariaLabel')}
      />
      <Button appearance="primary" onClick={handleSubmit}>
        {t('submit')}
      </Button>
    </div>
  );
}
```

## Fluent UI Usage

### Preferred Components

| Use Case | Fluent Component |
|----------|------------------|
| Container | `<Card>` |
| Text | `<Text>` with `as` prop for semantics |
| Buttons | `<Button appearance="primary|subtle|transparent">` |
| Input | `<Input>`, `<Textarea>` |
| Loading | `<Skeleton>`, `<Spinner>` |
| Overlays | `<Dialog>`, `<Drawer>` |
| Menus | `<Menu>`, `<MenuList>`, `<MenuItem>` |
| Icons | `@fluentui/react-icons` (e.g., `Search24Regular`) |

### Token Usage

```tsx
// ✅ Good: Use Fluent tokens via makeStyles or CSS variables
import { makeStyles, tokens } from '@fluentui/react-components';

const useStyles = makeStyles({
  card: {
    backgroundColor: tokens.colorNeutralBackground1,
    borderRadius: tokens.borderRadiusMedium,
    padding: tokens.spacingVerticalL,
  },
});

// ✅ Also good: CSS custom properties in module.css
.card {
  background-color: var(--colorNeutralBackground1);
  border-radius: var(--borderRadiusMedium);
}
```

## CSS Modules

### File Naming

```
components/
├── content/
│   ├── Hero.tsx
│   ├── Hero.module.css   # Co-located styles
│   ├── PillarCard.tsx
│   └── PillarCard.module.css
```

### Style Ownership Rule

**One source of truth per component**:
- Use CSS Modules for scoped styles
- Use `styles/globals.css` for design tokens and resets only
- Use inline styles only for truly dynamic values from props

```tsx
// ✅ Good: CSS Module for static styles
<div className={styles.container}>

// ✅ Good: Inline for dynamic values
<div style={{ gridColumn: `span ${columns}` }}>

// ❌ Bad: Mixing both for same property
<div className={styles.container} style={{ padding: '16px' }}>
```

## Internationalization (i18n)

### All Strings from Messages

```tsx
// ✅ Good: Use translations
const t = useTranslations('search');
return <Button>{t('submit')}</Button>;

// ❌ Bad: Hardcoded English
return <Button>Submit</Button>;
```

### Message File Structure

```json
// messages/en.json
{
  "search": {
    "placeholder": "Search AI resources...",
    "submit": "Search",
    "noResults": "No results found",
    "ariaLabel": "Search input"
  },
  "pillars": {
    "people": {
      "title": "People Enablement",
      "description": "Training, tools, and responsible AI"
    }
  }
}
```

## Accessibility

### Required Patterns

```tsx
// Keyboard navigation
<Button onKeyDown={(e) => e.key === 'Enter' && handleAction()}>

// Focus management
const inputRef = useRef<HTMLInputElement>(null);
useEffect(() => inputRef.current?.focus(), []);

// ARIA for custom controls
<div 
  role="button" 
  tabIndex={0}
  aria-label={t('toggleMenu')}
  aria-expanded={isOpen}
>

// Visible focus (handled by Fluent, but verify)
:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
```

### Semantic HTML

```tsx
// ✅ Good: Semantic structure
<main>
  <article>
    <h1>{title}</h1>
    <section aria-labelledby="featured">
      <h2 id="featured">{t('featured')}</h2>
    </section>
  </article>
</main>

// ❌ Bad: Div soup
<div className="main">
  <div className="content">
    <div className="title">{title}</div>
  </div>
</div>
```

## State Management

### Prefer URL State for Navigation

```tsx
// ✅ Good: Filter state in URL
import { useSearchParams } from 'next/navigation';

const searchParams = useSearchParams();
const pillar = searchParams.get('pillar');

// ❌ Bad: Local state for URL-worthy data
const [pillar, setPillar] = useState('sales');
```

### Local State for UI Only

```tsx
// ✅ Good: UI state stays local
const [isMenuOpen, setIsMenuOpen] = useState(false);
const [isHovered, setIsHovered] = useState(false);
```

## Component API Design

### Explicit Props

```typescript
// ✅ Good: Typed, documented props
interface ContentCardProps {
  /** Card title */
  title: string;
  /** Short description (1-2 lines) */
  description?: string;
  /** Pillar this content belongs to */
  pillar: PillarType;
  /** Click handler for card action */
  onOpen: () => void;
}

// ❌ Bad: any or missing types
interface ContentCardProps {
  data: any;
}
```

### Composition Over Props Drilling

```tsx
// ✅ Good: Composition
<Card>
  <CardHeader>{title}</CardHeader>
  <CardBody>{children}</CardBody>
</Card>

// ❌ Bad: Prop drilling
<Card title={title} body={body} footer={footer} headerIcon={icon} ... />
```

## Loading & Error States

### Required States

Every data-driven component needs:
- **Loading**: Skeleton or spinner
- **Empty**: Helpful message with action
- **Error**: User-safe message with retry

```tsx
function ContentList({ items, isLoading, error }: ContentListProps) {
  if (isLoading) {
    return <Skeleton />;
  }

  if (error) {
    return (
      <ErrorState 
        message={t('error.loadFailed')} 
        onRetry={refetch} 
      />
    );
  }

  if (items.length === 0) {
    return (
      <EmptyState 
        message={t('empty.noContent')} 
        action={{ label: t('empty.browse'), href: '/browse' }}
      />
    );
  }

  return <ul>{items.map(item => <ContentCard key={item.id} {...item} />)}</ul>;
}
```

## Component Organization

```
components/
├── content/      # Content display (Hero, Cards, Sections)
├── layout/       # Page structure (Header, Footer, LeftRail)
├── navigation/   # Nav elements (Breadcrumbs, LanguageToggle)
├── search/       # Search UI (Input, Results, Filters)
├── journey/      # AI Journey visualization
└── ui/           # Base components (Button, Input wrappers)
```
