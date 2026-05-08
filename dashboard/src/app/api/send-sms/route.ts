import { NextRequest, NextResponse } from 'next/server';
import { sendSMS, isSMSConfigured, getSMSStatus } from '@/lib/sms';

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

export async function POST(request: NextRequest) {
  if (!requireAuth(request)) {
    return NextResponse.json(
      { success: false, error: 'Authentication required' },
      { status: 401 }
    );
  }
  try {
    const body = await request.json();
    const { to, body: message } = body;

    if (!to || !message) {
      return NextResponse.json(
        { success: false, error: 'to and body are required' },
        { status: 400 }
      );
    }

    if (!isSMSConfigured()) {
      return NextResponse.json(
        { success: false, error: 'SMS service not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER in .env' },
        { status: 503 }
      );
    }

    const result = await sendSMS(to, message);
    return NextResponse.json(result);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json(
      { success: false, error: message },
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest) {
  if (!requireAuth(request)) {
    return NextResponse.json(
      { success: false, error: 'Authentication required' },
      { status: 401 }
    );
  }
  return NextResponse.json(getSMSStatus());
}
