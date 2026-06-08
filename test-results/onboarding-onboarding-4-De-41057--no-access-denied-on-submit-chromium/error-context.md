# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: onboarding/onboarding.spec.ts >> 4. Details form — fields present, no access denied on submit
- Location: tests/e2e/onboarding/onboarding.spec.ts:208:1

# Error details

```
TimeoutError: locator.click: Timeout 15000ms exceeded.
Call log:
  - waiting for getByRole('button', { name: /continue/i })
    - locator resolved to <button disabled type="submit" class="btn-primary btn-lg w-full">…</button>
  - attempting click action
    2 × waiting for element to be visible, enabled and stable
      - element is not enabled
    - retrying click action
    - waiting 20ms
    2 × waiting for element to be visible, enabled and stable
      - element is not enabled
    - retrying click action
      - waiting 100ms
    28 × waiting for element to be visible, enabled and stable
       - element is not enabled
     - retrying click action
       - waiting 500ms

```

# Page snapshot

```yaml
- generic [ref=e1]:
  - generic [ref=e3]:
    - generic [ref=e5]:
      - generic [ref=e6]:
        - generic [ref=e7]: "1"
        - generic [ref=e8]: Details
      - generic [ref=e10]:
        - generic [ref=e11]: "2"
        - generic [ref=e12]: Setup
      - generic [ref=e14]:
        - generic [ref=e15]: "3"
        - generic [ref=e16]: Launch
    - generic [ref=e17]:
      - generic [ref=e18]:
        - heading "PARWA" [level=1] [ref=e19]
        - paragraph [ref=e20]: AI-Powered Customer Support
      - generic [ref=e21]:
        - generic [ref=e22]:
          - heading "Tell us about yourself" [level=2] [ref=e23]
          - paragraph [ref=e24]: Help us personalize your PARWA experience
        - generic [ref=e25]:
          - generic [ref=e26]: Full Name *
          - generic [ref=e27]:
            - img [ref=e28]
            - textbox "Full Name *" [ref=e31]:
              - /placeholder: John Doe
              - text: Test User
        - generic [ref=e32]:
          - generic [ref=e33]: Company Name *
          - generic [ref=e34]:
            - img [ref=e35]
            - textbox "Company Name *" [active] [ref=e39]:
              - /placeholder: Acme Corporation
              - text: Test Company
        - generic [ref=e40]:
          - generic [ref=e41]: Work Email (optional)
          - generic [ref=e42]:
            - img [ref=e43]
            - textbox "Work Email (optional)" [ref=e46]:
              - /placeholder: john@company.com
        - generic [ref=e47]:
          - generic [ref=e48]: Industry *
          - button "Select your industry" [ref=e49]:
            - generic [ref=e50]:
              - img [ref=e51]
              - generic [ref=e55]: Select your industry
            - img [ref=e56]
        - generic [ref=e58]:
          - generic [ref=e59]: Company Size (optional)
          - generic [ref=e60]:
            - img [ref=e61]
            - combobox "Company Size (optional)" [ref=e66]:
              - option "Select company size" [selected]
              - option "1-10 employees"
              - option "11-50 employees"
              - option "51-200 employees"
              - option "201-500 employees"
              - option "501-1000 employees"
              - option "1000+ employees"
        - generic [ref=e67]:
          - generic [ref=e68]: Website (optional)
          - generic [ref=e69]:
            - img [ref=e70]
            - textbox "Website (optional)" [ref=e73]:
              - /placeholder: https://company.com
        - button "Continue" [disabled] [ref=e75]:
          - text: Continue
          - img [ref=e76]
    - paragraph [ref=e79]:
      - text: Need help?
      - link "Contact Support" [ref=e80] [cursor=pointer]:
        - /url: mailto:support@parwa.io
  - alert [ref=e81]
```

# Test source

```ts
  151 |   console.log(`[T2] After industry select — variants visible: ${hasVariants}`);
  152 | 
  153 |   // Add 1 unit using Increase Quantity button
  154 |   const increaseBtn = page.locator('button[aria-label="Increase quantity"]').first();
  155 |   if (await increaseBtn.isVisible().catch(() => false)) {
  156 |     await increaseBtn.click();
  157 |     await page.waitForTimeout(1000);
  158 | 
  159 |     // Should show quantity = 1
  160 |     const afterText = await pageText(page);
  161 |     const hasQuantity = afterText.includes('1 unit') || afterText.includes('1/');
  162 |     console.log(`[T2] After increase — quantity visible: ${hasQuantity}`);
  163 |   }
  164 | 
  165 |   // Should have "Continue with Jarvis" button
  166 |   const continueBtn = page.getByRole('button', { name: /continue with jarvis/i });
  167 |   const hasContinue = await continueBtn.isVisible().catch(() => false);
  168 |   console.log(`[T2] Continue with Jarvis visible: ${hasContinue}`);
  169 | 
  170 |   await screenshotOnFail(page, 't2-variants');
  171 | });
  172 | 
  173 | // ════════════════════════════════════════════════════════════════
  174 | // TEST 3: Pricing continue → redirects to /welcome/details
  175 | // ════════════════════════════════════════════════════════════════
  176 | test('3. Pricing continue redirects to /welcome/details', async ({ page }) => {
  177 |   await goto(page, '/pricing');
  178 | 
  179 |   await selectIndustry(page, 'E-commerce');
  180 | 
  181 |   // Add a variant first
  182 |   const increaseBtn = page.locator('button[aria-label="Increase quantity"]').first();
  183 |   if (await increaseBtn.isVisible().catch(() => false)) {
  184 |     await increaseBtn.click();
  185 |     await page.waitForTimeout(1000);
  186 |   }
  187 | 
  188 |   // Click Continue with Jarvis
  189 |   const continueBtn = page.getByRole('button', { name: /continue with jarvis/i });
  190 |   if (await continueBtn.isVisible().catch(() => false)) {
  191 |     await continueBtn.click();
  192 |     await page.waitForTimeout(5000);
  193 | 
  194 |     const url = page.url();
  195 |     console.log(`[T3] After continue — URL: ${url}`);
  196 |     // Should redirect to /welcome/details with pricing params
  197 |     expect(url).toContain('/welcome/details');
  198 |     expect(url).toContain('source=pricing');
  199 |     expect(url).toContain('industry=');
  200 |   }
  201 | 
  202 |   await screenshotOnFail(page, 't3-pricing-continue');
  203 | });
  204 | 
  205 | // ════════════════════════════════════════════════════════════════
  206 | // TEST 4: Details form — fields, validation, NO access denied
  207 | // ════════════════════════════════════════════════════════════════
  208 | test('4. Details form — fields present, no access denied on submit', async ({ page }) => {
  209 |   // Track 403 responses
  210 |   const accessDeniedUrls: string[] = [];
  211 |   page.on('response', async (resp) => {
  212 |     if (resp.status() === 403 && resp.url().includes('/api/')) {
  213 |       const body = await resp.text().catch(() => '');
  214 |       if (body.includes('AUTHORIZATION_ERROR') || body.includes('access denied') || body.includes('Tenant identification')) {
  215 |         accessDeniedUrls.push(resp.url());
  216 |       }
  217 |     }
  218 |   });
  219 | 
  220 |   // Navigate directly to details page (without auth)
  221 |   await goto(page, '/welcome/details?source=pricing&industry=ecommerce&variants=ecom-order-mgmt_1x');
  222 | 
  223 |   const url = page.url();
  224 |   const text = await pageText(page);
  225 |   console.log(`[T4] URL: ${url}`);
  226 | 
  227 |   // With the auth guard fix, should redirect to login
  228 |   if (url.includes('/login')) {
  229 |     console.log('[T4] ✅ Correctly redirected to login (not authenticated)');
  230 |     expect(url).toContain('/login');
  231 |     // The redirect param should preserve the details URL
  232 |     expect(url).toContain('redirect=');
  233 |     expect(url).toContain('welcome');
  234 |   } else if (text.includes('Tell us about yourself')) {
  235 |     // If authenticated (existing session), the form should render
  236 |     console.log('[T4] Details form visible (already authenticated)');
  237 | 
  238 |     // Check form fields
  239 |     await expect(page.locator('#full_name')).toBeVisible();
  240 |     await expect(page.locator('#company_name')).toBeVisible();
  241 |     const industrySelect = page.locator('#industry');
  242 |     if (await industrySelect.isVisible().catch(() => false)) {
  243 |       console.log('[T4] Industry select visible');
  244 |     }
  245 | 
  246 |     // Fill and submit
  247 |     await page.locator('#full_name').fill('Test User');
  248 |     await page.locator('#company_name').fill('Test Company');
  249 | 
  250 |     const continueBtn = page.getByRole('button', { name: /continue/i });
> 251 |     await continueBtn.click();
      |                       ^ TimeoutError: locator.click: Timeout 15000ms exceeded.
  252 |     await page.waitForTimeout(5000);
  253 | 
  254 |     // Check for access denied
  255 |     const afterText = await pageText(page);
  256 |     const hasAccessDenied = afterText.toLowerCase().includes('access denied');
  257 |     expect(hasAccessDenied).toBeFalsy();
  258 |   }
  259 | 
  260 |   // Should NOT have any 403 AUTHORIZATION_ERROR responses
  261 |   if (accessDeniedUrls.length > 0) {
  262 |     console.error(`[T4] ❌ Access denied on: ${accessDeniedUrls.join(', ')}`);
  263 |   }
  264 |   expect(accessDeniedUrls.length).toBe(0);
  265 | 
  266 |   await screenshotOnFail(page, 't4-details-form');
  267 | });
  268 | 
  269 | // ════════════════════════════════════════════════════════════════
  270 | // TEST 5: Onboarding Step 1 (Welcome) loads and completes
  271 | // ════════════════════════════════════════════════════════════════
  272 | test('5. Onboarding Step 1 — Welcome loads and completes', async ({ page }) => {
  273 |   await signUpNewUser(page);
  274 | 
  275 |   const url = page.url();
  276 |   const text = await pageText(page);
  277 |   console.log(`[T5] After signup — URL: ${url}`);
  278 |   console.log(`[T5] Page preview: ${text.substring(0, 300)}`);
  279 | 
  280 |   // Should be on onboarding or login
  281 |   const isOnOnboarding = url.includes('/onboarding') || text.includes('Welcome') || text.includes('Get Started');
  282 |   const isOnLogin = url.includes('/login');
  283 | 
  284 |   if (isOnOnboarding) {
  285 |     const getStartedBtn = page.getByRole('button', { name: /let.*get started|get started/i });
  286 |     if (await getStartedBtn.isVisible().catch(() => false)) {
  287 |       await getStartedBtn.click();
  288 |       await page.waitForTimeout(3000);
  289 |       console.log('[T5] ✅ Clicked Get Started');
  290 |     }
  291 |   } else if (isOnLogin) {
  292 |     console.log('[T5] On login page — signup may have failed');
  293 |   }
  294 | 
  295 |   await screenshotOnFail(page, 't5-welcome');
  296 | });
  297 | 
  298 | // ════════════════════════════════════════════════════════════════
  299 | // TEST 6: Step 2 (Legal Compliance) — consents + submit
  300 | // ════════════════════════════════════════════════════════════════
  301 | test('6. Step 2 — Legal Compliance with all consents', async ({ page }) => {
  302 |   await goto(page, '/onboarding');
  303 | 
  304 |   if (!await isAuthenticated(page)) {
  305 |     await signUpNewUser(page);
  306 |   }
  307 | 
  308 |   const text = await pageText(page);
  309 |   console.log(`[T6] Page content: ${text.substring(0, 200)}`);
  310 | 
  311 |   // If on welcome step, advance
  312 |   const getStartedBtn = page.getByRole('button', { name: /let.*get started|get started/i });
  313 |   if (await getStartedBtn.isVisible().catch(() => false)) {
  314 |     await getStartedBtn.click();
  315 |     await page.waitForTimeout(3000);
  316 |   }
  317 | 
  318 |   // Check for legal content
  319 |   const hasLegal = text.includes('Legal') || text.includes('Consent') || text.includes('Terms of Service');
  320 |   console.log(`[T6] Legal content found: ${hasLegal}`);
  321 | 
  322 |   if (hasLegal) {
  323 |     // Check all checkboxes
  324 |     const checkboxes = page.locator('button[role="checkbox"], input[type="checkbox"]');
  325 |     const count = await checkboxes.count();
  326 |     console.log(`[T6] Found ${count} checkboxes`);
  327 |     for (let i = 0; i < count; i++) {
  328 |       const isChecked = await checkboxes.nth(i).getAttribute('aria-checked').then(v => v === 'true').catch(() => false);
  329 |       if (!isChecked) {
  330 |         await checkboxes.nth(i).click().catch(() => {});
  331 |         await page.waitForTimeout(300);
  332 |       }
  333 |     }
  334 | 
  335 |     const acceptBtn = page.getByRole('button', { name: /accept.*continue|agree|continue/i });
  336 |     if (await acceptBtn.isVisible().catch(() => false)) {
  337 |       await acceptBtn.click();
  338 |       await page.waitForTimeout(4000);
  339 |       console.log('[T6] ✅ Legal consent submitted');
  340 |     }
  341 |   }
  342 | 
  343 |   await screenshotOnFail(page, 't6-legal');
  344 | });
  345 | 
  346 | // ════════════════════════════════════════════════════════════════
  347 | // TEST 7: Step 3 (Integration Setup) — connect/skip
  348 | // ════════════════════════════════════════════════════════════════
  349 | test('7. Step 3 — Integration Setup with skip warning', async ({ page }) => {
  350 |   await goto(page, '/onboarding');
  351 | 
```