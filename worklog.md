---
Task ID: 2
Agent: Main Agent
Task: Fix pricing page, restore coupons, improve CSRF, fix progress indicator, add dashboard integration health, update Paddle key

Work Log:
- Replaced /pricing page: removed wrong industry-module pricing ($99/$49/etc), now shows 3 simple variant cards ($999/$2499/$3999)
- Restored coupon-config.ts with full coupon support for manual testing (no discounts shown on pricing page, coupons applied at Paddle checkout)
- Improved CSRF handling: added BACKEND_URL as trusted origin, moved no-origin strategy to first attempt for faster resolution
- Fixed ProgressIndicator: smaller step sizes on mobile, overflow handling, all 6 steps consistently visible
- Added DashboardIntegrationHealth component to main dashboard page with connector verification status
- Updated Paddle live API key in .env.production (placeholder in git, real key via Vercel env vars)
- Build passes successfully

Stage Summary:
- Pricing page now shows correct prices: $999, $2499, $3999
- Coupons kept for manual testing (not displayed on pricing page)
- CSRF upload tries no-origin first for speed, then fallback origins
- ProgressIndicator shows all 6 steps on all screen sizes
- Dashboard now has integration health section with connector verification
- Paddle live key must be set in Vercel environment variables
