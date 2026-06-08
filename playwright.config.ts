import { defineConfig, devices } from '@playwright/test';

/**
 * PARWA Playwright Configuration
 *
 * Run tests:
 *   npx playwright test
 *   npx playwright test --ui
 *   npx playwright test --headed
 *
 * Against deployed site:
 *   npx playwright test
 *
 * Against local dev server:
 *   BASE_URL=http://localhost:3000 npx playwright test
 */

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : 1,
  timeout: 60000,
  expect: {
    timeout: 15000,
  },
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list'],
  ],
  use: {
    baseURL: process.env.BASE_URL || 'https://parwa.vercel.app',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15000,
    navigationTimeout: 45000,
  },

  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // No webServer configured — we test against the deployed site
  // or a manually started dev server
});
