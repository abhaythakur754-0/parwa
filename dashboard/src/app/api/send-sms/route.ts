import { NextResponse } from 'next/server';
import { sendSMS, isSMSConfigured, getSMSStatus } from '@/lib/sms';

export async function POST(request: Request) {
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

export async function GET() {
  return NextResponse.json(getSMSStatus());
}
