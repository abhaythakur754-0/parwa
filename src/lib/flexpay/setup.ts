/**
 * FlexPay Setup — Initialize with Razorpay Integration
 * ═══════════════════════════════════════════════════════════════════
 *
 * This module initializes the FlexPay scheduler with the actual
 * Razorpay payment processor for production use.
 *
 * Usage:
 * ```typescript
 * import '@/lib/flexpay/setup';
 * // Scheduler is now configured with Razorpay integration
 * ```
 *
 * Or call explicitly:
 * ```typescript
 * import { initializeFlexPayWithRazorpay } from '@/lib/flexpay/setup';
 * await initializeFlexPayWithRazorpay();
 * ```
 */

import { setPaymentProcessor } from './scheduler';
import { processTokenCharge, createInstallmentOrder } from './razorpay-integration';
import type { ChargeResult, PaymentProcessor } from './scheduler';

// Track if initialized
let isInitialized = false;

/**
 * Initialize FlexPay scheduler with Razorpay payment processor.
 * This enables real payment processing through Razorpay.
 */
export async function initializeFlexPayWithRazorpay(): Promise<void> {
  if (isInitialized) {
    console.log('[FlexPay/Setup] Already initialized');
    return;
  }

  // Create the payment processor using Razorpay integration
  const razorpayProcessor: PaymentProcessor = async (params) => {
    try {
      // Step 1: Create order in Razorpay
      const orderResult = await createInstallmentOrder({
        planId: params.planId,
        companyId: params.companyId,
        amountUsd: params.amount,
        dayNumber: parseInt(params.metadata?.day_number || '0', 10),
        isSecondaryCharge: params.metadata?.is_secondary === 'true',
        customerId: params.customerId,
        paymentToken: params.paymentToken,
      });

      if (!orderResult.success || !orderResult.orderId) {
        return {
          success: false,
          error: orderResult.error || 'Failed to create payment order',
          retriable: true,
        };
      }

      // Step 2: Process charge using stored token (for recurring payments)
      if (params.paymentToken && params.customerId) {
        const chargeResult = await processTokenCharge({
          planId: params.planId,
          companyId: params.companyId,
          amountUsd: params.amount,
          dayNumber: parseInt(params.metadata?.day_number || '0', 10),
          paymentToken: params.paymentToken,
          customerId: params.customerId,
          isSecondaryCharge: params.metadata?.is_secondary === 'true',
        });

        return {
          success: chargeResult.success,
          paymentId: chargeResult.paymentId,
          orderId: orderResult.orderId,
          error: chargeResult.error,
          errorCode: chargeResult.errorCode,
          retriable: chargeResult.retriable,
        };
      }

      // No token available - this shouldn't happen in normal flow
      return {
        success: false,
        error: 'No payment token available. Customer must complete tokenization first.',
        retriable: false,
      };

    } catch (error) {
      console.error('[FlexPay/Setup] Payment processing error:', error);
      
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Payment processing failed',
        retriable: true, // Network/system errors are retriable
      };
    }
  };

  // Set the processor
  setPaymentProcessor(razorpayProcessor);
  
  isInitialized = true;
  
  console.log('[FlexPay/Setup] Initialized with Razorpay payment processor');
}

/**
 * Check if FlexPay has been initialized.
 */
export function isFlexPayInitialized(): boolean {
  return isInitialized;
}

/**
 * Reset initialization state (useful for testing).
 */
export function resetInitialization(): void {
  isInitialized = false;
}

// Auto-initialize in non-test environments
if (process.env.NODE_ENV !== 'test') {
  // Don't auto-await - let it initialize asynchronously
  initializeFlexPayWithRazorpay().catch((err) => {
    console.error('[FlexPay/Setup] Auto-initialization failed:', err);
  });
}
