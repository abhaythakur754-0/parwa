/**
 * Create a one-time Razorpay order for the authenticated user.
 * Subscription activation is handled by the canonical billing API/webhook,
 * never by caller-supplied plan or user IDs in this legacy checkout route.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAuthenticatedUserId } from '@/lib/authenticated-user';
import { createPayment } from '@/lib/supabase-db';

const RAZORPAY_KEY_ID = process.env.RAZORPAY_KEY_ID;
const RAZORPAY_KEY_SECRET = process.env.RAZORPAY_KEY_SECRET;
const ALLOWED_CURRENCIES = new Set(['USD', 'INR']);

export async function POST(request: NextRequest) {
  const userId = await getAuthenticatedUserId(request);
  if (!userId) {
    return NextResponse.json(
      { error: 'unauthorized', message: 'User not authenticated' },
      { status: 401 },
    );
  }

  if (!RAZORPAY_KEY_ID || !RAZORPAY_KEY_SECRET) {
    return NextResponse.json(
      { error: 'payment_provider_unavailable', message: 'Razorpay is not configured' },
      { status: 503 },
    );
  }

  try {
    const body = await request.json().catch(() => null);
    const amount = body?.amount;
    const currency = typeof body?.currency === 'string' ? body.currency.toUpperCase() : 'USD';

    // Amount is already in the currency's smallest unit (cents/paise).
    if (!Number.isSafeInteger(amount) || amount <= 0 || amount > 100_000_000) {
      return NextResponse.json(
        { error: 'validation_error', message: 'Amount must be a positive integer in the smallest currency unit' },
        { status: 400 },
      );
    }
    if (!ALLOWED_CURRENCIES.has(currency)) {
      return NextResponse.json(
        { error: 'validation_error', message: 'Unsupported payment currency' },
        { status: 400 },
      );
    }

    const receipt = `parwa_${crypto.randomUUID()}`;
    const providerResponse = await fetch('https://api.razorpay.com/v1/orders', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Basic ${Buffer.from(`${RAZORPAY_KEY_ID}:${RAZORPAY_KEY_SECRET}`).toString('base64')}`,
      },
      body: JSON.stringify({
        amount,
        currency,
        receipt,
        notes: { user_id: userId, purpose: 'one_time_payment' },
      }),
      signal: AbortSignal.timeout(15_000),
    });

    const order = await providerResponse.json().catch(() => ({}));
    if (!providerResponse.ok || typeof order.id !== 'string') {
      console.error('[Razorpay] Order creation failed:', providerResponse.status);
      return NextResponse.json(
        { error: 'order_creation_failed', message: 'Razorpay could not create the order' },
        { status: 502 },
      );
    }

    try {
      const saved = await createPayment({
        user_id: userId,
        amount: order.amount,
        currency: order.currency,
        status: 'pending',
        razorpay_order_id: order.id,
        plan_name: 'One-time payment',
      });
      if (saved?.error) throw new Error('Payment record could not be saved');
    } catch (dbError) {
      console.error('[Razorpay] Payment record persistence failed:', dbError);
      return NextResponse.json(
        { error: 'payment_record_failed', message: 'Could not record the payment order. Please try again.' },
        { status: 503 },
      );
    }

    return NextResponse.json({
      success: true,
      order_id: order.id,
      amount: order.amount,
      currency: order.currency,
      key_id: RAZORPAY_KEY_ID,
    });
  } catch (error) {
    console.error('[Razorpay Create Order Error]:', error);
    return NextResponse.json(
      { error: 'internal_error', message: 'Failed to create payment order' },
      { status: 500 },
    );
  }
}
