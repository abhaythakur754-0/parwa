/**
 * PARWA Notification Service
 *
 * Sends real email/SMS notifications when tickets are created,
 * AI responds, or tickets are resolved/escalated.
 *
 * Channel routing:
 *   - Email channel tickets → email notification
 *   - SMS channel tickets → SMS notification
 *   - Voice channel tickets → email notification (transcript)
 *   - Chat channel tickets → in-app only (no external notification)
 */

import { sendEmail } from './email';
import { sendSMS, buildTicketSMS } from './sms';

export interface NotificationPayload {
  ticketNumber: string;
  customerName: string;
  customerEmail: string;
  customerPhone?: string;
  channel: 'email' | 'sms' | 'voice' | 'chat';
  subject: string;
  status: 'created' | 'in_progress' | 'resolved' | 'escalated';
  aiResponse?: string;
  resolution?: string;
}

export interface NotificationResult {
  emailSent: boolean;
  smsSent: boolean;
  emailError?: string;
  smsError?: string;
}

export async function sendTicketNotification(payload: NotificationPayload): Promise<NotificationResult> {
  const result: NotificationResult = { emailSent: false, smsSent: false };

  // Send email notification
  if (payload.channel === 'email' || payload.channel === 'voice' || payload.channel === 'chat') {
    const emailResult = await sendTicketEmail(payload);
    result.emailSent = emailResult.success;
    result.emailError = emailResult.error;
  }

  // Send SMS notification
  if (payload.channel === 'sms') {
    const smsResult = await sendTicketSMS(payload);
    result.smsSent = smsResult.success;
    result.smsError = smsResult.error;
  }

  console.log(`[Notification] ${payload.ticketNumber} ${payload.status}: email=${result.emailSent}, sms=${result.smsSent}`);

  return result;
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

async function sendTicketEmail(payload: NotificationPayload): Promise<{ success: boolean; error?: string }> {
  const { ticketNumber, customerName, customerEmail, subject, status, aiResponse, resolution } = payload;

  // H-16 FIX: Sanitize user-controlled fields to prevent HTML injection in email templates
  const safeName = escapeHtml(customerName);
  const safeAiResponse = aiResponse ? escapeHtml(aiResponse) : undefined;
  const safeResolution = resolution ? escapeHtml(resolution) : undefined;
  const safeSubject = escapeHtml(subject);

  let emailSubject: string;
  let htmlBody: string;

  switch (status) {
    case 'created':
      emailSubject = `[PARWA] ${ticketNumber} - Ticket Created: ${subject}`;
      htmlBody = buildCreatedEmail(safeName, ticketNumber, safeSubject);
      break;
    case 'in_progress':
      emailSubject = `[PARWA] ${ticketNumber} - We're working on your request`;
      htmlBody = buildInProgressEmail(safeName, ticketNumber, safeAiResponse);
      break;
    case 'resolved':
      emailSubject = `[PARWA] ${ticketNumber} - Your ticket has been resolved`;
      htmlBody = buildResolvedEmail(safeName, ticketNumber, safeResolution);
      break;
    case 'escalated':
      emailSubject = `[PARWA] ${ticketNumber} - Escalated to specialist`;
      htmlBody = buildEscalatedEmail(safeName, ticketNumber);
      break;
    default:
      emailSubject = `[PARWA] ${ticketNumber} - Update`;
      htmlBody = buildCreatedEmail(safeName, ticketNumber, safeSubject);
  }

  return sendEmail(customerEmail, emailSubject, htmlBody);
}

async function sendTicketSMS(payload: NotificationPayload): Promise<{ success: boolean; error?: string }> {
  const { ticketNumber, customerName, customerPhone, status } = payload;
  const body = buildTicketSMS(ticketNumber, status, customerName);
  // M-37: Use customer phone from payload instead of hardcoded number
  const recipientPhone = customerPhone || '';
  if (!recipientPhone) {
    console.warn(`[Notification] ${ticketNumber}: No customer phone provided for SMS`);
    return { success: false, error: 'No customer phone number provided' };
  }
  return sendSMS(recipientPhone, body);
}

// ── Email Templates ──

function buildCreatedEmail(name: string, ticketNumber: string, subject: string): string {
  return `<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f8f9fa;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fa;padding:40px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
        <tr><td style="background:linear-gradient(135deg,#f97316,#ea580c);padding:30px 40px;">
          <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;">PARWA</h1>
          <p style="margin:8px 0 0;color:rgba(255,255,255,0.85);font-size:14px;">AI-Powered Support</p>
        </td></tr>
        <tr><td style="padding:30px 40px;">
          <p style="margin:0 0 16px;color:#374151;font-size:16px;">Hi ${name},</p>
          <p style="margin:0 0 16px;color:#4b5563;font-size:14px;line-height:1.6;">We've received your support request and created ticket <strong style="color:#f97316;">${ticketNumber}</strong>.</p>
          <table width="100%" cellpadding="12" cellspacing="0" style="background:#f3f4f6;border-radius:8px;margin:16px 0;">
            <tr><td>
              <p style="margin:0;color:#6b7280;font-size:12px;">SUBJECT</p>
              <p style="margin:4px 0 0;color:#111827;font-size:14px;font-weight:600;">${subject}</p>
            </td></tr>
          </table>
          <p style="margin:0 0 16px;color:#4b5563;font-size:14px;line-height:1.6;">Our AI support team is reviewing your request and will respond shortly. You can track your ticket status in your dashboard.</p>
        </td></tr>
        <tr><td style="padding:20px 40px;border-top:1px solid #f3f4f6;">
          <p style="margin:0;color:#9ca3af;font-size:12px;">This is an automated message from PARWA AI Workforce Platform.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>`;
}

function buildInProgressEmail(name: string, ticketNumber: string, aiResponse?: string): string {
  const responseBlock = aiResponse
    ? `<table width="100%" cellpadding="16" cellspacing="0" style="background:#fff7ed;border-left:4px solid #f97316;border-radius:8px;margin:16px 0;">
        <tr><td>
          <p style="margin:0 0 8px;color:#9a3412;font-size:11px;font-weight:600;">AI RESPONSE</p>
          <p style="margin:0;color:#1c1917;font-size:14px;line-height:1.6;">${aiResponse}</p>
        </td></tr>
      </table>`
    : '';

  return `<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f8f9fa;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fa;padding:40px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
        <tr><td style="background:linear-gradient(135deg,#f97316,#ea580c);padding:30px 40px;">
          <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;">PARWA</h1>
          <p style="margin:8px 0 0;color:rgba(255,255,255,0.85);font-size:14px;">AI-Powered Support</p>
        </td></tr>
        <tr><td style="padding:30px 40px;">
          <p style="margin:0 0 16px;color:#374151;font-size:16px;">Hi ${name},</p>
          <p style="margin:0 0 8px;color:#4b5563;font-size:14px;line-height:1.6;">Your ticket <strong style="color:#f97316;">${ticketNumber}</strong> is being handled by our AI support agent.</p>
          ${responseBlock}
        </td></tr>
        <tr><td style="padding:20px 40px;border-top:1px solid #f3f4f6;">
          <p style="margin:0;color:#9ca3af;font-size:12px;">This is an automated message from PARWA AI Workforce Platform.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>`;
}

function buildResolvedEmail(name: string, ticketNumber: string, resolution?: string): string {
  const resolutionBlock = resolution
    ? `<table width="100%" cellpadding="16" cellspacing="0" style="background:#f0fdf4;border-left:4px solid #22c55e;border-radius:8px;margin:16px 0;">
        <tr><td>
          <p style="margin:0 0 8px;color:#166534;font-size:11px;font-weight:600;">RESOLUTION</p>
          <p style="margin:0;color:#1c1917;font-size:14px;line-height:1.6;">${resolution}</p>
        </td></tr>
      </table>`
    : '';

  return `<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f8f9fa;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fa;padding:40px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
        <tr><td style="background:linear-gradient(135deg,#22c55e,#16a34a);padding:30px 40px;">
          <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;">PARWA</h1>
          <p style="margin:8px 0 0;color:rgba(255,255,255,0.85);font-size:14px;">Ticket Resolved</p>
        </td></tr>
        <tr><td style="padding:30px 40px;">
          <p style="margin:0 0 16px;color:#374151;font-size:16px;">Hi ${name},</p>
          <p style="margin:0 0 8px;color:#4b5563;font-size:14px;line-height:1.6;">Great news! Your ticket <strong style="color:#22c55e;">${ticketNumber}</strong> has been resolved successfully.</p>
          ${resolutionBlock}
          <p style="margin:16px 0 0;color:#4b5563;font-size:14px;">If you need further assistance, please reply to this email or open a new ticket.</p>
        </td></tr>
        <tr><td style="padding:20px 40px;border-top:1px solid #f3f4f6;">
          <p style="margin:0;color:#9ca3af;font-size:12px;">This is an automated message from PARWA AI Workforce Platform.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>`;
}

function buildEscalatedEmail(name: string, ticketNumber: string): string {
  return `<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f8f9fa;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f8f9fa;padding:40px 20px;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
        <tr><td style="background:linear-gradient(135deg,#f97316,#ea580c);padding:30px 40px;">
          <h1 style="margin:0;color:#ffffff;font-size:24px;font-weight:700;">PARWA</h1>
          <p style="margin:8px 0 0;color:rgba(255,255,255,0.85);font-size:14px;">Ticket Escalated</p>
        </td></tr>
        <tr><td style="padding:30px 40px;">
          <p style="margin:0 0 16px;color:#374151;font-size:16px;">Hi ${name},</p>
          <p style="margin:0 0 8px;color:#4b5563;font-size:14px;line-height:1.6;">Your ticket <strong style="color:#f97316;">${ticketNumber}</strong> requires specialized attention and has been escalated to our expert support team.</p>
          <p style="margin:0;color:#4b5563;font-size:14px;line-height:1.6;">A human specialist will review your case and contact you within the next few hours. We appreciate your patience.</p>
        </td></tr>
        <tr><td style="padding:20px 40px;border-top:1px solid #f3f4f6;">
          <p style="margin:0;color:#9ca3af;font-size:12px;">This is an automated message from PARWA AI Workforce Platform.</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>`;
}
