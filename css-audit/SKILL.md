---
name: css-audit
description: Audit components for CSS best practice violations including inline styles, missing CSS Modules, and hardcoded values. Use to enforce styling standards before PRs or during code review.
version: 1.0.0
---

# CSS Audit Skill

## Purpose

Scan React components and CSS files for violations of the project's styling standards. Identifies inline style abuse, missing CSS Module files, and hardcoded values that should use design tokens.

## When to Use

- Before submitting a PR with UI changes
- During code review of component changes
- When onboarding to understand current technical debt
- Periodic codebase health checks
- After receiving feedback about styling inconsistencies

---

## Quick Start

```
Audit the components folder for CSS violations.
Run a CSS audit on the PillarCard component.
Check this file for inline style abuse.
```

---

## What Gets Audited

### Violation Types

| Violation | Severity | Pattern |
|-----------|----------|---------|
| **Inline Style Abuse** | 🔴 Critical | `style={{` with 3+ properties |
| **Missing CSS Module** | 🔴 Critical | `.tsx` component without `.module.css` |
| **Hardcoded Colors** | 🟡 Warning | `#hexcode` or `rgb()` instead of `var(--color-*)` |
| **Hardcoded Spacing** | 🟡 Warning | `16px` instead of `var(--spacing-*)` |
| **Hardcoded Font Sizes** | 🟡 Warning | `14px` instead of `var(--font-size-*)` |
| **Mixed Style Sources** | 🔴 Critical | Same property in both className and style |

---

## Audit Workflow

### Phase 1: Scan for Inline Styles

Search for components with inline style objects:

```typescript
// Pattern to find:
style={{
  property: value,
  property: value,
  // 3+ properties = violation
}}
```

**Acceptable exceptions:**
- Single dynamic value: `style={{ width: \`${percent}%\` }}`
- Truly computed values from props/state

### Phase 2: Check CSS Module Coverage

For each component file, verify:

```
components/content/ComponentName.tsx
  └── Must have: ComponentName.module.css
```

**Report missing files.**

### Phase 3: Scan for Hardcoded Values

In both `.tsx` and `.module.css` files, find:

```css
/* Violations */
padding: 24px;           /* Should be var(--spacing-lg) */
font-size: 14px;         /* Should be var(--font-size-sm) */
color: #525252;          /* Should be var(--color-text-secondary) */
background: #ffffff;     /* Should be var(--color-surface) */
border-radius: 8px;      /* Should be var(--radius-md) */
```

---

## Output Format

### Audit Report Structure

```markdown
## 🔍 CSS Audit Report

**Scope**: [files/folders audited]
**Date**: [timestamp]

### Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | X |
| 🟡 Warning | Y |
| ✅ Clean | Z files |

### 🔴 Critical Violations

#### 1. Inline Style Abuse

**File**: `components/content/PillarCard.tsx`
**Lines**: 45-67
**Issue**: 15 inline style properties

```tsx
// Current (violation)
<div style={{ 
  padding: '16px',
  display: 'flex',
  // ... 13 more properties
}}>
```

**Fix**: Create `PillarCard.module.css` and move styles:
```css
.container {
  padding: var(--spacing-md);
  display: flex;
}
```

---

#### 2. Missing CSS Module

**File**: `components/layout/Header.tsx`
**Issue**: No `Header.module.css` exists

**Fix**: Create co-located CSS Module file.

---

### 🟡 Warnings

#### Hardcoded Values in CSS

**File**: `app/[locale]/page.module.css`
**Line 23**: `font-size: 36px` → Use `var(--font-size-4xl)`
**Line 45**: `gap: 8px` → Use `var(--spacing-sm)`

---

### ✅ Clean Files

- `components/content/Hero.tsx` + `Hero.module.css`
- `components/search/SearchBox.tsx` + `SearchBox.module.css`

---

### Recommended Actions

1. **Immediate**: Fix critical violations in PillarCard, Header
2. **This sprint**: Address all hardcoded values
3. **Ongoing**: Run audit before each PR
```

---

## Token Reference

When suggesting fixes, map to these tokens:

### Spacing (8px grid)
| Value | Token |
|-------|-------|
| 4px | `--spacing-xs` |
| 8px | `--spacing-sm` |
| 16px | `--spacing-md` |
| 24px | `--spacing-lg` |
| 32px | `--spacing-xl` |
| 48px | `--spacing-xxl` |
| 64px | `--spacing-3xl` |
| 96px | `--spacing-4xl` |

### Font Sizes
| Value | Token |
|-------|-------|
| 12px | `--font-size-xs` |
| 14px | `--font-size-sm` |
| 16px | `--font-size-md` |
| 18px | `--font-size-lg` |
| 20px | `--font-size-xl` |
| 24px | `--font-size-2xl` |
| 28px | `--font-size-3xl` |
| 36px | `--font-size-4xl` |
| 48px | `--font-size-5xl` |

### Border Radius
| Value | Token |
|-------|-------|
| 6px | `--radius-sm` |
| 10px | `--radius-md` |
| 14px | `--radius-lg` |
| 18px | `--radius-xl` |

### Common Colors
| Hex | Token |
|-----|-------|
| #ffffff | `--color-surface` |
| #fafafa | `--color-background` |
| #1a1a1a | `--color-text` |
| #525252 | `--color-text-secondary` |
| #e5e5e5 | `--color-border` |
| #E31937 | `--color-primary` |
| #0066CC | `--color-ai-blue` |

---

## Integration with Other Skills

- **After audit**: Use findings to create refactoring tasks
- **With code-review**: Reference audit results in PR feedback
- **With session-learning**: If new violation patterns emerge, update instructions

---

## Example Invocations

```
# Full codebase audit
Run a CSS audit on the entire components folder.

# Single component
Audit PillarCard.tsx for styling violations.

# Specific violation type
Find all components with inline style abuse.

# Pre-PR check
Check my changed files for CSS violations before I commit.
```
