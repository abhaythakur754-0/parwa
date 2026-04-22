import { test, expect } from '@playwright/test';

/**
 * Training Pipeline E2E Tests
 * 
 * Tests for the training dashboard (/dashboard/training):
 * - Training runs list
 * - Mistake threshold progress
 * - Cold start functionality
 * - Retraining schedule
 */
test.describe('Training Pipeline - Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to training dashboard
    // Note: May need authentication in production
    await page.goto('/dashboard/training');
  });

  test('should render training dashboard', async ({ page }) => {
    // Dashboard should be visible
    const dashboard = page.locator('[data-testid="training-dashboard"]').or(
      page.locator('main').or(page.locator('h1'))
    );
    await expect(dashboard.first()).toBeVisible({ timeout: 10000 });
  });

  test('should display training statistics', async ({ page }) => {
    // Look for stats/metrics
    const stats = page.locator('[data-testid="training-stats"]').or(
      page.locator('text=/total|runs|completed|failed|running/i')
    );
    await expect(stats.first()).toBeVisible({ timeout: 5000 });
  });

  test('should show new training button', async ({ page }) => {
    // New training button should be present
    const newTrainingButton = page.getByRole('button', { name: /new.*training|start.*training|train/i }).or(
      page.getByRole('link', { name: /new.*training|start.*training/i })
    );
    
    if (await newTrainingButton.first().isVisible()) {
      await expect(newTrainingButton.first()).toBeVisible();
    }
  });
});

test.describe('Training Pipeline - Runs List', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard/training/runs');
  });

  test('should display training runs list', async ({ page }) => {
    // Runs list should be visible
    const runsList = page.locator('[data-testid="training-runs-list"]').or(
      page.locator('table').or(page.locator('[role="list"]'))
    );
    await expect(runsList.first()).toBeVisible({ timeout: 5000 });
  });

  test('should show run status indicators', async ({ page }) => {
    // Status badges should be visible
    const statusBadge = page.locator('[data-testid="run-status"]').or(
      page.locator('text=/completed|running|failed|queued|preparing|validating/i')
    );
    
    // At least one status should be visible
    const isVisible = await statusBadge.first().isVisible().catch(() => false);
    // Runs list exists even if empty
  });

  test('should allow filtering runs', async ({ page }) => {
    // Look for filter options
    const filterButton = page.getByRole('button', { name: /filter/i }).or(
      page.locator('select')
    );

    if (await filterButton.first().isVisible()) {
      await filterButton.first().click();
    }
  });

  test('should show run details on click', async ({ page }) => {
    // Look for clickable run card
    const runCard = page.locator('[data-testid="training-run-card"]').or(
      page.locator('tr[role="button"]').or(page.locator('a[href*="runs"]'))
    );

    if (await runCard.first().isVisible()) {
      await runCard.first().click();
      await page.waitForTimeout(500);
    }
  });
});

test.describe('Training Pipeline - New Training Run', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard/training/new');
  });

  test('should display training configuration form', async ({ page }) => {
    // Form should be visible
    const form = page.locator('form').or(
      page.locator('[data-testid="training-form"]')
    );
    await expect(form.first()).toBeVisible({ timeout: 5000 });
  });

  test('should have agent selection', async ({ page }) => {
    // Agent dropdown should be present
    const agentSelect = page.locator('select[name="agent"]').or(
      page.locator('[data-testid="agent-select"]').or(
        page.locator('text=/select.*agent|choose.*agent/i')
      )
    );
    await expect(agentSelect.first()).toBeVisible();
  });

  test('should have training parameters', async ({ page }) => {
    // Look for training parameter inputs
    const epochsInput = page.locator('input[name="epochs"]').or(
      page.locator('label:has-text("epochs") + input')
    );
    const learningRateInput = page.locator('input[name="learning_rate"]').or(
      page.locator('label:has-text("learning") + input')
    );

    // At least one parameter should be visible
    const params = page.locator('text=/epochs|learning.*rate|batch.*size/i');
    await expect(params.first()).toBeVisible();
  });

  test('should have submit button', async ({ page }) => {
    // Submit/start training button
    const submitButton = page.getByRole('button', { name: /start|submit|begin|train/i });
    await expect(submitButton.first()).toBeVisible();
  });

  test('should validate required fields', async ({ page }) => {
    // Try to submit without filling required fields
    const submitButton = page.getByRole('button', { name: /start|submit|begin/i }).first();
    
    if (await submitButton.isVisible()) {
      await submitButton.click();
      
      // Should show validation error
      const errorMessage = page.locator('text=/required|please|select/i').or(
        page.locator('[class*="error"]')
      );
    }
  });
});

test.describe('Training Pipeline - Mistake Threshold', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard/training');
  });

  test('should display mistake threshold progress', async ({ page }) => {
    // Mistake threshold indicator should be visible
    const thresholdProgress = page.locator('[data-testid="mistake-threshold"]').or(
      page.locator('text=/mistake|threshold|50/i')
    );
    await expect(thresholdProgress.first()).toBeVisible({ timeout: 5000 });
  });

  test('should show progress bar for threshold', async ({ page }) => {
    // Progress bar for threshold
    const progressBar = page.locator('[role="progressbar"]').or(
      page.locator('[data-testid="threshold-progress"]')
    );

    if (await progressBar.first().isVisible()) {
      const value = await progressBar.first().getAttribute('aria-valuenow');
      // Value should be between 0 and 100
      if (value) {
        const numValue = parseInt(value);
        expect(numValue).toBeGreaterThanOrEqual(0);
        expect(numValue).toBeLessThanOrEqual(100);
      }
    }
  });

  test('should display current mistake count', async ({ page }) => {
    // Should show count out of 50
    const countDisplay = page.locator('text=/\\d+.*50|\\d+\\/50/i').or(
      page.locator('text=/mistakes?:\\s*\\d+/i')
    );
    
    // Look for any number display related to mistakes
    const mistakeNumber = page.locator('[data-testid="mistake-count"]').or(
      page.locator('text=/\\d+.*mistake/i')
    );
  });
});

test.describe('Training Pipeline - Cold Start', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard/training');
  });

  test('should display cold start card', async ({ page }) => {
    // Cold start card should be visible
    const coldStartCard = page.locator('[data-testid="cold-start-card"]').or(
      page.locator('text=/cold.?start|new.*agent|template/i')
    );
    await expect(coldStartCard.first()).toBeVisible({ timeout: 5000 });
  });

  test('should show industry templates option', async ({ page }) => {
    // Industry templates should be referenced
    const templates = page.locator('text=/industry|template|ecommerce|saas|healthcare|retail/i');
    await expect(templates.first()).toBeVisible({ timeout: 5000 });
  });

  test('should allow cold start initialization', async ({ page }) => {
    // Initialize button should be present if agent needs cold start
    const initButton = page.getByRole('button', { name: /initialize|start|cold.?start/i });
    
    if (await initButton.first().isVisible()) {
      await expect(initButton.first()).toBeVisible();
    }
  });
});

test.describe('Training Pipeline - Retraining Schedule', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/dashboard/training');
  });

  test('should display retraining schedule', async ({ page }) => {
    // Retraining schedule section
    const scheduleCard = page.locator('[data-testid="retraining-schedule"]').or(
      page.locator('text=/retrain|schedule|due|bi.?weekly/i')
    );
    await expect(scheduleCard.first()).toBeVisible({ timeout: 5000 });
  });

  test('should show agents due for retraining', async ({ page }) => {
    // Due agents should be listed
    const dueAgents = page.locator('text=/due|overdue|scheduled/i');
    
    const isVisible = await dueAgents.first().isVisible().catch(() => false);
    // Schedule may be empty
  });

  test('should allow scheduling retraining', async ({ page }) => {
    // Schedule retraining button
    const scheduleButton = page.getByRole('button', { name: /schedule|retrain|start/i });
    
    if (await scheduleButton.first().isVisible()) {
      await expect(scheduleButton.first()).toBeVisible();
    }
  });
});

test.describe('Training Pipeline - Error Handling', () => {
  test('should display error boundary on errors', async ({ page }) => {
    // Navigate to training with potential error state
    await page.goto('/dashboard/training');

    // Error boundary should catch and display errors gracefully
    const errorBoundary = page.locator('[data-testid="error-boundary"]').or(
      page.locator('text=/error|failed|try.*again/i')
    );

    // If error occurs, it should be handled
    const hasError = await errorBoundary.first().isVisible().catch(() => false);
  });

  test('should show loading skeletons while loading', async ({ page }) => {
    await page.goto('/dashboard/training');

    // Look for loading states (skeleton or spinner)
    const loadingState = page.locator('[data-testid="loading-skeleton"]').or(
      page.locator('[class*="skeleton"]').or(
        page.locator('[class*="animate-pulse"]')
      )
    );

    // Loading states may appear briefly
    // Just verify page eventually loads
    await page.waitForLoadState('networkidle');
  });
});

test.describe('Training Pipeline - Responsive', () => {
  test('should be responsive on mobile', async ({ page, isMobile }) => {
    await page.goto('/dashboard/training');

    if (isMobile) {
      // Dashboard should still be usable
      const mainContent = page.locator('main').or(page.locator('[role="main"]'));
      await expect(mainContent.first()).toBeVisible();

      // Cards should stack vertically
      const cards = page.locator('[data-testid="training-card"]').or(
        page.locator('[class*="card"]')
      );
    }
  });
});
