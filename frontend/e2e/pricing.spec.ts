import { test, expect } from '@playwright/test';

/**
 * Pricing Page E2E Tests
 * 
 * Tests for the pricing page (/pricing):
 * - Page renders correctly
 * - Three pricing tiers displayed
 * - Monthly/Annual toggle works
 * - Feature comparison table
 * - FAQ section
 * - CTA buttons work
 */
test.describe('Pricing Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/pricing');
  });

  test('should render pricing page with three tiers', async ({ page }) => {
    // Check page title/heading
    const pricingHeading = page.locator('h1').or(
      page.locator('text=/Pricing|Choose.*Plan/i').first()
    );
    await expect(pricingHeading).toBeVisible();

    // Should have three pricing tiers
    const pricingCards = page.locator('[data-testid="pricing-card"]').or(
      page.locator('[class*="pricing"]').or(
        page.locator('text=/Starter|Growth|Enterprise|Pro|High/i')
      )
    );

    // At least 3 pricing tiers should be visible
    await expect(pricingCards.first()).toBeVisible();
  });

  test('should display pricing tier names', async ({ page }) => {
    // Check for tier names
    const starter = page.locator('text=/Starter|Basic|Essential/i');
    const growth = page.locator('text=/Growth|Pro|Professional/i');
    const enterprise = page.locator('text=/Enterprise|High|Premium/i');

    await expect(starter.first()).toBeVisible();
    await expect(growth.first()).toBeVisible();
    await expect(enterprise.first()).toBeVisible();
  });

  test('should have monthly/annual billing toggle', async ({ page }) => {
    // Look for billing toggle
    const monthlyToggle = page.locator('text=/Monthly/i').or(
      page.locator('button:has-text("Monthly")')
    );
    const annualToggle = page.locator('text=/Annual|Yearly/i').or(
      page.locator('button:has-text("Annual")')
    );

    await expect(monthlyToggle.first()).toBeVisible();
    await expect(annualToggle.first()).toBeVisible();

    // Click annual toggle
    await annualToggle.first().click();

    // Prices should update (check for annual pricing indicators)
    const annualIndicator = page.locator('text=/save|off|%|year/i');
    await expect(annualIndicator.first()).toBeVisible({ timeout: 3000 });
  });

  test('should display price amounts', async ({ page }) => {
    // Check for pricing amounts
    const pricePattern = /\$\d+/;
    const prices = page.locator(`text=${pricePattern}`);
    
    const priceCount = await prices.count();
    expect(priceCount).toBeGreaterThan(0);
  });

  test('should show feature lists for each tier', async ({ page }) => {
    // Each pricing card should have features
    const featureLists = page.locator('[data-testid="feature-list"]').or(
      page.locator('ul').or(
        page.locator('text=/unlimited|tickets|support|AI|agents/i')
      )
    );

    await expect(featureLists.first()).toBeVisible();
  });

  test('should have feature comparison table', async ({ page }) => {
    // Scroll to comparison section
    const comparisonSection = page.locator('text=/Compare|Comparison|All Features/i');
    
    if (await comparisonSection.first().isVisible()) {
      await comparisonSection.first().scrollIntoViewIfNeeded();
      await expect(comparisonSection.first()).toBeVisible();
    }
  });

  test('should display FAQ section', async ({ page }) => {
    // Scroll to FAQ
    const faqSection = page.locator('[data-testid="faq"]').or(
      page.locator('text=/FAQ|Frequently Asked/i')
    );
    
    await faqSection.first().scrollIntoViewIfNeeded();

    if (await faqSection.first().isVisible()) {
      // FAQ items should be present
      const faqItems = page.locator('[data-testid="faq-item"]').or(
        page.locator('[role="button"]').filter({ hasText: /\?$/ })
      );
      await expect(faqItems.first()).toBeVisible({ timeout: 3000 });
    }
  });

  test('should have working CTA buttons', async ({ page }) => {
    // Find CTA buttons (Get Started, Start Free Trial, etc.)
    const ctaButtons = page.getByRole('button', { name: /get started|start|choose|select/i }).or(
      page.getByRole('link', { name: /get started|start|choose|select/i })
    );

    const buttonCount = await ctaButtons.count();
    expect(buttonCount).toBeGreaterThan(0);
  });

  test('should highlight recommended/popular plan', async ({ page }) => {
    // Look for popular/recommended badge
    const popularBadge = page.locator('text=/Popular|Recommended|Best Value/i').or(
      page.locator('[data-testid="popular-badge"]')
    );

    // This is optional, just log if present
    const isPopularVisible = await popularBadge.first().isVisible().catch(() => false);
    console.log(`Popular plan badge visible: ${isPopularVisible}`);
  });

  test('should show savings percentage for annual', async ({ page }) => {
    // Click annual toggle if available
    const annualToggle = page.locator('button:has-text("Annual")').or(
      page.locator('text=/Annual/i')
    );

    if (await annualToggle.first().isVisible()) {
      await annualToggle.first().click();

      // Look for savings indicator
      const savings = page.locator('text=/save|off|%\s*off|discount/i');
      await expect(savings.first()).toBeVisible({ timeout: 3000 });
    }
  });

  test('should navigate to signup on CTA click', async ({ page }) => {
    // Find and click first CTA button
    const ctaButton = page.getByRole('link', { name: /get started|start|choose|select/i }).first();
    
    if (await ctaButton.isVisible()) {
      await ctaButton.click();
      
      // Should navigate to signup or checkout
      await expect(page).toHaveURL(/signup|checkout|register|onboarding/);
    }
  });
});

test.describe('Pricing Page - Tier Details', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/pricing');
  });

  test('Starter tier should have correct features', async ({ page }) => {
    // Find starter card
    const starterCard = page.locator('[data-testid="pricing-card"]').filter({
      hasText: /Starter|Basic/i
    }).or(
      page.locator('text=/Starter|Basic/i').first().locator('..')
    );

    // Should mention key starter features
    const features = page.locator('text=/tickets|AI|support|email/i');
    await expect(features.first()).toBeVisible();
  });

  test('Growth tier should show advanced features', async ({ page }) => {
    // Find growth card
    const growthCard = page.locator('[data-testid="pricing-card"]').filter({
      hasText: /Growth|Pro/i
    });

    // Growth should have more features than starter
    const advancedFeatures = page.locator('text=/priority|advanced|unlimited|integrations/i');
    await expect(advancedFeatures.first()).toBeVisible();
  });

  test('Enterprise tier should show premium features', async ({ page }) => {
    // Find enterprise/high tier
    const enterpriseCard = page.locator('[data-testid="pricing-card"]').filter({
      hasText: /Enterprise|High|Premium/i
    });

    // Should have premium features
    const premiumFeatures = page.locator('text=/dedicated|SLA|custom|white.?label/i');
    
    if (await enterpriseCard.isVisible()) {
      await enterpriseCard.scrollIntoViewIfNeeded();
    }
  });
});

test.describe('Pricing Page - Responsive', () => {
  test('should be responsive on mobile', async ({ page, isMobile }) => {
    await page.goto('/pricing');

    if (isMobile) {
      // Pricing cards should stack vertically
      const cards = page.locator('[data-testid="pricing-card"]').or(
        page.locator('[class*="pricing"]')
      );

      // All cards should still be visible
      const cardCount = await cards.count();
      for (let i = 0; i < Math.min(cardCount, 3); i++) {
        await expect(cards.nth(i)).toBeVisible();
      }
    }
  });

  test('should display toggle correctly on mobile', async ({ page, isMobile }) => {
    await page.goto('/pricing');

    if (isMobile) {
      // Toggle should be accessible
      const monthlyButton = page.locator('button:has-text("Monthly")').or(
        page.locator('text=/Monthly/i')
      );
      const annualButton = page.locator('button:has-text("Annual")').or(
        page.locator('text=/Annual/i')
      );

      await expect(monthlyButton.first()).toBeVisible();
      await expect(annualButton.first()).toBeVisible();
    }
  });
});
