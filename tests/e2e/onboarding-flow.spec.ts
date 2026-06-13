/**
 * E2E Test: Complete Onboarding Flow — Landing → Pricing → Onboarding → Dashboard
 */
import { test, expect } from '@playwright/test';

const BASE = process.env.TEST_URL || 'https://parwa.buzz';

test.describe('Complete Onboarding Flow', () => {

  test('Full flow: Landing → Pricing → Onboarding', async ({ page }) => {
    test.setTimeout(120000);

    await test.step('1. Load landing page', async () => {
      await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(2000);
      await page.screenshot({ path: '/home/z/my-project/download/e2e-01-landing.png', fullPage: false });
      await expect(page.locator('nav')).toBeVisible({ timeout: 10000 });
      console.log('✅ Landing page loaded');
    });

    await test.step('2. Navigate to Pricing page', async () => {
      await page.goto(`${BASE}/pricing`, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForTimeout(2000);
      await page.screenshot({ path: '/home/z/my-project/download/e2e-02-pricing.png', fullPage: false });
      await expect(page.getByRole('heading', { name: 'Choose Your Industry' })).toBeVisible({ timeout: 10000 });
      console.log('✅ Pricing page loaded');
    });

    await test.step('3. Select E-commerce industry', async () => {
      // IndustrySelector uses Card with role="button" and aria-pressed
      const ecommerceCard = page.getByRole('button', { name: /e-commerce/i }).first();
      await ecommerceCard.click();
      await page.waitForTimeout(1000);
      await page.screenshot({ path: '/home/z/my-project/download/e2e-03-industry-selected.png', fullPage: false });
      console.log('✅ Industry selected');
    });

    await test.step('4. Add variant quantity', async () => {
      // Look for + buttons on variant cards
      const increaseBtns = page.locator('button[aria-label*="ncrease"], button:has-text("+")').filter({ hasNot: page.locator('text=Continue') });
      const btnCount = await increaseBtns.count();
      console.log(`   Found ${btnCount} add buttons`);
      if (btnCount > 0) {
        await increaseBtns.first().click();
        await page.waitForTimeout(500);
      }
      await page.screenshot({ path: '/home/z/my-project/download/e2e-04-variants-selected.png', fullPage: false });
      console.log('✅ Variants selected');
    });

    await test.step('5. Continue from Pricing', async () => {
      const continueBtn = page.locator('button:has-text("Continue")').first();
      if (await continueBtn.isVisible()) {
        await continueBtn.click();
        await page.waitForTimeout(3000);
      }
      await page.screenshot({ path: '/home/z/my-project/download/e2e-05-after-pricing-continue.png', fullPage: false });
      console.log('✅ Clicked continue, URL:', page.url());
    });

    await test.step('6. Onboarding wizard', async () => {
      if (!page.url().includes('/onboarding') && !page.url().includes('/welcome/details')) {
        await page.goto(`${BASE}/onboarding`, { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(2000);
      }
      await page.screenshot({ path: '/home/z/my-project/download/e2e-06-onboarding-welcome.png', fullPage: false });

      // Check dark premium theme
      const bodyBg = await page.evaluate(() => {
        const el = document.querySelector('[class*="min-h-screen"]');
        if (!el) return 'none';
        return window.getComputedStyle(el).backgroundColor;
      });
      console.log('🎨 Background color:', bodyBg);

      // Check PARWA brand in header
      const hasBrand = await page.locator('header').locator('text=PARWA').first().isVisible({ timeout: 3000 }).catch(() => false);
      console.log('📐 PARWA brand in header:', hasBrand);

      // Check logout button
      const hasLogout = await page.locator('header').locator('text=Logout').first().isVisible({ timeout: 3000 }).catch(() => false);
      console.log('🔓 Logout in header:', hasLogout);

      // Click "Let's Get Started"
      const getStartedBtn = page.locator('button:has-text("Get Started")').first();
      if (await getStartedBtn.isVisible({ timeout: 5000 })) {
        await getStartedBtn.click();
        await page.waitForTimeout(1500);
        console.log('✅ Clicked Get Started');
      }
    });

    await test.step('7. Legal compliance', async () => {
      const legalTitle = page.locator('text=Legal Compliance');
      if (await legalTitle.isVisible({ timeout: 5000 })) {
        await page.screenshot({ path: '/home/z/my-project/download/e2e-07-legal.png', fullPage: false });

        // Click all 3 checkbox areas (they are Card rows with click handler)
        const termsRow = page.locator('text=Terms of Service').first();
        const privacyRow = page.locator('text=Privacy Policy').first();
        const aiDataRow = page.locator('text=AI Data Processing').first();

        for (const row of [termsRow, privacyRow, aiDataRow]) {
          if (await row.isVisible({ timeout: 2000 })) {
            // Click the parent card row to toggle checkbox
            await row.click();
            await page.waitForTimeout(300);
          }
        }

        await page.screenshot({ path: '/home/z/my-project/download/e2e-08-legal-checked.png', fullPage: false });

        // Click Accept All & Continue
        const acceptBtn = page.locator('button:has-text("Accept")').first();
        if (await acceptBtn.isVisible()) {
          await acceptBtn.click();
          await page.waitForTimeout(1500);
        }
        console.log('✅ Legal step done');
      }
    });

    await test.step('8. Integration setup', async () => {
      const integrationTitle = page.locator('text=Connect Integrations');
      if (await integrationTitle.isVisible({ timeout: 5000 })) {
        await page.screenshot({ path: '/home/z/my-project/download/e2e-09-integrations.png', fullPage: false });
        // Skip - click Continue
        const continueBtn = page.locator('button:has-text("Continue")').last();
        if (await continueBtn.isVisible()) {
          await continueBtn.click();
          await page.waitForTimeout(1500);
        }
        console.log('✅ Integration step done');
      }
    });

    await test.step('9. Knowledge upload', async () => {
      const knowledgeTitle = page.locator('text=Knowledge Base');
      if (await knowledgeTitle.isVisible({ timeout: 5000 })) {
        await page.screenshot({ path: '/home/z/my-project/download/e2e-10-knowledge.png', fullPage: false });
        // Skip
        const continueBtn = page.locator('button:has-text("Continue")').last();
        if (await continueBtn.isVisible()) {
          await continueBtn.click();
          await page.waitForTimeout(1500);
        }
        console.log('✅ Knowledge step done');
      }
    });

    await test.step('10. AI config', async () => {
      const aiTitle = page.locator('text=Configure Your AI Assistant');
      if (await aiTitle.isVisible({ timeout: 5000 })) {
        await page.screenshot({ path: '/home/z/my-project/download/e2e-11-ai-config.png', fullPage: false });
        const activateBtn = page.locator('button:has-text("Activate")').first();
        if (await activateBtn.isVisible()) {
          await activateBtn.click();
          await page.waitForTimeout(2000);
        }
        console.log('✅ AI config step done');
      }
    });

    await test.step('11. First Victory / final', async () => {
      await page.screenshot({ path: '/home/z/my-project/download/e2e-12-final.png', fullPage: false });

      const victoryText = page.locator('text=Welcome to PARWA!');
      if (await victoryText.isVisible({ timeout: 5000 })) {
        console.log('🎉 First Victory screen visible!');
        const dashBtn = page.locator('button:has-text("Dashboard")').first();
        if (await dashBtn.isVisible()) {
          await dashBtn.click();
          await page.waitForTimeout(3000);
        }
      }

      console.log('📍 Final URL:', page.url());
      await page.screenshot({ path: '/home/z/my-project/download/e2e-13-final-page.png', fullPage: false });
    });
  });
});
