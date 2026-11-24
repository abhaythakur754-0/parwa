/**
 * SHOBH Verify Razorpay Payment API
 * 
 * POST /api/razorpay/verify-payment
 * Verifies payment signature and updates status in Supabase
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAuthenticatedUserId } from '@/lib/api-auth';
import { updatePaymentStatus, createSubscription, getUserDetails, db } from '@/lib/supabase-db';
import crypto from 'crypto';

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
    const { 
      razorpay_order_id, 
      razorpay_payment_id, 
      razorpay_signature,
    } = body;

    // Validate required fields
    if (!razorpay_order_id || !razorpay_payment_id || !razorpay_signature) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      );
    }

    // Identity must come from the verified access token, never the request body.
    const userId = await getAuthenticatedUserId(request);
    if (!userId) return NextResponse.json({ error: 'unauthorized', message: 'Authentication required' }, { status: 401 });

    const paymentRecord = await db.from('payments').select('*', {
      filter: { razorpay_order_id, user_id: userId }, single: true,
    });
    if (!paymentRecord) return NextResponse.json({ error: 'payment_not_found' }, { status: 404 });
    if (paymentRecord.status === 'completed') return NextResponse.json({ success: true, verified: true, payment_id: paymentRecord.razorpay_payment_id, order_id: razorpay_order_id, message: 'Payment already verified' });
    if (paymentRecord.status !== 'pending') return NextResponse.json({ error: 'payment_not_pending' }, { status: 409 });

    console.log(`[Razorpay] Verifying payment: ${razorpay_payment_id}`);

    // Verify signature
    const generatedSignature = crypto
      .createHmac('sha256', RAZORPAY_KEY_SECRET)
      .update(`${razorpay_order_id}|${razorpay_payment_id}`)
      .digest('hex');

    const expected = Buffer.from(generatedSignature, 'hex');
    const received = typeof razorpay_signature === 'string' && /^[a-f0-9]{64}$/i.test(razorpay_signature) ? Buffer.from(razorpay_signature, 'hex') : Buffer.alloc(0);
    if (expected.length !== received.length || !crypto.timingSafeEqual(expected, received)) {
      console.error('[Razorpay] ❌ Signature mismatch!');
      
      // Do not mutate a payment record on an untrusted failed verification attempt.

      return NextResponse.json(
        { error: 'signature_verification_failed', message: 'Payment signature is invalid' },
        { status: 400 }
      );
    }

    // Confirm the payment directly with Razorpay; a valid HMAC alone is not
    // enough to prove the payment was captured for this exact order/amount.
    const providerResponse = await fetch(`https://api.razorpay.com/v1/payments/${encodeURIComponent(razorpay_payment_id)}`, {
      headers: {
        Authorization: `Basic ${Buffer.from(`${RAZORPAY_KEY_ID}:${RAZORPAY_KEY_SECRET}`).toString('base64')}`,
      },
      cache: 'no-store',
    });
    if (!providerResponse.ok) {
      return NextResponse.json({ error: 'payment_status_unavailable' }, { status: 502 });
    }
    const providerPayment = await providerResponse.json();
    if (
      providerPayment.order_id !== razorpay_order_id ||
      providerPayment.status !== 'captured' ||
      providerPayment.amount !== paymentRecord.amount ||
      providerPayment.currency !== paymentRecord.currency
    ) {
      return NextResponse.json({ error: 'payment_not_captured_or_mismatched' }, { status: 409 });
    }

    try {
      if (paymentRecord.plan_id && paymentRecord.amount) {
        const existingSubscription = await db.from('subscriptions').select('*', {
          filter: { user_id: userId, razorpay_order_id }, single: true,
        });
        if (!existingSubscription) {
          try {
            await createSubscription({
              user_id: userId,
              plan_id: paymentRecord.plan_id,
              plan_name: paymentRecord.plan_name || paymentRecord.plan_id.toUpperCase(),
              billing_cycle: 'monthly',
              amount: Math.round(paymentRecord.amount),
              currency: paymentRecord.currency || 'USD',
              razorpay_order_id,
            });
          } catch (insertError) {
            // A unique order-id index makes concurrent verification idempotent.
            const racedSubscription = await db.from('subscriptions').select('*', {
              filter: { user_id: userId, razorpay_order_id }, single: true,
            });
            if (!racedSubscription) throw insertError;
          }
        }
      }

      await updatePaymentStatus(razorpay_order_id, 'completed', {
        razorpay_payment_id,
        razorpay_signature,
        payment_method: 'razorpay',
        updated_at: new Date().toISOString(),
      }, userId);

      sendReceiptEmail(userId, {
        amount: Math.round((paymentRecord.amount || 0) / 100),
        plan_name: paymentRecord.plan_name || 'Subscription',
        order_id: razorpay_order_id,
        status: 'completed',
      }).catch(err => console.warn('[Email] Receipt failed:', err));
    } catch (dbError) {
      console.error('[Razorpay] Payment persistence failed:', dbError);
      return NextResponse.json({ error: 'payment_persistence_failed' }, { status: 503 });
    }

    return NextResponse.json({
      success: true,
      verified: true,
      payment_id: razorpay_payment_id,
      order_id: razorpay_order_id,
      message: 'Payment verified and recorded successfully',
      subscription_created: Boolean(paymentRecord.plan_id),
    });
  } catch (error) {
    console.error('[Razorpay Verify Error]:', error);
    return NextResponse.json(
      { error: 'verification_failed', message: 'Failed to verify payment' },
      { status: 500 }
    );
  }
}

// Helper function to send receipt email (non-blocking)
async function sendReceiptEmail(userId: string, receiptData: {
  amount: number;
  plan_name: string;
  order_id: string;
  status: string;
}) {
  try {
    // Get user details for email
    const userDetails = await getUserDetails(userId);
    
    if (userDetails?.work_email) {
      const { sendPaymentReceipt } = await import('@/lib/email-brevo');
      
      await sendPaymentReceipt({
        to: userDetails.work_email,
        userName: userDetails.full_name,
        amount: receiptData.amount,
        planName: receiptData.plan_name,
        orderId: receiptData.order_id,
        status: receiptData.status as 'completed' | 'processing' | 'failed',
      });
      
      console.log(`[Email] 📧 Receipt sent to ${userDetails.work_email}`);
    }
  } catch (emailError) {
    console.error('[Email] Failed to send receipt:', emailError);
  }
}
