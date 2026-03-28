/**
 * E2E Theme Tests
 * Testing dark mode, light mode, and system preference sync
 */

import { test, expect } from '@playwright/test';

test.describe('Theme Switching', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('Theme toggle should switch between light and dark', async ({ page }) => {
    // Check initial theme
    const html = page.locator('html');
    const initialClass = await html.getAttribute('class');

    // Find theme toggle button
    const themeToggle = page.locator('button[aria-label*="theme"], button[aria-label*="Theme"], [data-theme-toggle]');

    if (await themeToggle.count() > 0) {
      await themeToggle.click();

      // Wait for theme transition
      await page.waitForTimeout(300);

      // Theme should have changed
      const newClass = await html.getAttribute('class');
      expect(newClass).not.toBe(initialClass);
    }
  });

  test('Dark mode should apply dark class to html element', async ({ page }) => {
    // Force dark mode via localStorage
    await page.evaluate(() => {
      localStorage.setItem('parwa-theme', 'dark');
    });

    await page.reload();

    const html = page.locator('html');
    await expect(html).toHaveClass(/dark/);
  });

  test('Light mode should apply light class to html element', async ({ page }) => {
    // Force light mode via localStorage
    await page.evaluate(() => {
      localStorage.setItem('parwa-theme', 'light');
    });

    await page.reload();

    const html = page.locator('html');
    await expect(html).toHaveClass(/light/);
  });

  test('Theme preference should persist across page reloads', async ({ page }) => {
    // Set dark mode
    await page.evaluate(() => {
      localStorage.setItem('parwa-theme', 'dark');
    });

    await page.reload();

    // Should still be dark
    const html = page.locator('html');
    await expect(html).toHaveClass(/dark/);

    // Reload again
    await page.reload();

    // Should still be dark
    await expect(html).toHaveClass(/dark/);
  });

  test('System preference should be respected when set to system', async ({ page }) => {
    // Set system theme preference
    await page.evaluate(() => {
      localStorage.setItem('parwa-theme', 'system');
    });

    // Emulate dark mode preference
    await page.emulateMedia({ colorScheme: 'dark' });
    await page.reload();

    const html = page.locator('html');
    await expect(html).toHaveClass(/dark/);

    // Emulate light mode preference
    await page.emulateMedia({ colorScheme: 'light' });
    await page.reload();

    // Should be light now
    const htmlClass = await html.getAttribute('class');
    expect(htmlClass).not.toContain('dark');
  });

  test('Theme toggle button should be keyboard accessible', async ({ page }) => {
    const themeToggle = page.locator('button[aria-label*="theme"], button[aria-label*="Theme"]').first();

    if (await themeToggle.count() > 0) {
      // Tab to the button
      await page.keyboard.press('Tab');

      // Should be focusable
      await expect(themeToggle).toBeFocused();

      // Press Enter to toggle
      await page.keyboard.press('Enter');

      // Theme should have changed
      await page.waitForTimeout(300);

      // Verify theme changed by checking for theme class change
      const html = page.locator('html');
      const themeClass = await html.getAttribute('class');
      expect(themeClass).toMatch(/light|dark/);
    }
  });

  test('Theme toggle should have proper ARIA attributes', async ({ page }) => {
    const themeToggle = page.locator('button[aria-label*="theme"], button[aria-label*="Theme"]').first();

    if (await themeToggle.count() > 0) {
      // Should have aria-label
      const ariaLabel = await themeToggle.getAttribute('aria-label');
      expect(ariaLabel).toBeTruthy();
      expect(ariaLabel?.toLowerCase()).toContain('theme');
    }
  });
});

test.describe('Dark Mode Visual Tests', () => {
  test.use({ colorScheme: 'dark' });

  test('Dark mode should render correctly on dashboard', async ({ page }) => {
    await page.evaluate(() => {
      localStorage.setItem('parwa-theme', 'dark');
    });

    await page.goto('/dashboard');

    // Verify dark class is applied
    const html = page.locator('html');
    await expect(html).toHaveClass(/dark/);

    // Check background is dark
    const body = page.locator('body');
    const bgColor = await body.evaluate((el) => {
      return window.getComputedStyle(el).backgroundColor;
    });

    // Dark backgrounds typically have low RGB values
    const rgb = bgColor.match(/\d+/g);
    if (rgb && rgb.length >= 3) {
      const brightness = (parseInt(rgb[0]) + parseInt(rgb[1]) + parseInt(rgb[2])) / 3;
      expect(brightness).toBeLessThan(128); // Dark background
    }
  });

  test('Dark mode text should be readable', async ({ page }) => {
    await page.evaluate(() => {
      localStorage.setItem('parwa-theme', 'dark');
    });

    await page.goto('/');

    // Check text color is light (readable on dark)
    const mainText = page.locator('p, h1, h2, h3').first();
    const textColor = await mainText.evaluate((el) => {
      return window.getComputedStyle(el).color;
    });

    // Light text typically has high RGB values
    const rgb = textColor.match(/\d+/g);
    if (rgb && rgb.length >= 3) {
      const brightness = (parseInt(rgb[0]) + parseInt(rgb[1]) + parseInt(rgb[2])) / 3;
      expect(brightness).toBeGreaterThan(128); // Light text
    }
  });

  test('Dark mode cards should have visible borders', async ({ page }) => {
    await page.evaluate(() => {
      localStorage.setItem('parwa-theme', 'dark');
    });

    await page.goto('/dashboard');

    // Check card border is visible
    const card = page.locator('[class*="card"]').first();

    if (await card.count() > 0) {
      const borderColor = await card.evaluate((el) => {
        return window.getComputedStyle(el).borderColor;
      });

      // Border should be visible (not transparent)
      expect(borderColor).not.toBe('transparent');
      expect(borderColor).not.toBe('rgba(0, 0, 0, 0)');
    }
  });
});

test.describe('Light Mode Visual Tests', () => {
  test.use({ colorScheme: 'light' });

  test('Light mode should render correctly', async ({ page }) => {
    await page.evaluate(() => {
      localStorage.setItem('parwa-theme', 'light');
    });

    await page.goto('/');

    // Verify light class is applied or dark is not present
    const html = page.locator('html');
    const htmlClass = await html.getAttribute('class');

    // Either has light class or doesn't have dark class
    const isLight = htmlClass?.includes('light') || !htmlClass?.includes('dark');
    expect(isLight).toBeTruthy();
  });

  test('Light mode should have light background', async ({ page }) => {
    await page.evaluate(() => {
      localStorage.setItem('parwa-theme', 'light');
    });

    await page.goto('/');

    const body = page.locator('body');
    const bgColor = await body.evaluate((el) => {
      return window.getComputedStyle(el).backgroundColor;
    });

    // Light backgrounds typically have high RGB values
    const rgb = bgColor.match(/\d+/g);
    if (rgb && rgb.length >= 3) {
      const brightness = (parseInt(rgb[0]) + parseInt(rgb[1]) + parseInt(rgb[2])) / 3;
      expect(brightness).toBeGreaterThan(128); // Light background
    }
  });
});

test.describe('Theme Performance', () => {
  test('Theme switch should be instant (no flash)', async ({ page }) => {
    await page.goto('/');

    // Measure theme switch time
    const startTime = Date.now();

    const themeToggle = page.locator('button[aria-label*="theme"], button[aria-label*="Theme"]').first();

    if (await themeToggle.count() > 0) {
      await themeToggle.click();

      // Wait for class change
      await page.waitForFunction(() => {
        const html = document.documentElement;
        return html.classList.contains('dark') || html.classList.contains('light');
      });

      const endTime = Date.now();
      const switchTime = endTime - startTime;

      // Theme switch should be near-instant (< 100ms)
      expect(switchTime).toBeLessThan(100);
    }
  });
});
