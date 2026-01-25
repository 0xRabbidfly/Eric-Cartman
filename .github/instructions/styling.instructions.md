---
applyTo: "**/*.module.css,**/*.css,styles/**/*"
excludeAgent: ["code-review"]
---

# Styling Instructions

These rules apply to all CSS files, CSS Modules, and styling code.

## Architecture Overview

```
styles/
└── globals.css          # Design tokens, resets, utility classes

components/
├── content/
│   ├── Hero.tsx
│   └── Hero.module.css   # Co-located component styles
├── layout/
│   ├── Header.tsx
│   └── (styles in globals.css for global layout)
```

## CSS Modules (Component Styles)

### File Naming & Location

```
# ✅ Good: Co-located with component
components/content/PillarCard.tsx
components/content/PillarCard.module.css

# ❌ Bad: Separate styles folder
components/content/PillarCard.tsx
styles/components/PillarCard.css
```

### Basic Pattern

```css
/* PillarCard.module.css */

.card {
  background-color: var(--color-surface);
  border-radius: var(--radius-md);
  padding: var(--spacing-lg);
  border: 1px solid var(--color-border);
  transition: box-shadow var(--transition-fast), 
              border-color var(--transition-fast);
}

.card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--color-primary);
}

.title {
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text);
  margin-bottom: var(--spacing-sm);
}

.description {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: var(--line-height-relaxed);
}
```

### Usage in Components

```tsx
import styles from './PillarCard.module.css';

export function PillarCard({ title, description }: Props) {
  return (
    <article className={styles.card}>
      <h3 className={styles.title}>{title}</h3>
      <p className={styles.description}>{description}</p>
    </article>
  );
}
```

## Design Tokens (Use Variables)

### Always Use CSS Variables

```css
/* ✅ Good: Using design tokens */
.card {
  padding: var(--spacing-lg);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  color: var(--color-text);
}

/* ❌ Bad: Hardcoded values */
.card {
  padding: 24px;
  border-radius: 10px;
  background: #ffffff;
  color: #1a1a1a;
}
```

### Available Token Categories

| Category | Examples |
|----------|----------|
| **Spacing** | `--spacing-xs` (4px) → `--spacing-4xl` (96px) |
| **Colors** | `--color-primary`, `--color-text`, `--color-surface` |
| **Typography** | `--font-size-sm`, `--font-weight-semibold` |
| **Radius** | `--radius-sm` (6px) → `--radius-xl` (18px) |
| **Shadows** | `--shadow-sm` → `--shadow-2xl` |
| **Transitions** | `--transition-fast` (120ms), `--transition-normal` (200ms) |

## Color Usage

### CGI Brand Palette

```css
/* Primary - CGI Red (use sparingly) */
--color-cgi-red: #E31937;        /* Primary CTAs, brand accents */
--color-cgi-red-dark: #C01530;   /* Hover states */
--color-cgi-red-subtle: #FFE8EC; /* Subtle backgrounds */

/* AI Accent - Blue (tech/AI elements) */
--color-ai-blue: #0066CC;
--color-ai-blue-subtle: #E6F2FF;

/* Neutrals - Primary UI (most of the interface) */
--color-neutral-50: #fafafa;   /* Page background */
--color-neutral-100: #f5f5f5;  /* Card backgrounds */
--color-neutral-200: #e5e5e5;  /* Borders */
--color-neutral-600: #525252;  /* Secondary text */
--color-neutral-800: #262626;  /* Primary text */
```

### Color Rules

```css
/* ✅ Good: Semantic color usage */
.button-primary {
  background: var(--color-primary);      /* CGI Red for primary CTA */
}

.ai-indicator {
  color: var(--color-ai-blue);           /* Blue for AI elements */
}

.error-message {
  color: var(--color-error);             /* Semantic error, NOT brand red */
}

/* ❌ Bad: Brand red for errors */
.error-message {
  color: var(--color-cgi-red);           /* Don't use brand color for errors */
}
```

## Spacing System (8px Grid)

### Spacing Scale

```css
--spacing-xs: 4px;    /* Tight spacing */
--spacing-sm: 8px;    /* Inline elements */
--spacing-md: 16px;   /* Component padding */
--spacing-lg: 24px;   /* Section spacing */
--spacing-xl: 32px;   /* Large gaps */
--spacing-xxl: 48px;  /* Section margins */
--spacing-3xl: 64px;  /* Page sections */
--spacing-4xl: 96px;  /* Major divisions */
```

### Usage Pattern

```css
.section {
  padding: var(--spacing-3xl) 0;       /* Vertical section padding */
}

.card {
  padding: var(--spacing-lg);          /* Internal card padding */
  gap: var(--spacing-md);              /* Space between elements */
}

.button-group {
  gap: var(--spacing-sm);              /* Tight button spacing */
}
```

## Typography

### Font Scale

```css
--font-size-xs: 12px;   /* Meta, captions */
--font-size-sm: 14px;   /* Body small, labels */
--font-size-md: 16px;   /* Body default */
--font-size-lg: 18px;   /* Large body, card titles */
--font-size-xl: 20px;   /* Subheadings */
--font-size-2xl: 24px;  /* Section titles */
--font-size-3xl: 28px;  /* Page subtitles */
--font-size-4xl: 36px;  /* Page titles */
--font-size-5xl: 48px;  /* Hero titles */
```

### Typography Pattern

```css
.pageTitle {
  font-size: var(--font-size-4xl);
  font-weight: var(--font-weight-bold);
  line-height: var(--line-height-tight);
  letter-spacing: -0.01em;
}

.sectionTitle {
  font-size: var(--font-size-2xl);
  font-weight: var(--font-weight-semibold);
  margin-bottom: var(--spacing-lg);
}

.body {
  font-size: var(--font-size-md);
  line-height: var(--line-height-relaxed);
  color: var(--color-text-secondary);
}
```

## Interactive States

### Hover, Focus, Active

```css
.card {
  transition: box-shadow var(--transition-fast),
              border-color var(--transition-fast),
              transform var(--transition-fast);
}

.card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--color-primary);
}

.card:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.card:active {
  transform: scale(0.98);
}
```

### CGI Red Glow (Brand Accent)

```css
/* Use for primary CTAs on hover */
.primaryButton:hover {
  box-shadow: var(--shadow-primary);  /* 0 0 0 3px rgba(227,25,55,0.1) */
}

.primaryButton:focus-visible {
  box-shadow: var(--shadow-primary-lg);
}
```

## Responsive Design

### Breakpoints

```css
/* Desktop-first approach */
@media (max-width: 1440px) { /* Large desktop */ }
@media (max-width: 1024px) { /* Tablet landscape */ }
@media (max-width: 768px)  { /* Tablet portrait / Mobile */ }
@media (max-width: 480px)  { /* Small mobile */ }
```

### Responsive Pattern

```css
.grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-lg);
}

@media (max-width: 1024px) {
  .grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .grid {
    grid-template-columns: 1fr;
    gap: var(--spacing-md);
  }
}
```

## Animations & Motion

### Timing

```css
--transition-fast: 120ms cubic-bezier(0.4, 0, 0.2, 1);   /* Hover states */
--transition-normal: 200ms cubic-bezier(0.4, 0, 0.2, 1); /* Panels, modals */
--transition-slow: 300ms cubic-bezier(0.4, 0, 0.2, 1);   /* Page transitions */
```

### Motion Rules

```css
/* ✅ Good: Functional motion */
.panel {
  transition: transform var(--transition-normal);
}

/* ❌ Bad: Decorative/distracting motion */
.logo {
  animation: bounce 1s infinite;  /* Avoid */
}
```

### Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

## Accessibility

### Focus Visibility

```css
/* Always provide visible focus */
:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

/* Never remove focus without replacement */
/* ❌ Bad */
:focus { outline: none; }
```

### Contrast

- Text on white: Use `--color-text` (#1a1a1a) or `--color-text-secondary` (#525252)
- Text on colored backgrounds: Verify WCAG AA contrast (4.5:1 for normal text)

## Anti-Patterns

### Don't Mix Style Sources

```tsx
// ❌ Bad: Mixing CSS Modules + inline for same property
<div className={styles.card} style={{ padding: '20px' }}>

// ✅ Good: One source of truth
<div className={styles.card}>
```

### Don't Override Fluent UI Inline

```tsx
// ❌ Bad: Fighting Fluent styles
<Button style={{ backgroundColor: 'red' }}>

// ✅ Good: Use Fluent's appearance prop
<Button appearance="primary">
```

### Don't Create One-Off Values

```css
/* ❌ Bad: Magic numbers */
.special-card {
  padding: 22px;
  border-radius: 7px;
  margin-top: 37px;
}

/* ✅ Good: Use token scale */
.special-card {
  padding: var(--spacing-lg);
  border-radius: var(--radius-md);
  margin-top: var(--spacing-xl);
}
```

## File Organization

```
styles/
└── globals.css          # Tokens, resets, global layout, utilities

components/
├── content/
│   ├── Hero.module.css
│   ├── PillarCard.module.css
│   └── ContentCard.module.css
├── layout/
│   └── LeftRail.module.css
└── search/
    ├── SearchInput.module.css
    └── SearchResults.module.css

app/
└── [locale]/
    └── page.module.css   # Page-specific styles
```
