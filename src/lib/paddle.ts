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
 */

import { initializePaddle, Paddle } from '@paddle/paddle-js';

let paddleInstance: Paddle | undefined;

/**
 * Initialize Paddle.js with the public key from environment.
 * Safe to call multiple times — returns cached instance.
 */
export async function getPaddleInstance(): Promise<Paddle | undefined> {
  if (paddleInstance) return paddleInstance;

  const paddleKey = process.env.NEXT_PUBLIC_PADDLE_KEY;
  if (!paddleKey) {
    console.warn('[paddle] NEXT_PUBLIC_PADDLE_KEY not set — checkout disabled');
    return undefined;
  }

  try {
    paddleInstance = await initializePaddle({
      environment: paddleKey.startsWith('live_') ? 'production' : 'sandbox',
      token: paddleKey,
    });
    console.log('[paddle] Initialized successfully, environment:', paddleKey.startsWith('live_') ? 'production' : 'sandbox');
    return paddleInstance;
  } catch (err) {
    console.error('[paddle] Failed to initialize Paddle.js:', err);
    return undefined;
  }
}

/**
 * Variant type -> Paddle price ID mapping.
 * Must match the backend's PLAN_PRICE_IDS in paddle_service.py.
 */
export const VARIANT_PRICE_IDS: Record<string, string> = {
  mini_parwa: 'pri_01krxm4r0kcm6mm5fc84pp9bj0',
  parwa: 'pri_01krxm4ra529ry7bzr9z73pza1',
  parwa_high: 'pri_01krxm4rjx1bfgg1w9z4qr3dd8',
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
 */
export async function openCheckoutWithItems(
  items: Array<{ priceId: string; quantity: number }>,
  customData?: Record<string, unknown>,
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
      items: items.map(item => ({
        priceId: item.priceId,
        quantity: item.quantity,
      })),
      customData,
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
