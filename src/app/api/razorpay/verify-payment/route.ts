/**
 * Verify a one-time Razorpay payment for the authenticated user.
 * This endpoint records payment only; subscription activation belongs to the
 * canonical billing webhook after server-side plan/price validation.
 */

import { NextRequest, NextResponse } from 'next/server';
import { createHmac, timingSafeEqual } from 'node:crypto';
import { getAuthenticatedUserId } from '@/lib/authenticated-user';
import { getUserDetails, updatePaymentStatus } from '@/lib/supabase-db';

const RAZORPAY_KEY_ID = process.env.RAZORPAY_KEY_ID;
const RAZORPAY_KEY_SECRET = process.env.RAZORPAY_KEY_SECRET;

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
    const orderId = body?.razorpay_order_id;
    const paymentId = body?.razorpay_payment_id;
    const signature = body?.razorpay_signature;

    if (
      typeof orderId !== 'string' || !orderId ||
      typeof paymentId !== 'string' || !paymentId ||
      typeof signature !== 'string' || !/^[a-f0-9]{64}$/i.test(signature)
    ) {
      return NextResponse.json(
        { error: 'validation_error', message: 'Missing or invalid Razorpay payment fields' },
        { status: 400 },
      );
    }

    const expected = createHmac('sha256', RAZORPAY_KEY_SECRET)
      .update(\`\${orderId}|\${paymentId}\`)
      .digest();
    const received = Buffer.from(signature, 'hex');
    if (received.length !== expected.length || !timingSafeEqual(received, expected)) {
      return NextResponse.json(
        { error: 'signature_verification_failed', message: 'Payment signature is invalid' },
        { status: 400 },
      );
    }

    const authorization = \`Basic \${Buffer.from(\`\${RAZORPAY_KEY_ID}:\${RAZORPAY_KEY_SECRET}\`).toString('base64')}\`;
    const [orderResponse, paymentResponse] = await Promise.all([
      fetch(\`https://api.razorpay.com/v1/orders/\${encodeURIComponent(orderId)}\`, {
        headers: { Authorization: authorization },
        signal: AbortSignal.timeout(15_000),
      }),
      fetch(\`https://api.razorpay.com/v1/payments/\${encodeURIComponent(paymentId)}\`, {
        headers: { Authorization: authorization },
        signal: AbortSignal.timeout(15_000),
      }),
    ]);

    if (!orderResponse.ok || !paymentResponse.ok) {
      return NextResponse.json(
        { error: 'provider_verification_failed', message: 'Could not verify payment with Razorpay' },
        { status: 502 },
      );
    }

    const [order, payment] = await Promise.all([
      orderResponse.json(),
      paymentResponse.json(),
    ]);

    if (
      order?.id !== orderId ||
      payment?.id !== paymentId ||
      payment?.order_id !== orderId ||
      payment?.status !== 'captured' ||
      order?.status !== 'paid' ||
      order?.amount !== payment?.amount ||
      order?.currency !== payment?.currency
    ) {
      return NextResponse.json(
        { error: 'payment_not_captured', message: 'Razorpay has not confirmed a captured payment for this order' },
        { status: 400 },
      );
    }

    if (order?.notes?.user_id !== userId) {
      return NextResponse.json(
        { error: 'payment_owner_mismatch', message: 'This payment order does not belong to the authenticated user' },
        { status: 403 },
      );
    }

    const updatedPayment = await updatePaymentStatus(orderId, 'completed', {
      razorpay_payment_id: paymentId,
      razorpay_signature: signature,
      payment_method: 'razorpay',
      updated_at: new Date().toISOString(),
    });
    if (updatedPayment?.error) {
      throw new Error('Could not persist the verified payment status');
    }

    sendReceiptEmail(userId, {
      amount: order.amount / 100,
      plan_name: 'One-time payment',
      order_id: orderId,
      status: 'completed',
    }).catch((err) => console.warn('[Email] Receipt failed:', err));

    return NextResponse.json({
      success: true,
      verified: true,
      payment_id: paymentId,
      order_id: orderId,
      message: 'Payment verified and recorded successfully',
    });
  } catch (error) {
    console.error('[Razorpay Verify Error]:', error);
    return NextResponse.json(
      { error: 'verification_failed', message: 'Failed to verify payment' },
      { status: 500 },
    );
  }
}

async function sendReceiptEmail(userId: string, receiptData: {
  amount: number;
  plan_name: string;
  order_id: string;
  status: string;
}) {
  try {
    const userDetails = await getUserDetails(userId);
    if (!userDetails?.work_email) return;

    const { sendPaymentReceipt } = await import('@/lib/email-brevo');
    await sendPaymentReceipt({
      to: userDetails.work_email,
      userName: userDetails.full_name,
      amount: receiptData.amount,
      planName: receiptData.plan_name,
      orderId: receiptData.order_id,
      status: receiptData.status as 'completed' | 'processing' | 'failed',
    });
  } catch (emailError) {
    console.error('[Email] Failed to send receipt:', emailError);
  }
}
