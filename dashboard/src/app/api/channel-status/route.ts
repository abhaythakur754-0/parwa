import { NextResponse } from 'next/server';

export async function GET() {
  const BREVO_API_KEY = process.env.BREVO_API_KEY;
  const FROM_EMAIL = process.env.FROM_EMAIL;
  const TWILIO_ACCOUNT_SID = process.env.TWILIO_ACCOUNT_SID;
  const TWILIO_PHONE_NUMBER = process.env.TWILIO_PHONE_NUMBER;

  return NextResponse.json({
    email: {
      configured: !!BREVO_API_KEY,
      provider: BREVO_API_KEY ? 'Brevo' : null,
      fromEmail: FROM_EMAIL || null,
      apiKeyPreview: BREVO_API_KEY ? `${BREVO_API_KEY.slice(0, 8)}...` : null,
    },
    sms: {
      configured: !!(TWILIO_ACCOUNT_SID && process.env.TWILIO_AUTH_TOKEN && TWILIO_PHONE_NUMBER),
      provider: TWILIO_ACCOUNT_SID ? 'Twilio' : null,
      phoneNumber: TWILIO_PHONE_NUMBER || null,
      accountSidPreview: TWILIO_ACCOUNT_SID ? `${TWILIO_ACCOUNT_SID.slice(0, 6)}...` : null,
    },
  });
}
