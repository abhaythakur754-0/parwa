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
 *
 * ──────────────────────────────────────────────────────────────────────
 * CRITICAL FIX: We do NOT import @paddle/paddle-js from npm AT ALL.
 *
 * The npm package has internal ESM circular references that cause TDZ
 * ("Cannot access 'ea' before initialization") errors when Next.js /
 * Turbopack / Webpack bundles it. Even dynamic import() does NOT fix
 * this because the bundler still resolves and includes the module in
 * the chunk graph, and its top-level evaluation triggers the TDZ.
 *
 * Instead, we load Paddle.js ENTIRELY from the CDN script tag:
 *   <script src="https://cdn.paddle.com/paddle/v2/paddle.js"></script>
 *
 * This completely bypasses the bundler and the TDZ issue.
 * ──────────────────────────────────────────────────────────────────────
 */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type PaddleWindow = any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
type CheckoutOpenOptions = any;

let paddleInstance: PaddleWindow | undefined;
let paddleInitFailed = false;
let paddleLoadPromise: Promise<PaddleWindow | undefined> | undefined;

/**
 * Initialize Paddle.js with the public key from environment.
 * Safe to call multiple times — returns cached instance.
 * Will retry if initialization failed on a previous call.
 *
 * Loads Paddle.js ENTIRELY from CDN (no npm import).
 */
export async function getPaddleInstance(): Promise<PaddleWindow | undefined> {
  if (paddleInstance) return paddleInstance;
  if (paddleLoadPromise) return paddleLoadPromise;

  paddleLoadPromise = _loadPaddle();
  return paddleLoadPromise;
}

async function _loadPaddle(): Promise<PaddleWindow | undefined> {
  // Resolve the Paddle client-side token.
  const FALLBACK_PADDLE_KEY = 'live_84ceb40f4a03f934aadd1460d60';
  let paddleKey = process.env.NEXT_PUBLIC_PADDLE_KEY;

  if (!paddleKey || paddleKey === 'your_paddle_client_token_here' || paddleKey === 'undefined') {
    console.warn('[paddle] NEXT_PUBLIC_PADDLE_KEY not set or placeholder — using fallback');
    paddleKey = FALLBACK_PADDLE_KEY;
  }

  const isProduction = paddleKey.startsWith('live_') || paddleKey.startsWith('pdl_live_');
  const environment = isProduction ? 'production' : 'sandbox';

  try {
    console.log('[paddle] Loading via CDN script tag, environment:', environment);
    paddleInstance = await loadPaddleFromCDN(paddleKey, environment);

    if (paddleInstance) {
      console.log('[paddle] Initialized successfully via CDN');
      paddleInitFailed = false;
      return paddleInstance;
    } else {
      console.error('[paddle] CDN load returned undefined — key may be invalid');
      paddleInitFailed = true;
      return undefined;
    }
  } catch (err) {
    console.error('[paddle] CDN load failed:', (err as Error).message);
    paddleInitFailed = true;
    return undefined;
  }
}

/**
 * Load Paddle.js from CDN using a script tag.
 * This completely avoids the npm module TDZ issues.
 */
function loadPaddleFromCDN(paddleKey: string, environment: string): Promise<PaddleWindow> {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined') {
      reject(new Error('Not in browser'));
      return;
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const win = window as any;

    // Check if Paddle is already loaded and initialized
    if (win.Paddle && win.Paddle.Checkout) {
      console.log('[paddle] Paddle already on window and initialized');
      resolve(win.Paddle);
      return;
    }

    // Check if script already exists (might be loading)
    const existingScript = document.querySelector('script[src*="paddle"]');
    if (existingScript) {
      // Wait for it to load
      const checkInterval = setInterval(() => {
        if (win.Paddle && win.Paddle.Checkout) {
          clearInterval(checkInterval);
          resolve(win.Paddle);
        }
      }, 100);
      setTimeout(() => {
        clearInterval(checkInterval);
        reject(new Error('Paddle CDN script timed out (existing script)'));
      }, 15000);
      return;
    }

    // Inject the Paddle script tag
    const script = document.createElement('script');
    script.src = 'https://cdn.paddle.com/paddle/v2/paddle.js';
    script.async = true;

    script.onload = () => {
      console.log('[paddle] CDN script loaded, waiting for Paddle global...');
      // Paddle.js sets window.Paddle after the script loads
      const checkInterval = setInterval(() => {
        if (win.Paddle) {
          clearInterval(checkInterval);
          try {
            // Initialize Paddle with the token
            win.Paddle.Setup({
              environment,
              token: paddleKey,
            });
            console.log('[paddle] CDN Paddle.Setup() called successfully');
            resolve(win.Paddle);
          } catch (err) {
            reject(new Error(`Paddle.Setup() failed: ${(err as Error).message}`));
          }
        }
      }, 50);

      // Timeout after 10s
      setTimeout(() => {
        clearInterval(checkInterval);
        if (win.Paddle) {
          try {
            win.Paddle.Setup({ environment, token: paddleKey });
            resolve(win.Paddle);
          } catch {
            reject(new Error('Paddle CDN script loaded but Setup failed'));
          }
        } else {
          reject(new Error('Paddle CDN script loaded but window.Paddle not found'));
        }
      }, 10000);
    };

    script.onerror = () => {
      reject(new Error('Failed to load Paddle CDN script'));
    };

    document.head.appendChild(script);
  });
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
  paddleLoadPromise = undefined;
}

// Re-export from pure-data module to avoid breaking existing imports
// New code should import from @/lib/paddle-constants directly
export { VARIANT_PRICE_IDS } from './paddle-constants';

/**
 * Open the Paddle checkout overlay for a given transaction ID.
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
    setupCheckoutListeners(paddle, onSuccess, onClose);
    return true;
  } catch (err) {
    console.error('[paddle] Failed to open checkout:', err);
    return false;
  }
}

/**
 * Open the Paddle checkout overlay directly with items (price IDs).
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
    console.log('[paddle] Opening checkout with', items.length, 'items');

    paddle.Checkout.open(checkoutOptions);
    setupCheckoutListeners(paddle, onSuccess, onClose);
    return true;
  } catch (err) {
    console.error('[paddle] Failed to open items-based checkout:', err);
    return false;
  }
}

/**
 * Set up event listeners for Paddle checkout completion and close.
 */
function setupCheckoutListeners(
  _paddle: PaddleWindow,
  onSuccess?: () => void,
  onClose?: () => void,
): void {
  if (typeof window === 'undefined') return;

  const messageHandler = (event: MessageEvent) => {
    try {
      if (event.data && typeof event.data === 'object') {
        const data = event.data as Record<string, unknown>;
        if (data.event === 'checkout.completed' || data.name === 'checkout.completed') {
          console.log('[paddle] Checkout completed via postMessage');
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

  if (onClose) {
    let overlayDetected = false;
    const checkClosed = setInterval(() => {
      const overlay = document.querySelector('[data-paddle-overlay]') ||
        document.querySelector('iframe[src*="paddle"]') ||
        document.querySelector('.paddle-checkout');

      if (overlay) {
        overlayDetected = true;
      } else if (overlayDetected) {
        clearInterval(checkClosed);
        onClose();
        window.removeEventListener('message', messageHandler);
      }
    }, 1000);
    setTimeout(() => clearInterval(checkClosed), 600000);
  }
}
