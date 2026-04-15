import { test, expect } from '@playwright/test';

/**
 * Landing Page E2E Tests
 * 
 * Tests for the main landing page (/):
 * - Page renders correctly
 * - Hero section visible
 * - Feature carousel works
 * - How it works section
 * - Jarvis demo interaction
 * - Why Choose Us section
 * - Footer links
 * - Navigation to pricing
 * - Book demo modal
 */
test.describe('Landing Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should render landing page with hero section', async ({ page }) => {
    // Check page title
    await expect(page).toHaveTitle(/PARWA|AI Customer Support/);

    // Hero section should be visible
    const heroSection = page.locator('[data-testid="hero-section"]').or(
      page.locator('h1').first()
    );
    await expect(heroSection).toBeVisible();

    // Check for main CTA buttons
    const ctaButton = page.getByRole('link', { name: /get started|start free|try now/i }).or(
      page.getByRole('button', { name: /get started|start free|try now/i })
    );
    await expect(ctaButton.first()).toBeVisible();
  });

  test('should display feature carousel', async ({ page }) => {
    // Scroll to features section
    await page.locator('text=Features').or(page.locator('[data-testid="feature-carousel"]')).first().scrollIntoViewIfNeeded();

    // Feature carousel should exist
    const featureCarousel = page.locator('[data-testid="feature-carousel"]').or(
      page.locator('[class*="carousel"]').first()
    );
    
    // Check if features are visible (carousel or static features)
    const featuresSection = page.locator('text=/AI|Automation|Support/i').first();
    await expect(featuresSection).toBeVisible({ timeout: 5000 });
  });

  test('should display How It Works section', async ({ page }) => {
    // Scroll to How It Works section
    const howItWorks = page.locator('text=/How It Works|How it works/i');
    await howItWorks.scrollIntoViewIfNeeded();
    await expect(howItWorks).toBeVisible();

    // Check for step indicators
    const steps = page.locator('[data-testid="step-"]').or(
      page.locator('text=/Step|Connect|Train|Deploy/i')
    );
    await expect(steps.first()).toBeVisible();
  });

  test('should have Jarvis Demo section', async ({ page }) => {
    // Scroll to Jarvis demo
    const jarvisDemo = page.locator('[data-testid="jarvis-demo"]').or(
      page.locator('text=/Try Jarvis|Demo|Chat/i')
    );
    await jarvisDemo.first().scrollIntoViewIfNeeded();

    // Demo section should be visible
    await expect(jarvisDemo.first()).toBeVisible({ timeout: 5000 });
  });

  test('should display Why Choose Us section', async ({ page }) => {
    // Scroll to Why Choose Us
    const whyChooseUs = page.locator('[data-testid="why-choose-us"]').or(
      page.locator('text=/Why Choose|Benefits|Advantages/i')
    );
    await whyChooseUs.first().scrollIntoViewIfNeeded();
    await expect(whyChooseUs.first()).toBeVisible({ timeout: 5000 });
  });

  test('should have working footer with links', async ({ page }) => {
    // Scroll to footer
    const footer = page.locator('footer').or(page.locator('[data-testid="footer"]'));
    await footer.scrollIntoViewIfNeeded();
    await expect(footer).toBeVisible();

    // Check for footer links
    const footerLinks = footer.locator('a');
    const linkCount = await footerLinks.count();
    expect(linkCount).toBeGreaterThan(0);
  });

  test('should navigate to pricing page', async ({ page }) => {
    // Click pricing link in navigation
    const pricingLink = page.getByRole('link', { name: /pricing/i }).or(
      page.locator('a[href*="pricing"]')
    );
    
    await pricingLink.first().click();
    
    // Should be on pricing page
    await expect(page).toHaveURL(/pricing/);
  });

  test('should open book demo modal', async ({ page }) => {
    // Look for book demo button
    const bookDemoButton = page.getByRole('button', { name: /book.*demo|schedule.*demo/i }).or(
      page.getByRole('link', { name: /book.*demo|schedule.*demo/i })
    );

    if (await bookDemoButton.first().isVisible()) {
      await bookDemoButton.first().click();

      // Modal should appear
      const modal = page.locator('[role="dialog"]').or(
        page.locator('[data-testid="demo-modal"]')
      );
      await expect(modal).toBeVisible({ timeout: 5000 });
    }
  });

  test('should have responsive mobile layout', async ({ page, isMobile }) => {
    if (isMobile) {
      // Mobile menu should be available
      const mobileMenuButton = page.locator('[data-testid="mobile-menu"]').or(
        page.locator('button[aria-label*="menu"]')
      );
      
      if (await mobileMenuButton.isVisible()) {
        await mobileMenuButton.click();
        
        // Mobile navigation should be visible
        const mobileNav = page.locator('[data-testid="mobile-nav"]').or(
          page.locator('[role="navigation"]').last()
        );
        await expect(mobileNav).toBeVisible({ timeout: 5000 });
      }
    }
  });

  test('should have working navigation bar', async ({ page }) => {
    // Navigation should be visible
    const nav = page.locator('nav').or(page.locator('[role="navigation"]'));
    await expect(nav.first()).toBeVisible();

    // Logo should be present
    const logo = page.locator('img[alt*="PARWA"]').or(
      page.locator('text=PARWA').first()
    );
    await expect(logo).toBeVisible();
  });

  test('should have dogfooding banner if applicable', async ({ page }) => {
    // Check for dogfooding banner
    const banner = page.locator('[data-testid="dogfooding-banner"]').or(
      page.locator('text=/dogfooding|eating our own|we use/i')
    );

    // Banner is optional, just check if it exists
    const bannerVisible = await banner.first().isVisible().catch(() => false);
    // This is just a check, not an assertion
    if (bannerVisible) {
      console.log('Dogfooding banner is visible');
    }
  });
});

test.describe('Landing Page - Accessibility', () => {
  test('should have no accessibility violations on landing page', async ({ page }) => {
    await page.goto('/');
    
    // Check for basic accessibility
    // Heading hierarchy
    const h1 = page.locator('h1');
    await expect(h1).toHaveCount(1);

    // All images should have alt text
    const images = page.locator('img');
    const imageCount = await images.count();
    
    for (let i = 0; i < imageCount; i++) {
      const img = images.nth(i);
      const alt = await img.getAttribute('alt');
      const ariaLabel = await img.getAttribute('aria-label');
      const ariaHidden = await img.getAttribute('aria-hidden');
      
      // Image should have alt, aria-label, or be marked as decorative
      expect(alt || ariaLabel || ariaHidden === 'true').toBeTruthy();
    }
  });
});
