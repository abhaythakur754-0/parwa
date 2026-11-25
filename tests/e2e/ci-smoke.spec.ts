import { expect, test } from '@playwright/test';

const publicRoutes = [
  { path: '/', name: 'landing' },
  { path: '/pricing', name: 'pricing' },
  { path: '/login', name: 'login' },
  { path: '/signup', name: 'signup' },
  { path: '/onboarding', name: 'onboarding' },
];

test.describe('Parwa browser smoke checks', () => {
  for (const route of publicRoutes) {
    test(`renders ${route.path} in a real Chromium browser`, async ({ page }, testInfo) => {
      const pageErrors: string[] = [];
      page.on('pageerror', (error) => pageErrors.push(error.message));

      const response = await page.goto(route.path, {
        waitUntil: 'domcontentloaded',
        timeout: 45_000,
      });

      expect(response, `No document response for ${route.path}`).not.toBeNull();
      expect(
        response!.status(),
        `Unexpected HTTP status for ${route.path}`,
      ).toBeLessThan(500);

      await page.waitForLoadState('load');
      await expect(page.locator('body')).toBeVisible();
      await expect(page.locator('body')).not.toBeEmpty();

      // The landing hero reveals its content with an IntersectionObserver and
      // a short counter animation. Wait for the finished state before capture.
      if (route.path === '/') {
        await expect(page.getByRole('heading', { name: /Human Support vs/ })).toBeVisible();
        await expect(page.getByText('92%', { exact: true })).toBeVisible({ timeout: 10_000 });
      }

      await page.screenshot({
        path: testInfo.outputPath(`${route.name}.png`),
        fullPage: true,
      });

      expect(pageErrors, `Browser runtime errors on ${route.path}`).toEqual([]);
    });
  }
});
