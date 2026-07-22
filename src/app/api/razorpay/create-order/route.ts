/**
 * PARWA Create Razorpay Order API
 * 
 * POST /api/razorpay/create-order
 * Creates a Razorpay order and saves payment record to Supabase
 */

import { NextRequest, NextResponse } from 'next/server';
import { createPayment, getUserDetails } from '@/lib/supabase-db';
import crypto from 'crypto';

// Razorpay credentials from env
const RAZORPAY_KEY_ID = process.env.RAZORPAY_KEY_ID;
const RAZORPAY_KEY_SECRET = process.env.RAZORPAY_KEY_SECRET;

function getUserId(req: NextRequest): string | null {
  const authHeader = req.headers.get('authorization');
  if (authHeader) return authHeader.replace('Bearer ', '');

  const cookieHeader = req.headers.get('cookie');
  if (cookieHeader) {
    const cookies = Object.fromEntries(
      cookieHeader.split(';').map((c) => {
        const [key, ...val] = c.trim().split('=');
        return [key, val.join('=')];
      })
    );
    if (cookies.parwa_at) return cookies.parwa_at;
    if (cookies.user_id) return cookies.user_id;
  }

  // For demo/testing, allow user_id in body
  return null;
}

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
    
    // Get user ID
    let userId = getUserId(request);
    
    // Fallback: check body for user_id (for testing)
    if (!userId && body.user_id) {
      userId = body.user_id;
    }

    if (!amount || amount <= 0) {
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
    if (userId) {
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
        console.warn('[Razorpay] Could not save to DB:', dbError);
        // Continue even if DB save fails - payment can be reconciled later
      }
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
