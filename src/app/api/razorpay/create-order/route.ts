/**
 * SHOBH Create Razorpay Order API
 * 
 * POST /api/razorpay/create-order
 * Creates a Razorpay order and saves payment record to Supabase
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAuthenticatedUserId } from '@/lib/api-auth';
import { createPayment, getUserDetails } from '@/lib/supabase-db';
import crypto from 'crypto';

// Razorpay credentials from env
const RAZORPAY_KEY_ID = process.env.RAZORPAY_KEY_ID;
const RAZORPAY_KEY_SECRET = process.env.RAZORPAY_KEY_SECRET;

export async function POST(request: NextRequest) {
  try {
    if (!RAZORPAY_KEY_ID || !RAZORPAY_KEY_SECRET) {
      return NextResponse.json(
        { error: 'Razorpay not configured' },
        { status: 500 }
      );
    }

    const body = await request.json();
    const { amount, currency = 'USD', receipt, plan_id, plan_name } = body;
    
    // User identity must come from a verified access token.
    const userId = await getAuthenticatedUserId(request);
    if (!userId) return NextResponse.json({ error: 'unauthorized', message: 'Authentication required' }, { status: 401 });

    if (typeof amount !== 'number' || !Number.isSafeInteger(amount) || amount <= 0 || amount > 100000000) {
      return NextResponse.json(
        { error: 'Invalid amount' },
        { status: 400 }
      );
    }

    // Amount should be in smallest currency unit (cents for USD, paise for INR)
    const amountInSmallestUnit = Math.round(amount);

    // Generate receipt if not provided
    const orderReceipt = receipt || `receipt_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    console.log(`[Razorpay] Creating order for ${amountInSmallestUnit} ${currency}`);

    // Call Razorpay API to create order
    const razorpayResponse = await fetch('https://api.razorpay.com/v1/orders', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Basic ${Buffer.from(`${RAZORPAY_KEY_ID}:${RAZORPAY_KEY_SECRET}`).toString('base64')}`,
      },
      body: JSON.stringify({
        amount: amountInSmallestUnit,
        currency,
        receipt: orderReceipt,
        notes: {
          ...(userId && { user_id: userId }),
          ...(plan_id && { plan_id }),
          ...(plan_name && { plan_name }),
        },
      }),
    });

    if (!razorpayResponse.ok) {
      const errorData = await razorpayResponse.json().catch(() => ({}));
      console.error('[Razorpay] Order creation failed:', errorData);
      
      return NextResponse.json(
        { 
          error: 'order_creation_failed', 
          message: errorData.error?.description || 'Failed to create Razorpay order' 
        },
        { status: 500 }
      );
    }

    const orderData = await razorpayResponse.json();

    // Save payment record to Supabase (status: pending)
    try {
        await createPayment({
          user_id: userId,
          amount: amountInSmallestUnit,
          currency,
          status: 'pending',
          razorpay_order_id: orderData.id,
          plan_id: plan_id,
          plan_name: plan_name || 'Subscription',
        });
        
        console.log(`[Razorpay] ✅ Order created & saved to DB: ${orderData.id}`);
      } catch (dbError) {
        console.error('[Razorpay] Could not save payment record:', dbError);
        return NextResponse.json({ error: 'payment_record_failed', message: 'Unable to initialize payment record' }, { status: 503 });
      }

    return NextResponse.json({
      success: true,
      order_id: orderData.id,
      amount: orderData.amount,
      currency: orderData.currency,
      key_id: RAZORPAY_KEY_ID, // Return key for frontend
    });
  } catch (error) {
    console.error('[Razorpay Create Order Error]:', error);
    return NextResponse.json(
      { error: 'internal_error', message: 'Failed to create order' },
      { status: 500 }
    );
  }
}
