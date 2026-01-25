import { test, expect } from '@playwright/test';

/**
 * i18n Language Switching E2E Test Template
 *
 * Tests that language switching works correctly across the application
 */

test.describe('i18n Language Switching', () => {

  test('should switch between EN and FR', async ({ page }) => {
    // Navigate to home page
    await page.goto('/');

    // Verify default language (EN)
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');

    // Switch to French
    await page.click('[data-testid="language-switcher"]');
    await page.click('[data-testid="language-fr"]');

    // Verify language changed
    await expect(page.locator('html')).toHaveAttribute('lang', 'fr');

    // Verify content is in French (example)
    const heading = page.locator('h1').first();
    await expect(heading).not.toContainText('Welcome'); // EN
    await expect(heading).toContainText('Bienvenue');   // FR

    // Switch back to English
    await page.click('[data-testid="language-switcher"]');
    await page.click('[data-testid="language-en"]');

    // Verify back to English
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
    await expect(heading).toContainText('Welcome');
  });

  test('should persist language preference', async ({ page, context }) => {
    await page.goto('/');

    // Switch to French
    await page.click('[data-testid="language-switcher"]');
    await page.click('[data-testid="language-fr"]');

    // Verify cookie was set
    const cookies = await context.cookies();
    const localeCookie = cookies.find(c => c.name === 'NEXT_LOCALE');
    expect(localeCookie?.value).toBe('fr');

    // Navigate to another page
    await page.goto('/people-enablement');

    // Language should still be French
    await expect(page.locator('html')).toHaveAttribute('lang', 'fr');
  });

  test('should display all navigation items in both languages', async ({ page }) => {
    await page.goto('/');

    // Check EN navigation
    const enNav = page.locator('nav');
    await expect(enNav).toContainText('Home');
    await expect(enNav).toContainText('People Enablement');

    // Switch to FR
    await page.click('[data-testid="language-switcher"]');
    await page.click('[data-testid="language-fr"]');

    // Check FR navigation
    await expect(enNav).toContainText('Accueil');
    await expect(enNav).toContainText('Habilitation des personnes');
  });

  test('should format dates according to locale', async ({ page }) => {
    await page.goto('/');

    // Get date element (adjust selector as needed)
    const dateElement = page.locator('[data-testid="last-updated"]');

    // EN format: "January 24, 2026"
    await expect(dateElement).toContainText(/[A-Z][a-z]+\s\d{1,2},\s\d{4}/);

    // Switch to FR
    await page.click('[data-testid="language-switcher"]');
    await page.click('[data-testid="language-fr"]');

    // FR format: "24 janvier 2026"
    await expect(dateElement).toContainText(/\d{1,2}\s[a-zûéè]+\s\d{4}/);
  });

});
