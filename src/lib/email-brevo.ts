/**
 * PARWA Email Service - Brevo (SendinBlue) Integration
 * 
 * Sends transactional emails via Brevo REST API
 * Used for:
 * - OTP verification during onboarding
 * - Welcome emails after FirstVictory
 * - Payment receipts
 * - KB processing notifications
 * 
 * SECURITY: API key is server-side only, never exposed to client
 */

const BREVO_API_KEY = process.env.BREVO_API_KEY;
const BREVO_API_URL = 'https://api.brevo.com/v3';
const FROM_EMAIL = process.env.EMAIL_FROM_EMAIL || 'noreply@flexpay.com';
const FROM_NAME = process.env.EMAIL_FROM_NAME || 'FlexPay';

interface EmailPayload {
  to: string | string[];
  subject: string;
  htmlContent: string;
 textContent?: string;
  replyTo?: string;
  headers?: Record<string, string>;
  tags?: string[];
}

interface SendResult {
  success: boolean;
  messageId?: string;
  error?: string;
}

/**
 * Send email via Brevo API
 */
export async function sendEmail(payload: EmailPayload): Promise<SendResult> {
  if (!BREVO_API_KEY) {
    console.error('[Email] ❌ BREVO_API_KEY not configured');
    return { success: false, error: 'Email service not configured' };
  }

  try {
    const recipients = Array.isArray(payload.to) ? payload.to : [payload.to];
    
    const body = {
      sender: { name: FROM_NAME, email: FROM_EMAIL },
      to: recipients.map(email => ({ email })),
      subject: payload.subject,
      htmlContent: payload.htmlContent,
      textContent: payload.textContent || stripHtml(payload.htmlContent),
      replyTo: payload.replyTo ? { email: payload.replyTo } : undefined,
      headers: payload.headers,
      tags: ['flexpay', ...(payload.tags || [])],
    };

    console.log(`[Email] 📧 Sending to ${recipients.join(', ')}: ${payload.subject}`);

    const response = await fetch(`${BREVO_API_URL}/smtp/email`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'api-key': BREVO_API_KEY,
      },
      body: JSON.stringify(body),
    });

    const data = await response.json();

    if (!response.ok) {
      console.error('[Email] ❌ Brevo API error:', data);
      return { 
        success: false, 
        error: data.message || `API Error: ${response.status}` 
      };
    }

    console.log(`[Email] ✅ Sent successfully! Message ID: ${data.messageId}`);
    
    return {
      success: true,
      messageId: data.messageId,
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    console.error('[Email] ❌ Send error:', message);
    return { success: false, error: message };
  }
}

// ── OTP Email ──────────────────────────────────────────────────────

interface OtpEmailOptions {
  to: string;
  otpCode: string;
  userName?: string;
  expiryMinutes?: number;
}

export async function sendOtpEmail(options: OtpEmailOptions): Promise<SendResult> {
  const { to, otpCode, userName, expiryMinutes = 10 } = options;

  const subject = `Your FlexPay Verification Code: ${otpCode}`;
  
  const htmlContent = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#f4f4f5; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px; margin:0 auto; padding:20px;">
    
    <!-- Header -->
    <tr>
      <td style="background:linear-gradient(135deg,#f97316,#f59e0b); padding:30px; border-radius:16px 16px 0 0; text-align:center;">
        <h1 style="margin:0; color:white; font-size:28px;">🚀 FlexPay</h1>
        <p style="margin:8px 0 0; color:rgba(255,255,255,0.9);">Verify your email address</p>
      </td>
    </tr>
    
    <!-- Content -->
    <tr>
      <td style="background:white; padding:40px 30px; border:1px solid #e4e4e7;">
        
        <p style="margin:0 0 16px; color:#3f3f46; font-size:16px;">
          Hi ${userName || 'there'}, 👋
        </p>
        
        <p style="margin:0 0 24px; color:#52525b; font-size:15px; line-height:1.6;">
          Use the verification code below to complete your setup. This code will expire in <strong>${expiryMinutes} minutes</strong>.
        </p>
        
        <!-- OTP Code -->
        <div style="background:#fafafa; border:2px dashed #f97316; border-radius:12px; padding:24px; margin:24px 0; text-align:center;">
          <p style="margin:0 0 8px; color:#71717a; font-size:13px; text-transform:uppercase; letter-spacing:1px;">Your Verification Code</p>
          <p style="margin:0; font-size:36px; font-weight:700; letter-spacing:8px; color:#f97316; font-family:'Courier New',monospace;">
            ${otpCode}
          </p>
        </div>
        
        <p style="margin:24px 0 0; color:#a1a1aa; font-size:13px; text-align:center;">
          ⏰ This code expires in ${expiryMinutes} minutes<br>
          🔒 Never share this code with anyone
        </p>
        
      </td>
    </tr>
    
    <!-- Footer -->
    <tr>
      <td style="background:#18181b; padding:24px; border-radius:0 0 16px 16px; text-align:center;">
        <p style="margin:0 0 8px; color:#a1a1aa; font-size:13px;">
          Need help? <a href="mailto:support@flexpay.com" style="color:#f97316;text-decoration:none;">Contact Support</a>
        </p>
        <p style="margin:0; color:#71717a; font-size:12px;">
          © 2026 FlexPay. All rights reserved.
        </p>
      </td>
    </tr>
    
  </table>
  
</body>
</html>`;

  return sendEmail({
    to,
    subject,
    htmlContent,
    tags: ['otp-verification'],
  });
}

// ── Welcome Email ──────────────────────────────────────────────────

interface WelcomeEmailOptions {
  to: string;
  userName?: string;
  companyName?: string;
}

export async function sendWelcomeEmail(options: WelcomeEmailOptions): Promise<SendResult> {
  const { to, userName, companyName } = options;

  const subject = `Welcome to FlexPay! 🎉 Your AI Assistant is Ready`;

  const htmlContent = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
</head>
<body style="margin:0; padding:0; background:#f4f4f5; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px; margin:0 auto; padding:20px;">
    
    <!-- Celebration Header -->
    <tr>
      <td style="background:linear-gradient(135deg,#f97316,#eab308); padding:40px 30px; border-radius:16px 16px 0 0; text-align:center;">
        <h1 style="margin:0; color:white; font-size:32px;">🎉 You're In!</h1>
        <p style="margin:12px 0 0; color:rgba(255,255,255,0.95); font-size:18px;">
          Welcome${userName ? `, ${userName}` : ''} to FlexPay!
        </p>
      </td>
    </tr>
    
    <!-- Success Message -->
    <tr>
      <td style="background:white; padding:40px 30px; border:1px solid #e4e4e7;">
        
        <p style="margin:0 0 20px; color:#3f3f46; font-size:16px; line-height:1.6;">
          Congratulations! Your account is now active and ready to go.
        </p>
        
        ${companyName ? `
        <div style="background:#fef3c7; border-left:4px solid #f59e0b; padding:16px; margin:20px 0; border-radius:0 8px 8px 0;">
          <p style="margin:0; color:#92400e; font-size:14px;">
            🏢 <strong>${companyName}</strong> is now connected to FlexPay
          </p>
        </div>
        ` : ''}
        
        <h3 style="margin:28px 0 12px; color:#18181b; font-size:17px;">What's Next?</h3>
        
        <ul style="margin:0; padding-left:20px; color:#52525b; line-height:2;">
          <li><strong>Explore Dashboard</strong> — Check your analytics & settings</li>
          <li><strong>Configure Integrations</strong> — Connect more channels</li>
          <li><strong>Train Your AI</strong> — Upload more docs to knowledge base</li>
        </ul>
        
        <div style="text-align:center; margin:32px 0 0;">
          <a href="${process.env.NEXT_PUBLIC_APP_URL || 'https://app.flexpay.com'}/dashboard" 
             style="display:inline-block; background:linear-gradient(135deg,#f97316,#f59e0b); color:white; padding:14px 32px; border-radius:8px; text-decoration:none; font-weight:600; font-size:15px;">
            Go to Dashboard →
          </a>
        </div>
        
      </td>
    </tr>
    
    <!-- Footer -->
    <tr>
      <td style="background:#18181b; padding:24px; border-radius:0 0 16px 16px; text-align:center;">
        <p style="margin:0; color:#71717a; font-size:12px;">
          © 2026 FlexPay • Built with ❤️ for amazing customer support
        </p>
      </td>
    </tr>
    
  </table>
</body>
</html>`;

  return sendEmail({
    to,
    subject,
    htmlContent,
    tags: ['welcome', 'onboarding-complete'],
  });
}

// ── Payment Receipt ────────────────────────────────────────────────

interface PaymentReceiptOptions {
  to: string;
  userName?: string;
  amount: number;
  currency?: string;
  planName: string;
  orderId: string;
  status: 'completed' | 'processing' | 'failed';
}

export async function sendPaymentReceipt(options: PaymentReceiptOptions): Promise<SendResult> {
  const { to, userName, amount, currency = 'INR', planName, orderId, status } = options;

  const isSuccess = status === 'completed';
  const subject = isSuccess 
    ? `Payment Confirmed ✅ ₹${amount} for ${planName}`
    : `Payment Update: ${planName}`;

  const statusColor = isSuccess ? '#10b981' : '#f59e0b';
  const statusIcon = isSuccess ? '✅' : '⏳';

  const htmlContent = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
</head>
<body style="margin:0; padding:0; background:#f4f4f5; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px; margin:0 auto; padding:20px;">
    
    <tr>
      <td style="background:${statusColor}; padding:30px; border-radius:16px 16px 0 0; text-align:center;">
        <h1 style="margin:0; color:white; font-size:28px;">${statusIcon} Payment ${isSuccess ? 'Confirmed' : 'Update'}</h1>
        <p style="margin:8px 0 0; color:rgba(255,255,255,0.9);">
          ${isSuccess ? 'Thank you for your payment!' : 'Your payment is being processed'}
        </p>
      </td>
    </tr>
    
    <tr>
      <td style="background:white; padding:40px 30px; border:1px solid #e4e4e7;">
        
        <p style="margin:0 0 24px; color:#52525b;">
          Hi${userName ? `, ${userName}` : ''},
        </p>
        
        <!-- Payment Details -->
        <div style="background:#fafafa; border-radius:12px; padding:24px; margin:20px 0;">
          
          <table style="width:100%; border-collapse:collapse;">
            <tr>
              <td style="padding:12px 0; color:#71717a; font-size:14px;">Plan</td>
              <td style="padding:12px 0; text-align:right; color:#18181b; font-weight:600;">${planName}</td>
            </tr>
            <tr>
              <td style="padding:12px 0; border-top:1px solid #e4e4e7; color:#71717a; font-size:14px;">Amount</td>
              <td style="padding:12px 0; border-top:1px solid #e4e4e7; text-align:right; color:#18181b; font-weight:700; font-size:18px;">₹${amount.toLocaleString()}</td>
            </tr>
            <tr>
              <td style="padding:12px 0; border-top:1px solid #e4e4e7; color:#71717a; font-size:14px;">Order ID</td>
              <td style="padding:12px 0; border-top:1px solid #e4e4e7; text-align:right; color:#18181b; font-family:monospace; font-size:13px;">${orderId}</td>
            </tr>
            <tr>
              <td style="padding:12px 0; border-top:1px solid #e4e4e7; color:#71717a; font-size:14px;">Status</td>
              <td style="padding:12px 0; border-top:1px solid #e4e4e7; text-align:right;">
                <span style="display:inline-block; background:${statusColor}20; color:${statusColor}; padding:4px 12px; border-radius:20px; font-size:13px; font-weight:600;">
                  ${status.charAt(0).toUpperCase() + status.slice(1)}
                </span>
              </td>
            </tr>
          </table>
          
        </div>
        
        ${isSuccess ? `
        <p style="margin:24px 0 0; color:#52525b; font-size:14px; text-align:center;">
          A detailed receipt will be available in your dashboard.
        </p>
        ` : ''}
        
      </td>
    </tr>
    
    <tr>
      <td style="background:#18181b; padding:24px; border-radius:0 0 16px 16px; text-align:center;">
        <p style="margin:0; color:#71717a; font-size:12px;">
          Questions? <a href="mailto:billing@flexpay.com" style="color:#f97316;text-decoration:none;">Contact Billing</a>
        </p>
      </td>
    </tr>
    
  </table>
</body>
</html>`;

  return sendEmail({
    to,
    subject,
    htmlContent,
    tags: ['payment', `payment-${status}`, planName.toLowerCase()],
  });
}

// ── Utility Functions ───────────────────────────────────────────────

function stripHtml(html: string): string {
  return html.replace(/<[^>]*>/g, '').replace(/\s+/g, ' ').trim();
}

// Legacy compatibility - export as default too
export default { sendEmail, sendOtpEmail, sendWelcomeEmail, sendPaymentReceipt };
