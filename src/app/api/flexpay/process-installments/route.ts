/**
 * FlexPay Process Installments API Endpoint
 * ═══════════════════════════════════════════════════════════════════
 *
 * POST /api/flexpay/process-installments
 *
 * Proxies to the backend FastAPI endpoint which uses the real
 * Razorpay client to charge tokenized cards.
 *
 * The backend has the Razorpay API keys — the frontend does not.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAccessTokenFromCookies } from '@/lib/auth-cookies';
import { getBackendUrl } from '@/lib/backend-url';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const token = getAccessTokenFromCookies(req as unknown as Request);
    const backendUrl = getBackendUrl();

    console.log('[FlexPay/API] Forwarding charge request to backend...');

    const response = await fetch(`${backendUrl}/api/flexpay/process-installments`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        Cookie: req.headers.get('cookie') || '',
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(30000),
    });

    const data = await response.json();

    if (!response.ok) {
      return NextResponse.json(
        {
          success: false,
          error: data.error || data.detail || 'Charge failed',
          errorCode: data.error_code || 'UNKNOWN',
        },
        { status: response.status }
      );
    }

    return NextResponse.json({
      success: true,
      status: data.status || 'success',
      payment_id: data.payment_id || data.id,
      amount: data.amount,
      installment_number: data.installment_number,
      remaining: data.remaining,
      processedAt: new Date().toISOString(),
    });
  } catch (error) {
    console.error('[FlexPay/API] Error processing installments:', error);

    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error ? error.message : 'Failed to process installment',
        errorCode: 'NETWORK_ERROR',
      },
      { status: 500 }
    );
  }
}

// GET endpoint for checking scheduler status
export async function GET() {
  try {
    const backendUrl = getBackendUrl();
    const response = await fetch(`${backendUrl}/api/flexpay/scheduler-status`, {
      headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(10000),
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json({ success: true, ...data });
    }

    return NextResponse.json({
      success: true,
      stats: { totalProcessed: 0, successfulCharges: 0, failedCharges: 0 },
      timestamp: new Date().toISOString(),
      message: 'Scheduler status unavailable (backend not reachable)',
    });
  } catch (error) {
    console.error('[FlexPay/API] Error getting scheduler status:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to get scheduler status' },
      { status: 500 }
    );
  }
}
