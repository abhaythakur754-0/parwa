/**
 * PARWA Coupon Code Configuration
 * ═══════════════════════════════════════════════════════════════════
 *
 * Pricing is simple: $999 / $2,499 / $3,999 — no discounts shown on the frontend.
 *
 * Coupons are kept for MANUAL TESTING purposes. For example:
 * - A 100% off coupon "PARWAFREE" lets you test the full checkout flow without paying
 * - Create coupons in Paddle Dashboard → Catalog → Discounts
 * - Pass coupon code at checkout to apply them
 *
 * The frontend does NOT display discount fields or coupon inputs on the pricing page.
 * Coupons are only applied during the Paddle checkout overlay.
 */

export interface Coupon {
  code: string;
  discountPercent: number;
  paddleDiscountId?: string;
  description: string;
  active: boolean;
  maxUses?: number;
  expiresAt?: string;
}

// ── Active Coupons (for manual testing) ──────────────────────────────
// Add coupons here that should be available for manual checkout testing.
// They are NOT displayed on the pricing page — only applied at Paddle checkout.

export const COUPONS: Coupon[] = [
  // Example: 100% off for testing the full checkout flow
  // Uncomment and set the actual Paddle discount code when created:
  // {
  //   code: 'PARWAFREE',
  //   discountPercent: 100,
  //   paddleDiscountId: 'dsc_01xxx',
  //   description: '100% off — testing only',
  //   active: true,
  //   maxUses: 100,
  // },
];

/**
 * Validate a coupon code.
 * Returns the Coupon if valid, null otherwise.
 * This is used to pass the coupon to Paddle checkout — not for UI display.
 */
export function validateCoupon(code: string): Coupon | null {
  if (!code?.trim()) return null;
  const coupon = COUPONS.find(
    (c) => c.code.toLowerCase() === code.toLowerCase() && c.active
  );
  return coupon || null;
}

/**
 * Apply a coupon discount to a price.
 * Returns the discounted price, or the original price if no coupon.
 */
export function applyCouponDiscount(price: number, coupon: Coupon | null): number {
  if (!coupon) return price;
  return Math.round(price * (1 - coupon.discountPercent / 100));
}

/**
 * Get the Paddle discount code for a coupon (for checkout pre-fill).
 */
export function getPaddleDiscountCode(coupon: Coupon | null): string | undefined {
  return coupon?.code || undefined;
}

/**
 * Get the Paddle internal discount ID for a coupon (alternative to code).
 */
export function getPaddleDiscountId(coupon: Coupon | null): string | undefined {
  return coupon?.paddleDiscountId || undefined;
}

/**
 * Format a coupon's discount for display (only in checkout context).
 */
export function formatDiscount(coupon: Coupon): string {
  return `${coupon.discountPercent}% off`;
}
