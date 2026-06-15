/**
 * PARWA Paddle.js Initialization Helper
 *
 * Initializes the Paddle.js client SDK with the environment's public key
 * and provides functions to open the Paddle checkout overlay.
 *
 * IMPORTANT: Paddle.js is the ONLY Paddle call made from the browser.
 * All transaction creation goes through the BFF proxy -> backend.
 *
 * Two checkout flows are supported:
 * 1. Transaction-based: Backend creates a transaction -> returns transaction_id -> Paddle.js opens it
 * 2. Items-based: Paddle.js opens checkout directly with price IDs (no server transaction needed)
 *
 * The items-based flow is the PRIMARY flow for onboarding because:
 * - New customers don't have a Paddle customer_id yet
 * - Paddle.js handles the entire checkout lifecycle
 * - After payment, Paddle fires a webhook to our backend with subscription details
 *
 * Discount/Coupon support:
 * - Paddle uses "discounts" (what users call "coupons")
 * - Pass `discountCode` to pre-apply a coupon code in checkout (e.g. "PARWAFREE")
 * - Pass `discountId` to pre-apply by Paddle internal ID (e.g. "dsc_01xxx")
 * - You cannot use both at the same time
 */

import { initializePaddle, Paddle, type CheckoutOpenOptions } from '@paddle/paddle-js';

let paddleInstance: Paddle | undefined;
let paddleInitFailed = false;

/**
 * Initialize Paddle.js with the public key from environment.
 * Safe to call multiple times — returns cached instance.
 * Will retry if initialization failed on a previous call.
 */
export async function getPaddleInstance(): Promise<Paddle | undefined> {
  if (paddleInstance) return paddleInstance;

  const paddleKey = process.env.NEXT_PUBLIC_PADDLE_KEY;
  if (!paddleKey) {
    console.warn('[paddle] NEXT_PUBLIC_PADDLE_KEY not set — checkout disabled');
    return undefined;
  }

  try {
    const isProduction = paddleKey.startsWith('live_') || paddleKey.startsWith('pdl_live_');
    console.log('[paddle] Initializing with key prefix:', paddleKey.substring(0, 10) + '...', 'environment:', isProduction ? 'production' : 'sandbox');
    paddleInstance = await initializePaddle({
      environment: isProduction ? 'production' : 'sandbox',
      token: paddleKey,
    });
    if (paddleInstance) {
      console.log('[paddle] Initialized successfully, environment:', isProduction ? 'production' : 'sandbox');
      paddleInitFailed = false;
    } else {
      console.error('[paddle] initializePaddle returned undefined — key may be invalid or truncated');
      paddleInitFailed = true;
    }
    return paddleInstance;
  } catch (err) {
    console.error('[paddle] Failed to initialize Paddle.js:', err);
    paddleInitFailed = true;
    return undefined;
  }
}

/**
 * Check if Paddle initialization previously failed.
 * Useful for showing diagnostic info in the UI.
 */
export function isPaddleInitFailed(): boolean {
  return paddleInitFailed;
}

/**
 * Reset the Paddle instance (e.g., after key change).
 * Next call to getPaddleInstance() will re-initialize.
 */
export function resetPaddleInstance(): void {
  paddleInstance = undefined;
  paddleInitFailed = false;
}

/**
 * Variant type -> Paddle price ID mapping.
 * Must match the backend's PLAN_PRICE_IDS in paddle_service.py.
 */
export const VARIANT_PRICE_IDS: Record<string, string> = {
  mini_parwa: 'pri_01ksamxdpw0kmh3qj9p1gdzgms',  // Active: Starter $999/mo
  parwa: 'pri_01ksamxf31qkmbekat2cgmqyef',        // Active: Growth $2,499/mo
  parwa_high: 'pri_01ksamxed6jkm7g7xz687ax3zy',    // Active: High $3,999/mo
};

/**
 * Open the Paddle checkout overlay for a given transaction ID.
 *
 * This is the server-side transaction flow:
 * 1. Backend creates a transaction via Paddle API -> returns transaction_id
 * 2. Frontend calls openCheckout(transactionId) -> Paddle overlay opens
 * 3. User completes payment in the overlay
 * 4. Paddle fires events / redirects on completion
 *
 * @param transactionId - The Paddle transaction ID returned by the backend
 * @param onSuccess - Optional callback when checkout completes successfully
 * @param onClose - Optional callback when checkout is closed without completing
 */
export async function openCheckout(
  transactionId: string,
  onSuccess?: () => void,
  onClose?: () => void,
): Promise<boolean> {
  const paddle = await getPaddleInstance();
  if (!paddle) {
    console.error('[paddle] Cannot open checkout — Paddle not initialized');
    return false;
  }

  try {
    paddle.Checkout.open({
      transactionId,
      settings: {
        displayMode: 'overlay',
        theme: 'light',
        successUrl: typeof window !== 'undefined'
          ? `${window.location.origin}/onboarding?step=victory`
          : undefined,
      },
    });

    // Listen for checkout completion via Paddle events
    setupCheckoutListeners(paddle, onSuccess, onClose);

    return true;
  } catch (err) {
    console.error('[paddle] Failed to open checkout:', err);
    return false;
  }
}

/**
 * Open the Paddle checkout overlay directly with items (price IDs).
 *
 * This is the CLIENT-SIDE checkout flow — no server transaction needed.
 * Recommended for new customers who don't have a Paddle customer_id yet.
 *
 * Paddle.js creates the transaction internally, handles payment,
 * and fires webhooks to our backend after completion.
 *
 * @param items - Array of { priceId, quantity } items to check out
 * @param customData - Optional metadata to embed in the transaction
 * @param onSuccess - Optional callback when checkout completes successfully
 * @param onClose - Optional callback when checkout is closed without completing
 * @param discountCode - Optional Paddle discount/coupon code to pre-apply (e.g. "PARWAFREE" for 100% off testing)
 * @param discountId - Optional Paddle internal discount ID (alternative to discountCode)
 */
export async function openCheckoutWithItems(
  items: Array<{ priceId: string; quantity: number }>,
  customData?: Record<string, unknown>,
  onSuccess?: () => void,
  onClose?: () => void,
  discountCode?: string,
  discountId?: string,
): Promise<boolean> {
  const paddle = await getPaddleInstance();
  if (!paddle) {
    console.error('[paddle] Cannot open checkout — Paddle not initialized');
    return false;
  }

  try {
    // Build checkout options — Paddle uses discriminated unions:
    // discountCode XOR discountId (can't have both)
    const baseOptions = {
      items: items.map(item => ({
        priceId: item.priceId,
        quantity: item.quantity,
      })),
      customData,
      settings: {
        displayMode: 'overlay' as const,
        theme: 'light' as const,
        successUrl: typeof window !== 'undefined'
          ? `${window.location.origin}/onboarding?step=victory`
          : undefined,
      },
    };

    // Build the final options with the correct discount type
    // PRIORITY: Use discountId over discountCode — it's more reliable
    // (no case-sensitivity issues, always matches what's in Paddle)
    let checkoutOptions: CheckoutOpenOptions;
    if (discountId) {
      checkoutOptions = { ...baseOptions, discountId };
    } else if (discountCode) {
      checkoutOptions = { ...baseOptions, discountCode };
    } else {
      checkoutOptions = { ...baseOptions };
    }

    if (discountCode || discountId) {
      console.log('[paddle] Applying discount:', discountId ? `id=${discountId}` : `code=${discountCode}`);
    }
    console.log('[paddle] Opening checkout with', items.length, 'items, prices:', items.map(i => i.priceId));

    paddle.Checkout.open(checkoutOptions);

    // Listen for checkout completion via Paddle events
    setupCheckoutListeners(paddle, onSuccess, onClose);

    return true;
  } catch (err) {
    console.error('[paddle] Failed to open items-based checkout:', err);
    return false;
  }
}

/**
 * Set up event listeners for Paddle checkout completion and close.
 * 
 * Paddle.js v1.x doesn't have addEventListener on Checkout.
 * Instead, we detect completion via:
 * 1. The successUrl redirect (Paddle redirects the page on success)
 * 2. DOM polling for overlay close detection
 * 3. Window message events as a fallback
 */
function setupCheckoutListeners(
  _paddle: Paddle,
  onSuccess?: () => void,
  onClose?: () => void,
): void {
  if (typeof window === 'undefined') return;

  // Listen for Paddle postMessage events (checkout.completed, checkout.closed)
  const messageHandler = (event: MessageEvent) => {
    try {
      // Paddle.js sends postMessage events from the checkout iframe
      if (event.data && typeof event.data === 'object') {
        const data = event.data as Record<string, unknown>;
        if (data.event === 'checkout.completed' || data.name === 'checkout.completed') {
          console.log('[paddle] Checkout completed successfully via postMessage');
          onSuccess?.();
          window.removeEventListener('message', messageHandler);
        } else if (data.event === 'checkout.closed' || data.name === 'checkout.closed') {
          console.log('[paddle] Checkout closed via postMessage');
          onClose?.();
          window.removeEventListener('message', messageHandler);
        }
      }
    } catch {
      // Ignore non-Paddle messages
    }
  };
  window.addEventListener('message', messageHandler);

  // Close detection via overlay DOM polling
  if (onClose) {
    let overlayDetected = false;
    const checkClosed = setInterval(() => {
      const overlay = document.querySelector('[data-paddle-overlay]') ||
        document.querySelector('iframe[src*="paddle"]') ||
        document.querySelector('.paddle-checkout');
      
      if (overlay) {
        overlayDetected = true;
      } else if (overlayDetected) {
        // Overlay was visible and is now gone = user closed it
        clearInterval(checkClosed);
        onClose();
        window.removeEventListener('message', messageHandler);
      }
    }, 1000);
    setTimeout(() => clearInterval(checkClosed), 600000);
  }
}
