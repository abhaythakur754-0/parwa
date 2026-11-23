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

const RAZORPAY_KEY_SECRET = process.env.RAZORPAY_KEY_SECRET;

export async function POST(request: NextRequest) {
  try {
    if (!RAZORPAY_KEY_SECRET) {
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
      
      // Update payment status to failed
      if (userId && paymentRecord.status === 'pending') {
        try {
          await updatePaymentStatus(razorpay_order_id, 'failed', {
            error_message: 'Signature verification failed',
          });
        } catch (e) { /* ignore */ }
      }

      return NextResponse.json(
        { error: 'signature_verification_failed', message: 'Payment signature is invalid' },
        { status: 400 }
      );
    }

    // ✅ Signature valid - payment verified!
    console.log(`[Razorpay] ✅ Payment verified successfully!`);

    // Update payment record in Supabase
    let updatedPayment;
    if (userId && razorpay_order_id) {
      try {
        updatedPayment = await updatePaymentStatus(razorpay_order_id, 'completed', {
          razorpay_payment_id,
          razorpay_signature,
          payment_method: 'razorpay',
          updated_at: new Date().toISOString(),
        });

        // Create or update subscription if plan info provided
        if (paymentRecord.plan_id && paymentRecord.amount) {
          await createSubscription({
            user_id: userId,
            plan_id: paymentRecord.plan_id,
            plan_name: paymentRecord.plan_name || paymentRecord.plan_id.toUpperCase(),
            billing_cycle: 'monthly',
            amount: Math.round(paymentRecord.amount),
            currency: paymentRecord.currency || 'INR',
          });
          
          console.log(`[Razorpay] 📋 Subscription created: ${paymentRecord.plan_id}`);
        }

        // Send payment receipt email (async - don't block response)
        sendReceiptEmail(userId, {
          amount: Math.round((paymentRecord.amount || 0) / 100),
          plan_name: paymentRecord.plan_name || 'Subscription',
          order_id: razorpay_order_id,
          status: 'completed',
        }).catch(err => console.warn('[Email] Receipt failed:', err));

      } catch (dbError) {
        console.error('[Razorpay] DB update failed:', dbError);
        // Don't fail the verification - payment was successful
      }
    }

    return NextResponse.json({
      success: true,
      verified: true,
      payment_id: razorpay_payment_id,
      order_id: razorpay_order_id,
      message: 'Payment verified and recorded successfully',
      ...(updatedPayment && { subscription_created: true }),
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
