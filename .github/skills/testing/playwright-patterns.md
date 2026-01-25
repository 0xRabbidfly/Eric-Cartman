# Playwright E2E Test Patterns

Complete patterns for end-to-end testing with Playwright in the AI-HUB-Portal.

## Basic Page Navigation

```typescript
import { test, expect } from '@playwright/test';

test('navigates to home page', async ({ page }) => {
  await page.goto('/');

  await expect(page).toHaveTitle(/AI Hub/);
  await expect(page.locator('h1')).toContainText('Welcome');
});

test('navigates between pillar pages', async ({ page }) => {
  await page.goto('/');

  // Click on pillar link
  await page.click('text=People Enablement');

  // Verify navigation
  await expect(page).toHaveURL(/\/people-enablement/);
  await expect(page.locator('h1')).toContainText('People Enablement');
});

test('uses breadcrumb navigation', async ({ page }) => {
  await page.goto('/people-enablement/training-literacy');

  // Click breadcrumb to go back
  await page.click('nav[aria-label="Breadcrumb"] >> text=People Enablement');

  await expect(page).toHaveURL(/\/people-enablement$/);
});
```

## Search Flow with Authentication

```typescript
import { test, expect } from '@playwright/test';

test.describe('Search functionality', () => {
  test.beforeEach(async ({ page }) => {
    // Login (adjust based on your auth flow)
    await page.goto('/');
    await page.click('text=Sign In');
    await page.fill('[name="email"]', process.env.TEST_USER_EMAIL!);
    await page.fill('[name="password"]', process.env.TEST_USER_PASSWORD!);
    await page.click('button[type="submit"]');

    // Wait for login to complete
    await page.waitForURL('/', { timeout: 10000 });
  });

  test('performs search and displays results', async ({ page }) => {
    // Enter search query
    await page.fill('[role="searchbox"]', 'AI training');
    await page.press('[role="searchbox"]', 'Enter');

    // Wait for results
    await page.waitForLoadState('networkidle');

    // Verify results displayed
    const results = page.locator('[data-testid="search-result"]');
    await expect(results).toHaveCount.greaterThan(0);
  });

  test('filters search results by pillar', async ({ page }) => {
    await page.fill('[role="searchbox"]', 'training');
    await page.press('[role="searchbox"]', 'Enter');

    // Apply filter
    await page.click('text=People Enablement');

    // Verify filtered results
    await expect(page.locator('[data-testid="search-result"]')).toHaveCount.greaterThan(0);
    await expect(page.locator('[data-testid="active-filter"]')).toContainText('People Enablement');
  });

  test('clears search and returns to home', async ({ page }) => {
    await page.fill('[role="searchbox"]', 'test query');
    await page.press('[role="searchbox"]', 'Enter');

    // Clear search
    await page.click('[aria-label="Clear search"]');

    await expect(page.locator('[role="searchbox"]')).toHaveValue('');
  });
});
```

## Accessibility Testing

```typescript
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test.describe('Accessibility', () => {
  test('home page has no accessibility violations', async ({ page }) => {
    await page.goto('/');

    const accessibilityScanResults = await new AxeBuilder({ page }).analyze();

    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('search page has no violations', async ({ page }) => {
    await page.goto('/search?q=test');

    const accessibilityScanResults = await new AxeBuilder({ page })
      .exclude('#playwright-error-box') // Exclude dev-only elements
      .analyze();

    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('keyboard navigation works', async ({ page }) => {
    await page.goto('/');

    // Tab through interactive elements
    await page.keyboard.press('Tab'); // Focus search
    await page.keyboard.press('Tab'); // Focus first nav item
    await page.keyboard.press('Tab'); // Focus second nav item

    // Verify focus is visible
    const focused = page.locator(':focus');
    await expect(focused).toBeVisible();
  });

  test('screen reader announcements work', async ({ page }) => {
    await page.goto('/');

    // Check aria-live regions
    const liveRegion = page.locator('[aria-live="polite"]');
    await expect(liveRegion).toBeAttached();

    // Trigger search
    await page.fill('[role="searchbox"]', 'test');
    await page.press('[role="searchbox"]', 'Enter');

    // Verify announcement
    await expect(liveRegion).toContainText(/results/i);
  });
});
```

## Form Submission

```typescript
import { test, expect } from '@playwright/test';

test.describe('Contact Form', () => {
  test('submits form with valid data', async ({ page }) => {
    await page.goto('/contact');

    await page.fill('[name="name"]', 'Test User');
    await page.fill('[name="email"]', 'test@cgi.com');
    await page.fill('[name="message"]', 'This is a test message');

    await page.click('button[type="submit"]');

    // Wait for success message
    await expect(page.locator('[role="alert"]')).toContainText(/success/i);
  });

  test('shows validation errors for invalid input', async ({ page }) => {
    await page.goto('/contact');

    // Try to submit empty form
    await page.click('button[type="submit"]');

    // Verify validation errors
    await expect(page.locator('text=Name is required')).toBeVisible();
    await expect(page.locator('text=Email is required')).toBeVisible();
  });

  test('validates email format', async ({ page }) => {
    await page.goto('/contact');

    await page.fill('[name="email"]', 'invalid-email');
    await page.click('button[type="submit"]');

    await expect(page.locator('text=Invalid email')).toBeVisible();
  });
});
```

## Language Switching

```typescript
import { test, expect } from '@playwright/test';

test.describe('i18n Language Switching', () => {
  test('switches from EN to FR', async ({ page }) => {
    await page.goto('/');

    // Verify default language
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');

    // Switch to French
    await page.click('[data-testid="language-switcher"]');
    await page.click('text=Français');

    // Verify language changed
    await expect(page.locator('html')).toHaveAttribute('lang', 'fr');
    await expect(page.locator('h1')).toContainText('Bienvenue');
  });

  test('persists language preference', async ({ page, context }) => {
    await page.goto('/');

    // Switch to French
    await page.click('[data-testid="language-switcher"]');
    await page.click('text=Français');

    // Navigate to another page
    await page.goto('/people-enablement');

    // Language should still be French
    await expect(page.locator('html')).toHaveAttribute('lang', 'fr');
  });
});
```

## API Mocking

Mock API responses for consistent testing.

```typescript
import { test, expect } from '@playwright/test';

test('mocks search API response', async ({ page }) => {
  // Intercept API call and return mock data
  await page.route('**/api/search*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        results: [
          { id: '1', title: 'Mocked Result 1', url: 'https://example.com/1' },
          { id: '2', title: 'Mocked Result 2', url: 'https://example.com/2' },
        ],
        total: 2,
      }),
    });
  });

  await page.goto('/');
  await page.fill('[role="searchbox"]', 'test');
  await page.press('[role="searchbox"]', 'Enter');

  // Verify mocked results
  await expect(page.locator('text=Mocked Result 1')).toBeVisible();
  await expect(page.locator('text=Mocked Result 2')).toBeVisible();
});

test('handles API errors gracefully', async ({ page }) => {
  await page.route('**/api/search*', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'Internal server error' }),
    });
  });

  await page.goto('/');
  await page.fill('[role="searchbox"]', 'test');
  await page.press('[role="searchbox"]', 'Enter');

  await expect(page.locator('[role="alert"]')).toContainText(/error/i);
});
```

## Mobile Responsive Testing

```typescript
import { test, expect, devices } from '@playwright/test';

test.use(devices['iPhone 13']);

test('mobile navigation works', async ({ page }) => {
  await page.goto('/');

  // Open mobile menu
  await page.click('[aria-label="Menu"]');

  // Verify menu visible
  await expect(page.locator('[role="navigation"]')).toBeVisible();

  // Click nav item
  await page.click('text=People Enablement');

  await expect(page).toHaveURL(/\/people-enablement/);
});

test.use(devices['iPad Pro']);

test('tablet layout displays correctly', async ({ page }) => {
  await page.goto('/');

  const viewport = page.viewportSize();
  expect(viewport?.width).toBe(1024);

  // Verify layout adapts
  await expect(page.locator('[data-testid="sidebar"]')).toBeVisible();
});
```

## Screenshot Comparison

```typescript
import { test, expect } from '@playwright/test';

test('home page visual regression', async ({ page }) => {
  await page.goto('/');

  // Take screenshot
  await expect(page).toHaveScreenshot('home-page.png', {
    fullPage: true,
    animations: 'disabled',
  });
});

test('pillar page visual regression', async ({ page }) => {
  await page.goto('/people-enablement');

  await expect(page).toHaveScreenshot('pillar-page.png', {
    maxDiffPixels: 100, // Allow small differences
  });
});
```

## Test Fixtures (Reusable Setup)

```typescript
// fixtures.ts
import { test as base } from '@playwright/test';

type Fixtures = {
  authenticatedPage: Page;
};

export const test = base.extend<Fixtures>({
  authenticatedPage: async ({ page }, use) => {
    // Login before each test
    await page.goto('/');
    await page.click('text=Sign In');
    await page.fill('[name="email"]', process.env.TEST_USER_EMAIL!);
    await page.fill('[name="password"]', process.env.TEST_USER_PASSWORD!);
    await page.click('button[type="submit"]');
    await page.waitForURL('/');

    await use(page);

    // Logout after test
    await page.click('[aria-label="User menu"]');
    await page.click('text=Sign Out');
  },
});

// Use in tests
import { test } from './fixtures';

test('authenticated user can search', async ({ authenticatedPage }) => {
  await authenticatedPage.fill('[role="searchbox"]', 'AI');
  await authenticatedPage.press('[role="searchbox"]', 'Enter');

  await expect(authenticatedPage.locator('[data-testid="search-result"]'))
    .toHaveCount.greaterThan(0);
});
```

## Parallel Testing

```typescript
// playwright.config.ts
export default defineConfig({
  workers: process.env.CI ? 2 : 4,
  fullyParallel: true,
});

// Tests run in parallel by default
test.describe.parallel('Pillar pages', () => {
  test('people enablement loads', async ({ page }) => {
    await page.goto('/people-enablement');
    await expect(page.locator('h1')).toBeVisible();
  });

  test('sales enablement loads', async ({ page }) => {
    await page.goto('/sales-enablement');
    await expect(page.locator('h1')).toBeVisible();
  });
});
```

## Waiting Strategies

```typescript
test('waits for dynamic content', async ({ page }) => {
  await page.goto('/');

  // Wait for specific element
  await page.waitForSelector('[data-testid="content-loaded"]');

  // Wait for network to be idle
  await page.waitForLoadState('networkidle');

  // Wait for specific response
  await page.waitForResponse(response =>
    response.url().includes('/api/content') && response.status() === 200
  );

  // Custom wait condition
  await page.waitForFunction(() => document.querySelectorAll('.item').length > 10);
});
```
