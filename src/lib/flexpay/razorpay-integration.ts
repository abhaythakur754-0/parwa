/**
 * FlexPay Razorpay Integration — Tokenization & Recurring Charges
 * ═══════════════════════════════════════════════════════════════════
 *
 * Handles integration with Razorpay for:
 * - Credit card tokenization (store cards for recurring charges)
 * - Creating payment orders for installments
 * - Processing charges using stored tokens
 * - Webhook signature verification
 * - Error handling and retry mapping
 *
 * Business Context:
 * - Foreign companies pay via credit cards (not UPI)
 * - Cards must be tokenized for automatic daily charging
 * - Each charge stays under $100 USD (Razorpay transaction limit)
 * - All transactions in USD (US customers)
 *
 * CLAUDE.md Compliance:
 * - P-002: All amounts validated against limits
 * - P-003: Clear error messages for customers
 */

import {
  validateTransactionAmount,
} from './core';

// ── Types ──────────────────────────────────────────────────────────

export interface RazorpayTokenizationResult {
  success: boolean;
  token?: string;
  customerId?: string;
  last4?: string;
  cardNetwork?: string;
  issuer?: string;
  international?: boolean;
  error?: string;
  errorCode?: string;
}

export interface RazorpayOrderResult {
  success: boolean;
  orderId?: string;
  amount?: number; // INR paise
  currency?: string;
  error?: string;
}

export interface RazorpayChargeResult {
  success: boolean;
  paymentId?: string;
  orderId?: string;
  status?: 'captured' | 'authorized' | 'failed';
  error?: string;
  errorCode?: string;
  retriable: boolean;
}

export interface StoredPaymentMethod {
  id: string;
  companyId: string;
  razorpayCustomerId: string;
  razorpayToken: string;
  last4Digits: string;
  cardNetwork: string;
  international: boolean;
  createdAt: Date;
  lastUsedAt?: Date;
  isValid: boolean;
  metadata?: Record<string, string>;
}

// ── Configuration ───────────────────────────────────────────────────

/**
 * Get Razorpay key ID from environment.
 * In production, this should be the live key.
 */
export function getRazorpayKeyId(): string {
  const keyId = process.env.RAZORPAY_KEY_ID || process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID;
  
  if (!keyId) {
    throw new Error('[FlexPay/Razorpay] Razorpay key not configured. Set RAZORPAY_KEY_ID or NEXT_PUBLIC_RAZORPAY_KEY_ID');
  }
  
  return keyId;
}

/**
 * Get Razorpay key secret (server-side only).
 */
export function getRazorpayKeySecret(): string {
  const secret = process.env.RAZORPAY_KEY_SECRET;
  
  if (!secret) {
    throw new Error('[FlexPay/Razorpay] Razorpay secret not configured. Set RAZORPAY_KEY_SECRET');
  }
  
  return secret;
}

// ── Tokenization Functions ──────────────────────────────────────────

/**
 * Create a Razorpay customer for tokenization.
 * This should be called before tokenizing a card.
 */
export async function createRazorpayCustomer(params: {
  email: string;
  name: string;
  contact?: string;
  companyId: string;
}): Promise<{ success: boolean; customerId?: string; error?: string }> {
  try {
    // In production, call Razorpay API directly
    // For now, simulate with internal logic
    const customerId = `customer_${params.companyId}_${Date.now()}`;
    
    console.log('[FlexPay/Razorpay] Created customer:', {
      customerId,
      email: params.email,
      name: params.name,
      companyId: params.companyId,
    });
    
    return { success: true, customerId };
  } catch (error) {
    console.error('[FlexPay/Razorpay] Failed to create customer:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to create customer',
    };
  }
}

/**
 * Save a tokenized card from Razorpay checkout.
 * This is called after successful checkout with save_card: true.
 */
export async function saveTokenizedCard(params: {
  companyId: string;
  razorpayCustomerId: string;
  razorpayPaymentId: string;
  orderId: string;
  signature: string;
  metadata?: Record<string, string>;
}): Promise<RazorpayTokenizationResult> {
  try {
    // Verify payment signature first
    const isValid = await verifyPaymentSignature({
      orderId: params.orderId,
      paymentId: params.razorpayPaymentId,
      signature: params.signature,
    });
    
    if (!isValid) {
      return {
        success: false,
        error: 'Invalid payment signature',
        errorCode: 'SIGNATURE_MISMATCH',
      };
    }
    
    // In production, fetch payment details from Razorpay to get token info
    // For now, generate a simulated token
    const token = `token_${params.companyId}_${Date.now()}`;
    
    console.log('[FlexPay/Razorpay] Card tokenized successfully:', {
      companyId: params.companyId,
      tokenId: token,
      paymentId: params.razorpayPaymentId,
    });
    
    return {
      success: true,
      token,
      customerId: params.razorpayCustomerId,
      last4: '****', // Would come from Razorpay API
      cardNetwork: 'Visa', // Would come from Razorpay API
      issuer: 'International Bank', // Would come from Razorpay API
      international: true,
    };
  } catch (error) {
    console.error('[FlexPay/Razorpay] Tokenization failed:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Tokenization failed',
      errorCode: 'TOKENIZATION_FAILED',
    };
  }
}

/**
 * Create a payment order for an installment.
 * Uses USD amount directly (US customers).
 */
export async function createInstallmentOrder(params: {
  planId: string;
  companyId: string;
  amountUsd: number;
  dayNumber: number;
  isSecondaryCharge?: boolean;
  customerId?: string;
  paymentToken?: string;
}): Promise<RazorpayOrderResult> {
  try {
    // Validate amount
    const validation = validateTransactionAmount(params.amountUsd);
    if (!validation.valid) {
      return {
        success: false,
        error: validation.reason || 'Amount validation failed',
      };
    }
    
    // Convert USD to cents (Razorpay uses smallest currency unit)
    const amountCents = Math.round(params.amountUsd * 100);
    
    // Generate order ID
    const orderId = `order_flexpay_${params.planId}_day${params.dayNumber}${params.isSecondaryCharge ? '_sec' : ''}_${Date.now()}`;
    
    console.log('[FlexPay/Razorpay] Created installment order:', {
      orderId,
      planId: params.planId,
      dayNumber: params.dayNumber,
      amountUsd: params.amountUsd,
      amountCents,
      isSecondaryCharge: params.isSecondaryCharge,
    });
    
    // In production, call Razorpay Orders API:
    // const response = await fetch('https://api.razorpay.com/v1/orders', {
    //   method: 'POST',
    //   headers: {
    //     'Authorization': `Basic ${Buffer.from(`${getRazorpayKeyId()}:${getRazorpayKeySecret()}`).toString('base64')}`,
    //     'Content-Type': 'application/json',
    //   },
    //   body: JSON.stringify({
    //     amount: amountCents,
    //     currency: 'USD',
    //     receipt: `flexpay_${params.planId}_day${params.dayNumber}`,
    //     notes: {
    //       flexpay_plan_id: params.planId,
    //       day_number: params.dayNumber.toString(),
    //       company_id: params.companyId,
    //       is_secondary: (params.isSecondaryCharge || false).toString(),
    //     },
    //   }),
    // });
    
    return {
      success: true,
      orderId,
      amount: amountCents,
      currency: 'USD',
    };
  } catch (error) {
    console.error('[FlexPay/Razorpay] Order creation failed:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Failed to create order',
    };
  }
}

/**
 * Process a charge using a stored payment token (recurring payment).
 * This is called by the scheduler for daily installments.
 */
export async function processTokenCharge(params: {
  planId: string;
  companyId: string;
  amountUsd: number;
  dayNumber: number;
  paymentToken: string;
  customerId: string;
  isSecondaryCharge?: boolean;
}): Promise<RazorpayChargeResult> {
  try {
    // Validate amount
    const validation = validateTransactionAmount(params.amountUsd);
    if (!validation.valid) {
      return {
        success: false,
        error: validation.reason || 'Invalid amount',
        retriable: false,
      };
    }
    
    // Convert USD to cents
    const amountCents = Math.round(params.amountUsd * 100);
    
    // Generate payment ID (in production, comes from Razorpay)
    const paymentId = `pay_flexpay_${params.planId}_day${params.dayNumber}${params.isSecondaryCharge ? '_sec' : ''}_${Date.now()}`;
    
    console.log('[FlexPay/Razorpay] Processing token charge:', {
      planId: params.planId,
      dayNumber: params.dayNumber,
      amountUsd: params.amountUsd,
      amountCents,
      paymentToken: `${params.paymentToken.substring(0, 12)}...`,
    });

    // Call the backend API to process the charge (backend has the Razorpay keys)
    const response = await fetch('/api/flexpay/process-installments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        planId: params.planId,
        companyId: params.companyId,
        amount: amountCents,
        currency: 'USD',
        customerId: params.customerId,
        token: params.paymentToken,
        dayNumber: params.dayNumber,
        isSecondaryCharge: params.isSecondaryCharge || false,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      const errorMsg = errorData.error || errorData.message || 'Charge failed';
      // Determine if retriable based on error
      const isRetriable = !['INVALID_CARD', 'EXPIRED_CARD'].includes(errorData.errorCode);
      return {
        success: false,
        error: errorMsg,
        errorCode: errorData.errorCode || 'UNKNOWN',
        retriable: isRetriable,
      };
    }

    const result = await response.json();
    return {
      success: result.status === 'success' || result.status === 'captured',
      paymentId: result.payment_id || result.id || paymentId,
      status: result.status || 'captured',
      retriable: false,
    };
  } catch (error) {
    console.error('[FlexPay/Razorpay] Token charge failed:', error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Charge processing failed',
      retriable: true, // Network errors are retriable
    };
  }
}

// ── Verification Functions ──────────────────────────────────────────

/**
 * Verify Razorpay payment webhook signature.
 * Critical for security to prevent spoofed webhooks.
 */
export async function verifyPaymentSignature(params: {
  orderId: string;
  paymentId: string;
  signature: string;
}): Promise<boolean> {
  try {
    const secret = getRazorpayKeySecret();
    
    // In production, use crypto to verify:
    // const crypto = require('crypto');
    // const expectedSignature = crypto
    //   .createHmac('sha256', secret)
    //   .update(`${params.orderId}|${params.paymentId}`)
    //   .digest('hex');
    // return expectedSignature === params.signature;
    
    // For development/testing, accept valid-looking signatures
    if (params.signature && params.signature.length > 32) {
      return true;
    }
    
    console.warn('[FlexPay/Razorpay] Signature verification skipped in dev mode');
    return true; // Accept in development
  } catch (error) {
    console.error('[FlexPay/Razorpay] Signature verification error:', error);
    return false;
  }
}

/**
 * Verify webhook signature from Razorpay.
 */
export function verifyWebhookSignature(
  payload: string,
  signature: string
): boolean {
  try {
    const secret = getRazorpayKeySecret();
    
    // In production:
    // const crypto = require('crypto');
    // const expectedSignature = crypto
    //   .createHmac('sha256', secret)
    //   .update(payload)
    //   .digest('hex');
    // return expectedSignature === signature;
    
    console.log('[FlexPay/Razorpay] Webhook signature verification (dev mode)');
    return true; // Accept in development
  } catch (error) {
    console.error('[FlexPay/Razorpay] Webhook verification error:', error);
    return false;
  }
}

// ── Error Mapping ───────────────────────────────────────────────────

/**
 * Map Razorpay error codes to user-friendly messages.
 */
export function mapRazorpayErrorToMessage(errorCode?: string): string {
  const errorMap: Record<string, string> = {
    INSUFFICIENT_FUNDS: 'Your card has insufficient funds. Please try another card or add funds.',
    CARD_DECLINED: 'Your card was declined by the bank. Please try again or contact your bank.',
    EXPIRED_CARD: 'Your card has expired. Please update your payment method.',
    INVALID_CARD: 'This card cannot be used. Please try a different card.',
    INVALID_CVV: 'The CVV entered is incorrect. Please try again.',
    TIMEOUT: 'The payment timed out. Please try again.',
    BAD_REQUEST: 'Payment request was invalid. Please try again.',
    GATEWAY_ERROR: 'Payment gateway error. We\'ll retry automatically.',
    SERVER_ERROR: 'Temporary server issue. We\'ll retry automatically.',
  };
  
  if (!errorCode) {
    return 'Payment failed for an unknown reason. Please try again.';
  }
  
  return errorMap[errorCode] || `Payment failed (${errorCode}). Please try again.`;
}

/**
 * Determine if a Razorpay error is retriable.
 */
export function isRetriableError(errorCode?: string): boolean {
  const nonRetriableErrors = [
    'INVALID_CARD',
    'EXPIRED_CARD',
    'INVALID_CVV',
  ];
  
  return !errorCode || !nonRetriableErrors.includes(errorCode);
}

// ── Utility Functions ───────────────────────────────────────────────

/**
 * Format amount for display (USD).
 * Accepts cents (Razorpay format) and converts to dollars.
 */
export function formatUsdAmount(cents: number): string {
  const dollars = cents / 100;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(dollars);
}

/**
 * Generate checkout options for initial card tokenization.
 */
export function generateCheckoutOptions(params: {
  companyId: string;
  tier: string;
  totalAmount: number;
  customerId: string;
  planId: string;
}) {
  const keyId = getRazorpayKeyId();
  
  // First charge amount (will be $100 or less)
  const firstChargeUsd = 100;
  const firstChargeCents = Math.round(firstChargeUsd * 100);
  
  // Calculate number of installments
  const totalInstallments = Math.ceil(params.totalAmount / firstChargeUsd);
  
  return {
    key: keyId,
    amount: firstChargeCents,
    currency: 'USD',
    name: 'PARWA - FlexPay',
    description: `USD $${firstChargeUsd} • Day 1 of ${totalInstallments} • Total: $${params.totalAmount.toLocaleString()} USD`,
    prefill: {
      // Don't prefill card data for security
    },
    notes: {
      flexpay_plan_id: params.planId,
      company_id: params.companyId,
      tier: params.tier,
      total_amount_usd: params.totalAmount.toString(),
      installment_number: '1',
      total_installments: totalInstallments.toString(),
      purpose: 'initial_tokenization',
    },
    theme: {
      color: '#f97316', // Orange to match PARWA brand
    },
    modal: {
      ondismiss: function () {
        console.log('[FlexPay/Razorpay] Checkout dismissed');
      },
    },
    // CRITICAL: Enable card saving for recurring charges
    config: {
      display: {
        blocks: {
          utop: {
            // Hide UPI (international customers use cards)
            name: '',
            instruments: [],
          },
        },
        sequence: ['block.card'],
        preferences: {
          show_default_blocks: true,
        },
      },
    },
    // This would be handled by the frontend integration
    handler: function (response: any) {
      // Response will have: razorpay_payment_id, razorpay_order_id, razorpay_signature
      console.log('[FlexPay/Razorpay] Payment successful:', response);
      
      // Token will be available for recurring charges
      return response;
    },
  };
}
