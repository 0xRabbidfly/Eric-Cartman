# CGI Brand Guidelines — AI Hub Portal

This document defines the CGI brand guidelines for the Canada AI Hub Portal. Reference this file from agents and design documents to maintain consistency.

## Brand Tone

- **Confident, modern, insights-driven** — not playful
- **Calm and premium** — professional internal tool, not consumer app
- Clean neutral surfaces with strong typographic hierarchy
- Generous whitespace, card-based discovery patterns

## Brand Values

| Value | Application in Design |
|-------|----------------------|
| **Efficiency** | Minimize steps to complete tasks |
| **Clarity** | Clear information hierarchy, no ambiguity |
| **Trust** | Consistent patterns, predictable behavior |
| **Professionalism** | Enterprise-grade polish, not flashy |

## Visual Direction

- Purposeful imagery (innovation, teams, technology themes)
- Minimal UI chrome — let content breathe
- Avoid busy backgrounds behind text
- Do NOT copy public CGI web designs verbatim — use high-level patterns only

## Color Palette

### Primary — CGI Red

Use sparingly for primary CTAs and brand accents only.

| Token | Value | Usage |
|-------|-------|-------|
| `--color-cgi-red` | #E31937 | Primary brand color, main CTAs |
| `--color-cgi-red-dark` | #C01530 | Hover states |
| `--color-cgi-red-light` | #FF3D5C | Light variant |
| `--color-cgi-red-subtle` | #FFE8EC | Subtle backgrounds, badges |

### AI Accent — Blue

Use for AI/tech indicators and secondary actions.

| Token | Value | Usage |
|-------|-------|-------|
| `--color-ai-blue` | #0066CC | AI elements, tech indicators |
| `--color-ai-blue-light` | #3399FF | Light variant |
| `--color-ai-blue-subtle` | #E6F2FF | Subtle backgrounds |

### Neutrals — Professional Grays

Majority of the UI uses neutral tones.

| Token | Value | Usage |
|-------|-------|-------|
| `--color-neutral-50` | #fafafa | Page backgrounds |
| `--color-neutral-100` | #f5f5f5 | Card backgrounds, hover states |
| `--color-neutral-200` | #e5e5e5 | Borders, dividers |
| `--color-neutral-400` | #a3a3a3 | Disabled states |
| `--color-neutral-500` | #737373 | Placeholder text |
| `--color-neutral-600` | #525252 | Secondary text |
| `--color-neutral-800` | #262626 | Primary text |
| `--color-neutral-900` | #171717 | Headings |

### Semantic Colors

Never use brand colors for semantic meaning.

| Token | Value | Usage |
|-------|-------|-------|
| `--color-error` | #DC2626 | Error states (NOT brand red) |
| `--color-success` | #16A34A | Success states |
| `--color-warning` | #EA580C | Warning states |
| `--color-info` | #0284C7 | Informational states |

## Color Usage Rules

1. **CGI Red** — Primary CTAs, active navigation, brand accents only
2. **AI Blue** — AI/tech indicators, assistant UI, secondary actions
3. **Neutrals** — All surfaces, text, borders (majority of UI)
4. **Never** use brand red for errors (use semantic `--color-error`)
5. **WCAG AA contrast required** for all text

## Typography

### Font Family

```css
font-family: 'Segoe UI', 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
```

### Type Scale

| Purpose | Size | Weight | Token |
|---------|------|--------|-------|
| Hero title | 48px | Bold | `--font-size-5xl` |
| Page title | 36-40px | Bold | `--font-size-4xl` |
| Section title | 24-28px | Semibold | `--font-size-2xl` to `--font-size-3xl` |
| Card title | 16-18px | Semibold | `--font-size-md` to `--font-size-lg` |
| Body | 14-16px | Normal | `--font-size-sm` to `--font-size-md` |
| Meta/caption | 12-13px | Normal | `--font-size-xs` |

### Line Length

Target 70-90 characters for body paragraphs.

## Spacing

8px baseline grid with consistent increments.

| Token | Value | Usage |
|-------|-------|-------|
| `--spacing-xs` | 4px | Tight inline spacing |
| `--spacing-sm` | 8px | Inline elements, small gaps |
| `--spacing-md` | 16px | Component internal padding |
| `--spacing-lg` | 24px | Card padding, gutters |
| `--spacing-xl` | 32px | Section internal spacing |
| `--spacing-xxl` | 48px | Between page sections |
| `--spacing-3xl` | 64px | Major section margins |
| `--spacing-4xl` | 96px | Hero/page divisions |

## Shape & Elevation

### Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--radius-sm` | 6px | Small elements, badges |
| `--radius-md` | 10px | Cards, inputs |
| `--radius-lg` | 14px | Large cards |
| `--radius-xl` | 18px | Hero sections |

### Shadows

| Token | Usage |
|-------|-------|
| `--shadow-sm` | Default cards, subtle elevation |
| `--shadow-md` | Hover states, raised elements |
| `--shadow-lg` | Modals, drawers |
| `--shadow-primary` | CGI red glow for brand hover states |

## Motion

### Timing

| Token | Duration | Usage |
|-------|----------|-------|
| `--transition-fast` | 120ms | Hover, quick state changes |
| `--transition-normal` | 200ms | Panel transitions, modals |
| `--transition-slow` | 300ms | Page transitions |

### Easing

```css
cubic-bezier(0.4, 0, 0.2, 1)
```

### Motion Principles

- **Functional, not decorative** — Motion serves a purpose
- **Crisp, not floaty** — Prefer snappy transitions
- **Respect user preferences** — Honor `prefers-reduced-motion`

## Layout

### Grid System

- 12 columns with 24px gutters
- Max container width: 1440px
- Content centered on page

### Key Dimensions

| Element | Value |
|---------|-------|
| Header height | 72px |
| Left rail width | 280px |
| Max content width | 1440px |

### Breakpoints

| Breakpoint | Width | Description |
|------------|-------|-------------|
| Desktop | 1440px | Full layout |
| Tablet landscape | 1024px | Adjusted grid |
| Tablet portrait | 768px | Stacked layout |
| Mobile | 480px | Single column |

## Navigation Structure

### Four Pillars

| Pillar | Purpose |
|--------|---------|
| **People Enablement** | Training, tools access, responsible AI |
| **Sales Enablement** | Playbooks, POVs, use case library |
| **IP & Solutions** | Reusable assets, offerings, frameworks |
| **Partnerships** | Strategic partners, engagement models |

### Navigation Depth

- Maximum 3-4 levels deep
- Breadcrumbs on detail pages
- Left rail for in-page navigation

## Accessibility

- **WCAG AA compliance** required
- Keyboard navigation for all interactive elements
- Visible focus states (2px primary color outline)
- ARIA labels for icon-only buttons
- Color not the only indicator of state
- Touch targets minimum 44x44px on mobile
- Respect `prefers-reduced-motion`
