/**
 * PARWA SMS Service — Twilio API Integration
 *
 * Sends SMS messages via the Twilio REST API.
 * Used for:
 *   - Ticket status updates (created, resolved, escalated)
 *   - Customer notifications
 *   - OTP verification
 */

const TWILIO_ACCOUNT_SID = process.env.TWILIO_ACCOUNT_SID;
const TWILIO_AUTH_TOKEN = process.env.TWILIO_AUTH_TOKEN;
const TWILIO_PHONE_NUMBER = process.env.TWILIO_PHONE_NUMBER;

export interface SMSSendResult {
  success: boolean;
  sid?: string;
  error?: string;
}

export function isSMSConfigured(): boolean {
  return !!(TWILIO_ACCOUNT_SID && TWILIO_AUTH_TOKEN && TWILIO_PHONE_NUMBER);
}

export function getSMSStatus(): {
  configured: boolean;
  accountSid: string | null;
  phoneNumber: string | null;
  missingVars: string[];
} {
  const missing: string[] = [];
  if (!TWILIO_ACCOUNT_SID) missing.push('TWILIO_ACCOUNT_SID');
  if (!TWILIO_AUTH_TOKEN) missing.push('TWILIO_AUTH_TOKEN');
  if (!TWILIO_PHONE_NUMBER) missing.push('TWILIO_PHONE_NUMBER');

  return {
    configured: missing.length === 0,
    accountSid: TWILIO_ACCOUNT_SID ? `${TWILIO_ACCOUNT_SID.slice(0, 6)}...` : null,
    phoneNumber: TWILIO_PHONE_NUMBER || null,
    missingVars: missing,
  };
}

export async function sendSMS(
  to: string,
  body: string
): Promise<SMSSendResult> {
  if (!TWILIO_ACCOUNT_SID || !TWILIO_AUTH_TOKEN || !TWILIO_PHONE_NUMBER) {
    const missing: string[] = [];
    if (!TWILIO_ACCOUNT_SID) missing.push('TWILIO_ACCOUNT_SID');
    if (!TWILIO_AUTH_TOKEN) missing.push('TWILIO_AUTH_TOKEN');
    if (!TWILIO_PHONE_NUMBER) missing.push('TWILIO_PHONE_NUMBER');
    console.error('[SMS] Missing env vars:', missing.join(', '));
    return { success: false, error: `SMS not configured. Missing: ${missing.join(', ')}` };
  }

  try {
    // Format phone number (ensure E.164 format)
    let formattedTo = to.trim();
    if (!formattedTo.startsWith('+')) {
      formattedTo = '+' + formattedTo.replace(/[^0-9]/g, '');
    }

    const TWILIO_API_URL = `https://api.twilio.com/2010-04-01/Accounts/${TWILIO_ACCOUNT_SID}/Messages.json`;

    const auth = Buffer.from(`${TWILIO_ACCOUNT_SID}:${TWILIO_AUTH_TOKEN}`).toString('base64');

    const response = await fetch(TWILIO_API_URL, {
      method: 'POST',
      headers: {
        'Authorization': `Basic ${auth}`,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        From: TWILIO_PHONE_NUMBER,
        To: formattedTo,
        Body: body,
      }).toString(),
    });

    const data = await response.json();

    if (response.ok) {
      return { success: true, sid: data.sid };
    }

    console.error('[SMS] Twilio API error:', response.status, JSON.stringify(data));
    return { success: false, error: `Twilio error ${data.code || response.status}: ${data.message || 'Unknown error'}` };
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    console.error('[SMS] Send error:', message);
    return { success: false, error: message };
  }
}

export function buildTicketSMS(ticketNumber: string, status: string, customerName: string, message?: string): string {
  const prefix = `[PARWA] ${ticketNumber}`;
  const maxLength = 160;

  let body: string;
  switch (status) {
    case 'created':
      body = `${prefix}: Hi ${customerName}, your ticket has been created. We'll respond shortly.`;
      break;
    case 'in_progress':
      body = `${prefix}: Hi ${customerName}, we're working on your ticket now.`;
      break;
    case 'resolved':
      body = `${prefix}: Hi ${customerName}, your ticket has been resolved. Thank you for contacting us!`;
      break;
    case 'escalated':
      body = `${prefix}: Hi ${customerName}, your ticket has been escalated to a specialist. We'll update you soon.`;
      break;
    default:
      body = `${prefix}: Update on your ticket — status changed to ${status}.`;
  }

  if (message && body.length + message.length + 10 < maxLength) {
    body += ` ${message}`;
  }

  return body;
}
