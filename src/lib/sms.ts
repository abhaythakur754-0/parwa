/**
 * PARWA SMS Service — Backend Proxy
 *
 * Sends SMS messages by calling the Parwa backend API,
 * which routes through the ProviderRegistry.
 *
 * SECURITY: Never calls Twilio directly from the frontend.
 * All external API calls go through: Frontend → BFF → Backend → ProviderRegistry → External API
 */

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:5100';

export interface SMSSendResult {
  success: boolean;
  sid?: string;
  error?: string;
}

export function isSMSConfigured(): boolean {
  // Always return true — the backend handles provider detection
  // If no SMS provider is configured, the backend will return a clear error
  return true;
}

export function getSMSStatus(): {
  configured: boolean;
  accountSid: string | null;
  phoneNumber: string | null;
  missingVars: string[];
} {
  return {
    configured: true,
    accountSid: null,  // No longer exposed to frontend
    phoneNumber: null, // No longer exposed to frontend
    missingVars: [],   // Backend handles this
  };
}

export async function sendSMS(
  to: string,
  body: string
): Promise<SMSSendResult> {
  try {
    const response = await fetch(`${BACKEND_URL}/api/v1/sms/send`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ to, body }),
    });

    const data = await response.json();

    if (response.ok && data.success) {
      return { success: true, sid: data.sid || data.data?.sid };
    }

    console.error('[SMS] Backend error:', response.status, JSON.stringify(data));
    return { success: false, error: data.error || data.message || `Backend returned ${response.status}` };
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
