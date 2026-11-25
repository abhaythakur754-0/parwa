import { NextRequest, NextResponse } from 'next/server';

/**
 * Legacy frontend FlexPay tokenization was a simulation: it fabricated
 * customer IDs and card tokens instead of confirming tokenization with
 * Razorpay. Do not accept payment identifiers or report a saved card here.
 * Use the authenticated backend FlexPay/payment-method integration instead.
 */
export async function POST(_request: NextRequest) {
  return NextResponse.json(
    {
      success: false,
      error: 'legacy_tokenization_disabled',
      message: 'This legacy tokenization endpoint is disabled because it did not persist or verify real Razorpay card tokens.',
    },
    { status: 410, headers: { 'Cache-Control': 'no-store' } }
  );
}
