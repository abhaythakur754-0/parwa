/**
 * FlexPay Tokenization API Endpoint
 * ═══════════════════════════════════════════════════════════════════
 *
 * POST /api/flexpay/tokenize
 *
 * Handles initial card tokenization for FlexPay recurring charges:
 * - Creates Razorpay customer (if not exists)
 * - Returns checkout options for card collection
 * - Saves token after successful payment
 * - Stores payment method for future installments
 *
 * Request Body:
 * {
 *   companyId: string,
 *   email: string,
 *   name: string,
 *   contact?: string,
 *   tier: 'mini' | 'parwa' | 'high',
 *   planId: string,
 *   totalAmount: number,
 *   razorpayPaymentId?: string,  // After successful checkout
 *   razorpayOrderId?: string,     // After successful checkout
 *   razorpaySignature?: string    // After successful checkout
 * }
 *
 * Response:
 * {
 *   success: true,
 *   needsCheckout: boolean,       // If true, show Razorpay checkout
 *   checkoutOptions?: object,     // Options for Razorpay checkout
 *   tokenizationResult?: object,  // After successful payment
 * }
 */

import { NextRequest, NextResponse } from 'next/server';
import {
  createRazorpayCustomer,
  saveTokenizedCard,
  generateCheckoutOptions,
} from '@/lib/flexpay/razorpay-integration';
import { getPlan as getSchedulerPlan } from '@/lib/flexpay/scheduler';

// ── Types ──────────────────────────────────────────────────────────

interface TokenizeRequest {
  companyId: string;
  email: string;
  name: string;
  contact?: string;
  tier: string;
  planId: string;
  totalAmount: number;
  // Post-checkout fields
  razorpayPaymentId?: string;
  razorpayOrderId?: string;
  razorpaySignature?: string;
}

// ── Validation ─────────────────────────────────────────────────────

function validateTokenizeRequest(body: Partial<TokenizeRequest>): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (!body.companyId || body.companyId.trim().length === 0) {
    errors.push('companyId is required');
  }

  if (!body.email || !body.email.includes('@')) {
    errors.push('Valid email is required');
  }

  if (!body.name || body.name.trim().length === 0) {
    errors.push('name is required');
  }

  if (!body.tier || !['mini', 'parwa', 'high'].includes(body.tier)) {
    errors.push('tier must be one of: mini, parwa, high');
  }

  if (!body.planId || body.planId.trim().length === 0) {
    errors.push('planId is required');
  }

  if (!body.totalAmount || body.totalAmount <= 0) {
    errors.push('totalAmount must be greater than zero');
  }

  return { valid: errors.length === 0, errors };
}

// ── Handler ────────────────────────────────────────────────────────

export async function POST(req: NextRequest) {
  try {
    let body: TokenizeRequest;
    try {
      body = await req.json();
    } catch {
      return NextResponse.json(
        { success: false, error: 'Invalid JSON in request body' },
        { status: 400 }
      );
    }

    // Validate request
    const validation = validateTokenizeRequest(body);
    if (!validation.valid) {
      return NextResponse.json(
        { success: false, error: 'Validation failed', details: validation.errors },
        { status: 400 }
      );
    }

    // Verify plan exists
    const plan = getSchedulerPlan(body.planId);
    if (!plan) {
      return NextResponse.json(
        { success: false, error: 'Plan not found' },
        { status: 404 }
      );
    }

    // Check if this is a post-checkout call (saving token)
    if (body.razorpayPaymentId && body.razorpayOrderId && body.razorpaySignature) {
      return await handlePostCheckout(body);
    }

    // Otherwise, create customer and return checkout options
    return await initiateTokenization(body);

  } catch (error) {
    console.error('[FlexPay/Tokenize] Error:', error);
    
    const message = error instanceof Error ? error.message : 'Unknown error occurred';
    
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to process tokenization request',
        details: message 
      },
      { status: 500 }
    );
  }
}

// ── Helper Functions ───────────────────────────────────────────────

async function initiateTokenization(body: TokenizeRequest): Promise<NextResponse> {
  // Create or get Razorpay customer
  const customerResult = await createRazorpayCustomer({
    email: body.email,
    name: body.name,
    contact: body.contact,
    companyId: body.companyId,
  });

  if (!customerResult.success || !customerResult.customerId) {
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to create payment profile',
        details: customerResult.error 
      },
      { status: 500 }
    );
  }

  // Generate checkout options
  const checkoutOptions = generateCheckoutOptions({
    companyId: body.companyId,
    tier: body.tier,
    totalAmount: body.totalAmount,
    customerId: customerResult.customerId,
    planId: body.planId,
  });

  console.log('[FlexPay/Tokenize] Initiated tokenization:', {
    companyId: body.companyId,
    planId: body.planId,
    customerId: customerResult.customerId,
  });

  return NextResponse.json({
    success: true,
    needsCheckout: true,
    customerId: customerResult.customerId,
    checkoutOptions: {
      key: checkoutOptions.key,
      amount: checkoutOptions.amount,
      currency: checkoutOptions.currency,
      name: checkoutOptions.name,
      description: checkoutOptions.description,
      notes: checkoutOptions.notes,
      theme: checkoutOptions.theme,
      // Don't include handler in JSON response - it's a function
    },
    message: 'Complete the payment to save your card for automatic charging',
  });
}

async function handlePostCheckout(body: TokenizeRequest): Promise<NextResponse> {
  // Save the tokenized card
  const tokenResult = await saveTokenizedCard({
    companyId: body.companyId,
    razorpayCustomerId: '', // Would come from session/context
    razorpayPaymentId: body.razorpayPaymentId!,
    orderId: body.razorpayOrderId!,
    signature: body.razorpaySignature!,
    metadata: {
      tier: body.tier,
      planId: body.planId,
      totalAmount: body.totalAmount.toString(),
    },
  });

  if (!tokenResult.success) {
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to save payment method',
        details: tokenResult.error 
      },
      { status: 400 }
    );
  }

  console.log('[FlexPay/Tokenize] Card saved successfully:', {
    companyId: body.companyId,
    planId: body.planId,
    token: tokenResult.token,
    last4: tokenResult.last4,
  });

  return NextResponse.json({
    success: true,
    needsCheckout: false,
    tokenizationResult: {
      token: tokenResult.token,
      last4: tokenResult.last4,
      cardNetwork: tokenResult.cardNetwork,
      international: tokenResult.international,
    },
    message: 'Payment method saved successfully! Your FlexPay plan is now active.',
  });
}
