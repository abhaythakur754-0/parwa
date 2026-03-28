/**
 * E2E Accessibility Tests
 * WCAG 2.1 AA compliance testing with axe-core
 */

import { test, expect } from '@playwright/test';

// Axe-core import for accessibility testing
import AxeBuilder from '@axe-core/playwright';

test.describe('Accessibility (WCAG 2.1 AA)', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the application
    await page.goto('/');
  });

  test('Landing page should have no accessibility violations', async ({ page }) => {
    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze();

    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('Dashboard page should have no accessibility violations', async ({ page }) => {
    // Login first (assuming test user exists)
    await page.goto('/auth/login');
    await page.fill('input[name="email"]', 'test@example.com');
    await page.fill('input[name="password"]', 'testpassword');
    await page.click('button[type="submit"]');

    // Wait for dashboard to load
    await page.waitForURL('/dashboard');

    const accessibilityScanResults = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      .analyze();

    expect(accessibilityScanResults.violations).toEqual([]);
  });

  test('Skip link should be present and functional', async ({ page }) => {
    await page.goto('/dashboard');

    // Check skip link exists
    const skipLink = page.locator('[data-skip-link="true"]');
    await expect(skipLink).toBeVisible();

    // Tab to skip link
    await page.keyboard.press('Tab');
    await expect(skipLink).toBeFocused();

    // Press Enter to skip
    await page.keyboard.press('Enter');

    // Main content should be focused
    const mainContent = page.locator('main, [role="main"], #main-content');
    await expect(mainContent).toBeFocused();
  });

  test('All images should have alt text', async ({ page }) => {
    await page.goto('/');

    const images = await page.locator('img').all();

    for (const img of images) {
      const alt = await img.getAttribute('alt');
      const role = await img.getAttribute('role');

      // Either alt text or role="presentation" for decorative images
      expect(alt !== null || role === 'presentation').toBeTruthy();
    }
  });

  test('Form inputs should have labels', async ({ page }) => {
    await page.goto('/auth/login');

    const inputs = await page.locator('input:not([type="hidden"]):not([type="submit"])').all();

    for (const input of inputs) {
      const id = await input.getAttribute('id');
      const ariaLabel = await input.getAttribute('aria-label');
      const ariaLabelledBy = await input.getAttribute('aria-labelledby');

      if (id) {
        // Check for associated label
        const label = page.locator(`label[for="${id}"]`);
        const hasLabel = await label.count() > 0;

        expect(hasLabel || ariaLabel || ariaLabelledBy).toBeTruthy();
      } else {
        // Should have aria-label or aria-labelledby
        expect(ariaLabel || ariaLabelledBy).toBeTruthy();
      }
    }
  });

  test('Color contrast should meet WCAG AA standards', async ({ page }) => {
    await page.goto('/');

    const accessibilityScanResults = await new AxeBuilder({ page })
      .withRules(['color-contrast'])
      .analyze();

    const contrastViolations = accessibilityScanResults.violations.filter(
      (v) => v.id === 'color-contrast'
    );

    expect(contrastViolations).toEqual([]);
  });

  test('Keyboard navigation should work for main menu', async ({ page }) => {
    await page.goto('/dashboard');

    // Tab through navigation
    const focusedElements = [];

    for (let i = 0; i < 15; i++) {
      await page.keyboard.press('Tab');
      const focused = await page.evaluate(() => {
        const el = document.activeElement;
        return el ? el.tagName + (el.id ? `#${el.id}` : '') + (el.className ? `.${el.className.split(' ')[0]}` : '') : null;
      });
      if (focused) {
        focusedElements.push(focused);
      }
    }

    // Should have navigated through multiple elements
    expect(focusedElements.length).toBeGreaterThan(5);
  });

  test('Focus should be visible on all interactive elements', async ({ page }) => {
    await page.goto('/');

    const buttons = await page.locator('button').all();
    const links = await page.locator('a').all();
    const inputs = await page.locator('input, select, textarea').all();

    const interactiveElements = [...buttons, ...links, ...inputs].slice(0, 10);

    for (const element of interactiveElements) {
      await element.focus();

      // Check if focus ring is visible (via CSS class or outline)
      const hasFocusVisible = await element.evaluate((el) => {
        const style = window.getComputedStyle(el);
        return (
          style.outline !== 'none' ||
          style.boxShadow !== 'none' ||
          el.classList.contains('focus-visible') ||
          el.classList.contains('focus:ring')
        );
      });

      expect(hasFocusVisible).toBeTruthy();
    }
  });

  test('Modal should trap focus', async ({ page }) => {
    await page.goto('/dashboard');

    // Trigger modal (assuming there's a button to open it)
    const modalTrigger = page.locator('button[aria-haspopup="dialog"], [data-modal-trigger]');
    if (await modalTrigger.count() > 0) {
      await modalTrigger.first().click();

      // Wait for modal to appear
      const modal = page.locator('[role="dialog"]');
      await expect(modal).toBeVisible();

      // Tab through modal - focus should stay within
      await page.keyboard.press('Tab');
      await page.keyboard.press('Tab');
      await page.keyboard.press('Tab');

      const focusedInModal = await page.evaluate(() => {
        const modal = document.querySelector('[role="dialog"]');
        const focused = document.activeElement;
        return modal?.contains(focused);
      });

      expect(focusedInModal).toBeTruthy();

      // Escape should close modal
      await page.keyboard.press('Escape');
      await expect(modal).not.toBeVisible();
    }
  });

  test('ARIA landmarks should be present', async ({ page }) => {
    await page.goto('/');

    // Check for main landmark
    const mainLandmark = page.locator('main, [role="main"]');
    await expect(mainLandmark).toHaveCount(1);

    // Check for navigation landmark
    const navLandmark = page.locator('nav, [role="navigation"]');
    expect(await navLandmark.count()).toBeGreaterThanOrEqual(1);
  });

  test('Page should have proper heading structure', async ({ page }) => {
    await page.goto('/');

    // Should have exactly one h1
    const h1Count = await page.locator('h1').count();
    expect(h1Count).toBe(1);

    // Headings should be in proper order (no skipping levels)
    const headings = await page.locator('h1, h2, h3, h4, h5, h6').all();

    let prevLevel = 0;
    for (const heading of headings) {
      const tagName = await heading.evaluate((el) => el.tagName);
      const level = parseInt(tagName.charAt(1));

      // Should not skip more than one level
      expect(level).toBeLessThanOrEqual(prevLevel + 1);

      prevLevel = level;
    }
  });
});

test.describe('Mobile Accessibility', () => {
  test.use({ viewport: { width: 375, height: 667 } });

  test('Touch targets should be at least 44x44 pixels', async ({ page }) => {
    await page.goto('/');

    const buttons = await page.locator('button, a, input[type="button"], input[type="submit"]').all();

    for (const button of buttons.slice(0, 20)) {
      const box = await button.boundingBox();
      if (box) {
        expect(box.width).toBeGreaterThanOrEqual(44);
        expect(box.height).toBeGreaterThanOrEqual(44);
      }
    }
  });

  test('Mobile navigation should be accessible', async ({ page }) => {
    await page.goto('/dashboard');

    // Open mobile menu
    const menuButton = page.locator('[aria-label*="menu"], [aria-label*="Menu"]');
    if (await menuButton.count() > 0) {
      await menuButton.click();

      // Menu should be visible
      const menu = page.locator('[role="dialog"], [role="menu"], .mobile-menu, .drawer');
      await expect(menu.first()).toBeVisible();

      // Should be able to navigate with keyboard
      await page.keyboard.press('Tab');
      const focused = await page.evaluate(() => document.activeElement?.tagName);
      expect(focused).toBeTruthy();
    }
  });
});
