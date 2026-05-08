import { NextRequest, NextResponse } from 'next/server';

// Auth check helper
function requireAuth(request: NextRequest): boolean {
  const authHeader = request.headers.get('authorization');
  const sessionCookie = request.cookies.get('parwa_session');
  if (!authHeader && !sessionCookie) {
    return false;
  }
  if (authHeader && !authHeader.startsWith('Bearer ')) {
    return false;
  }
  return true;
}

/**
 * GET /api/channel-status
 * Returns channel configuration status for the dashboard.
 *
 * ── H-17 FIX: Removed API key prefix leaks ──
 * Previously exposed first 8 chars of Brevo key and first 6 of Twilio SID.
 * Now only returns boolean configured status and provider name.
 */
export async function GET(request: NextRequest) {
  if (!requireAuth(request)) {
    return NextResponse.json(
      { success: false, error: 'Authentication required' },
      { status: 401 }
    );
  }
  const BREVO_API_KEY = process.env.BREVO_API_KEY;
  const FROM_EMAIL = process.env.FROM_EMAIL;
  const TWILIO_ACCOUNT_SID = process.env.TWILIO_ACCOUNT_SID;
  const TWILIO_PHONE_NUMBER = process.env.TWILIO_PHONE_NUMBER;
  const TWILIO_AUTH_TOKEN = process.env.TWILIO_AUTH_TOKEN;

  return NextResponse.json({
    email: {
      configured: !!BREVO_API_KEY,
      provider: BREVO_API_KEY ? 'Brevo' : null,
      fromEmail: FROM_EMAIL || null,
    },
    sms: {
      configured: !!(TWILIO_ACCOUNT_SID && TWILIO_AUTH_TOKEN && TWILIO_PHONE_NUMBER),
      provider: TWILIO_ACCOUNT_SID ? 'Twilio' : null,
      phoneNumber: TWILIO_PHONE_NUMBER || null,
    },
  });
}
