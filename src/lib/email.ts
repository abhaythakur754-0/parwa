/**
 * PARWA Email Service — Backend Proxy
 *
 * Sends emails by calling the Parwa backend API,
 * which routes through the ProviderRegistry.
 *
 * SECURITY: Never calls Brevo/SendGrid directly from the frontend.
 * All external API calls go through: Frontend → BFF → Backend → ProviderRegistry → External API
 */

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:5100';

export async function sendEmail(
  to: string,
  subject: string,
  htmlContent: string
): Promise<{ success: boolean; error?: string }> {
  try {
    const response = await fetch(`${BACKEND_URL}/api/v1/email/send`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        to: [to],
        subject,
        body: htmlContent,
        html_body: htmlContent,
      }),
    });

    const data = await response.json();

    if (response.ok && data.success) {
      return { success: true };
    }

    console.error('[Email] Backend error:', response.status, JSON.stringify(data));
    return { success: false, error: data.error || data.message || `Backend returned ${response.status}` };
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    console.error('[Email] Send error:', message);
    return { success: false, error: message };
  }
}
