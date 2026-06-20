/**
 * PARWA Demo Billing API
 *
 * GET  /api/demo/billing         — Get bill summary for a demo session
 * POST /api/demo/billing/estimate — Calculate bill estimate
 * POST /api/demo/billing/payment  — Create a payment checkout URL
 */

import { NextRequest, NextResponse } from 'next/server';
import { getDemoSession, calculateBillSummary, generateId } from '@/lib/demo-store';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const sessionId = searchParams.get('session_id');

    if (!sessionId) {
      return NextResponse.json(
        { error: { code: 'MISSING_SESSION_ID', message: 'session_id is required' } },
        { status: 400 },
      );
    }

    const session = getDemoSession(sessionId);
    if (!session) {
      return NextResponse.json(
        { error: { code: 'SESSION_NOT_FOUND', message: 'Demo session not found' } },
        { status: 404 },
      );
    }

    const bill_summary = calculateBillSummary(session.variant_tier, 'ecommerce');

    return NextResponse.json({
      bill_summary,
      estimate: {
        industry: 'ecommerce',
        ticket_volume: session.variant_tier === 'starter' ? 1000 : session.variant_tier === 'growth' ? 5000 : 15000,
        selected_variants: [],
        plan: session.variant_tier,
        bill_summary,
      },
    });
  } catch (error) {
    return NextResponse.json(
      { error: { code: 'BILLING_GET_ERROR', message: 'Failed to get billing info' } },
      { status: 500 },
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Estimate endpoint
    if (body.variant_id && body.ticket_volume !== undefined) {
      const { variant_id, industry, ticket_volume } = body;
      const bill_summary = calculateBillSummary(
        (variant_id as 'starter' | 'growth' | 'high') || 'starter',
        industry || 'ecommerce',
        ticket_volume || 1000,
      );

      return NextResponse.json({ bill_summary });
    }

    // Payment endpoint
    if (body.provider && body.amount) {
      const { provider, amount, currency, variant_id, industry } = body;

      // Simulate payment checkout URL (in production, this would call Paddle/Stripe/Razorpay)
      const transactionId = generateId('pay');
      const simulatedCheckoutUrl = `https://${provider}.com/checkout/${transactionId}`;

      return NextResponse.json({
        checkout_url: simulatedCheckoutUrl,
        transaction_id: transactionId,
        provider,
        status: 'pending',
        amount: String(amount),
        currency: currency || 'USD',
      });
    }

    return NextResponse.json(
      { error: { code: 'INVALID_REQUEST', message: 'Provide variant_id + ticket_volume for estimate, or provider + amount for payment' } },
      { status: 400 },
    );
  } catch (error) {
    return NextResponse.json(
      { error: { code: 'BILLING_ERROR', message: error instanceof Error ? error.message : 'Billing request failed' } },
      { status: 500 },
    );
  }
}
