/**
 * PARWA Verify Razorpay Payment API
 * 
 * POST /api/razorpay/verify-payment
 * Verifies payment signature and updates status in Supabase
 */

import { NextRequest, NextResponse } from 'next/server';
import { updatePaymentStatus, createSubscription, getUserDetails } from '@/lib/supabase-db';
import crypto from 'crypto';

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

  const url = new URL(req.url);
  return url.searchParams.get('user_id');
}

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
      user_id: bodyUserId,
      plan_id,
      plan_name,
      amount,
    } = body;

    // Validate required fields
    if (!razorpay_order_id || !razorpay_payment_id || !razorpay_signature) {
      return NextResponse.json(
        { error: 'Missing required fields' },
        { status: 400 }
      );
    }

    // Get user ID from auth or body
    let userId = getUserId(request) || bodyUserId;

    console.log(`[Razorpay] Verifying payment: ${razorpay_payment_id}`);

    // Verify signature
    const generatedSignature = crypto
      .createHmac('sha256', RAZORPAY_KEY_SECRET)
      .update(`${razorpay_order_id}|${razorpay_payment_id}`)
      .digest('hex');

    if (generatedSignature !== razorpay_signature) {
      console.error('[Razorpay] ❌ Signature mismatch!');
      
      // Update payment status to failed
      if (userId) {
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
        if (plan_id && amount) {
          await createSubscription({
            user_id: userId,
            plan_id,
            plan_name: plan_name || plan_id.toUpperCase(),
            billing_cycle: 'monthly',
            amount: Math.round(amount),
            currency: 'INR',
          });
          
          console.log(`[Razorpay] 📋 Subscription created: ${plan_id}`);
        }

        // Send payment receipt email (async - don't block response)
        sendReceiptEmail(userId, {
          amount: Math.round((amount || 0) / 100), // Convert back to rupees
          plan_name: plan_name || 'Subscription',
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
        ...receiptData,
      });
      
      console.log(`[Email] 📧 Receipt sent to ${userDetails.work_email}`);
    }
  } catch (emailError) {
    console.error('[Email] Failed to send receipt:', emailError);
  }
}
