---
name: testing
description: Comprehensive testing workflow for Next.js App Router with Vitest, React Testing Library, and Playwright E2E tests. Use when writing tests, debugging failures, or improving coverage.
version: 1.0.0
---

# Testing Skill

## Purpose

Streamline test creation and execution for the AI-HUB-Portal Next.js application with TypeScript, Fluent UI, and NextAuth authentication.

## When to Use

- Writing new unit/integration tests for components or utilities
- Creating E2E tests for user workflows
- Debugging failing tests
- Improving test coverage
- Validating accessibility requirements

## Test Stack

| Type | Tool | Config |
|------|------|--------|
| Unit/Integration | Vitest + React Testing Library | `vitest.config.ts` |
| E2E | Playwright | `playwright.config.ts` |
| Coverage | Vitest c8 | `npm run test:coverage` |

## Quick Start

### Run Tests

```powershell
# Unit/Integration tests
npm run test              # Run all tests once
npm run test:watch        # Watch mode for development
npm run test:coverage     # Generate coverage report

# E2E tests
npx playwright test                    # Run all E2E tests
npx playwright test --ui               # Interactive UI mode
npx playwright test --debug            # Debug mode with inspector
npx playwright test tests/e2e/search   # Run specific test file
```

### Create New Test

**See**: `templates/` for complete test templates

**Unit test**:
```typescript
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

describe('ComponentName', () => {
  it('renders with required props', () => {
    render(<ComponentName title="Test" />);
    expect(screen.getByText('Test')).toBeInTheDocument();
  });
});
```

**E2E test**:
```typescript
import { test, expect } from '@playwright/test';

test('should navigate to page', async ({ page }) => {
  await page.goto('/');
  await expect(page).toHaveTitle(/AI Hub/);
});
```

**See**:
- `vitest-patterns.md` - Unit test patterns (server components, client components, hooks, API routes)
- `playwright-patterns.md` - E2E test patterns (navigation, auth, accessibility)

## Test File Organization

```
tests/
├── unit/                          # Unit tests (mirror app structure)
│   ├── components/
│   │   ├── layout/
│   │   └── content/
│   ├── lib/
│   └── app/
├── integration/                   # Integration tests
│   └── api/
└── e2e/                          # Playwright E2E tests
    ├── navigation.spec.ts
    ├── search.spec.ts
    └── accessibility.spec.ts
```

**Naming convention**: `[component-name].test.tsx` for unit, `[feature].spec.ts` for E2E

## Coverage Targets

From project requirements:

| Metric | Target | Current |
|--------|--------|---------|
| Statements | > 80% | Run `npm run test:coverage` |
| Branches | > 75% | |
| Functions | > 80% | |
| Lines | > 80% | |

**Focus areas**: Components, utilities, API routes

**Exclude**: Config files, type definitions, test files

## Mock Authentication

For testing protected routes and API endpoints:

```typescript
import { getServerSession } from 'next-auth';
import { vi } from 'vitest';

vi.mock('next-auth', () => ({
  getServerSession: vi.fn()
}));

// Mock authenticated user
vi.mocked(getServerSession).mockResolvedValue({
  user: { email: 'test@133t.com', name: 'Test User' }
});
```

**See**: `api-testing` skill for complete authentication mocking patterns

## Troubleshooting

### Test fails with "Cannot find module '@/...'"

**Cause**: Path alias not configured in test setup

**Fix**: Check `vitest.config.ts` has correct path mappings:
```typescript
resolve: {
  alias: {
    '@': path.resolve(__dirname, './'),
  }
}
```

### Fluent UI component not rendering

**Cause**: Missing FluentProvider wrapper

**Fix**: Wrap in provider:
```typescript
render(
  <FluentProvider theme={webLightTheme}>
    <YourComponent />
  </FluentProvider>
);
```

### E2E test times out waiting for element

**Cause**: Element not appearing or slow page load

**Fix**:
1. Increase timeout: `await page.waitForSelector('...', { timeout: 10000 })`
2. Check element actually exists in DOM
3. Use `page.waitForLoadState('networkidle')`

### Mock not being applied

**Cause**: Mock defined after import

**Fix**: Define mocks before imports:
```typescript
vi.mock('module-name');
import { ComponentUsingMock } from './component';
```

## Best Practices

### DO:
✅ Test user-facing behavior, not implementation
✅ Use semantic queries (`getByRole`, `getByLabelText`)
✅ Mock external dependencies (APIs, auth, database)
✅ Run tests in CI/CD pipeline
✅ Keep tests focused and independent
✅ Use descriptive test names

### DON'T:
❌ Test implementation details (component state, props drilling)
❌ Use `getByTestId` unless absolutely necessary
❌ Write tests that depend on other tests
❌ Mock everything (test real integration when possible)
❌ Ignore accessibility in tests

## Related Skills

- `code-review` - Validates test coverage before merge
- `api-testing` - Use for API route testing patterns
- `deployment` - Use to configure CI/CD test execution
- `i18n` - Use for bilingual testing patterns

## Workflow Integration

Typical testing workflow:

1. **Write code** → Implement feature/fix
2. **Write tests** → Use appropriate pattern from this skill
3. **Run tests locally** → `npm run test:watch`
4. **Check coverage** → `npm run test:coverage`
5. **Commit** → CI/CD runs tests automatically
6. **Code review** → Reviewer checks test coverage
7. **Deploy** → E2E tests run in staging

## Supporting Files

- `vitest-patterns.md` - Unit test patterns for all component types
- `playwright-patterns.md` - E2E test patterns and examples
- `templates/unit-test.template.ts` - Boilerplate unit test
- `templates/component-test.template.tsx` - React component test
- `templates/e2e-test.template.ts` - Playwright E2E test
