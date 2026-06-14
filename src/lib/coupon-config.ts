/**
 * PARWA Coupon Code Configuration
 * ═══════════════════════════════════════════════════════════════════
 *
 * Manages coupon codes for discounts during checkout.
 * Primarily used for testing — 100% off coupons let you walk
 * through the entire Paddle checkout flow at $0.
 *
 * Paddle Terminology:
 * - Paddle calls coupons "discounts"
 * - A discount has a `code` (what users type) and an `id` (Paddle internal)
 * - In Checkout.open, use `discountCode` (human code) or `discountId` (Paddle ID)
 *
 * How to set up a test coupon:
 * 1. Go to Paddle Dashboard → Catalog → Discounts
 * 2. Create a discount:
 *    - Code: "PARWAFREE"
 *    - Type: Percentage
 *    - Amount: 100%
 *    - Recurring: Yes (so it applies every billing cycle)
 * 3. Copy the discount code and optionally the Paddle discount ID
 * 4. Add it to the COUPONS list below, or set env var NEXT_PUBLIC_PADDLE_FREE_DISCOUNT_CODE
 *
 * ⚠️  IMPORTANT: For $0 transactions to work, make sure:
 *     - You're using Paddle Sandbox for testing
 *     - Sandbox allows $0 transactions by default
 *     - If using Live, ensure "Allow free transactions" is enabled
 */

// ── Coupon Definition ──────────────────────────────────────────────

export interface Coupon {
  /** Human-readable code the user types (e.g. "PARWAFREE") */
  code: string;
  /** Discount percentage (0-100). 100 = completely free */
  discountPercent: number;
  /** Paddle discount ID (e.g. "dsc_01xxxxxx") — pass as discountId to Checkout.open */
  paddleDiscountId?: string;
  /** Short description shown in UI */
  description: string;
  /** Whether this coupon is active */
  active: boolean;
  /** Max times this coupon can be used (undefined = unlimited) */
  maxUses?: number;
  /** ISO date when coupon expires (undefined = never) */
  expiresAt?: string;
}

// ── Registered Coupons ─────────────────────────────────────────────

/**
 * Add your Paddle discounts/coupons here.
 *
 * To add a new test coupon:
 * 1. Create it in Paddle Dashboard → Catalog → Discounts
 * 2. Copy the discount code and/or Paddle discount ID
 * 3. Add an entry below
 *
 * The env var NEXT_PUBLIC_PADDLE_FREE_DISCOUNT_CODE can override
 * the discount code at deploy time.
 * The env var NEXT_PUBLIC_PADDLE_FREE_DISCOUNT_ID can override
 * the Paddle discount ID at deploy time.
 */
export const COUPONS: Coupon[] = [
  {
    code: process.env.NEXT_PUBLIC_PADDLE_FREE_DISCOUNT_CODE || 'durga754',
    discountPercent: 100,
    // Override via env var, or hardcode your Paddle discount ID here
    paddleDiscountId: process.env.NEXT_PUBLIC_PADDLE_FREE_DISCOUNT_ID || undefined,
    description: '100% off — Full testing access (all variants free)',
    active: true,
  },
];

// ── Coupon Lookup ──────────────────────────────────────────────────

/**
 * Validate a coupon code (case-insensitive).
 * Returns the coupon if valid and active, or null.
 */
export function validateCoupon(code: string): Coupon | null {
  if (!code || code.trim().length === 0) return null;
  const normalized = code.trim().toUpperCase();
  const coupon = COUPONS.find(
    (c) => c.active && c.code.toUpperCase() === normalized
  );
  if (!coupon) return null;

  // Check expiry
  if (coupon.expiresAt && new Date(coupon.expiresAt) < new Date()) {
    return null;
  }

  return coupon;
}

/**
 * Apply a coupon discount to a price.
 * Returns the discounted price (never below 0).
 */
export function applyCouponDiscount(
  price: number,
  coupon: Coupon | null
): number {
  if (!coupon) return price;
  const discount = price * (coupon.discountPercent / 100);
  return Math.max(0, Math.round((price - discount) * 100) / 100);
}

/**
 * Get the Paddle discount code for a validated coupon.
 * This is the human-readable code passed to Checkout.open as `discountCode`.
 */
export function getPaddleDiscountCode(coupon: Coupon | null): string | undefined {
  if (!coupon) return undefined;
  return coupon.code;
}

/**
 * Get the Paddle discount ID for a validated coupon.
 * This is the internal Paddle ID passed to Checkout.open as `discountId`.
 * Only used if discountCode is not available.
 */
export function getPaddleDiscountId(coupon: Coupon | null): string | undefined {
  if (!coupon) return undefined;
  return (
    coupon.paddleDiscountId ||
    process.env.NEXT_PUBLIC_PADDLE_FREE_DISCOUNT_ID ||
    undefined
  );
}

/**
 * Format the discount label for display.
 * e.g. "100% off" or "50% off"
 */
export function formatDiscount(coupon: Coupon): string {
  return `${coupon.discountPercent}% off`;
}
