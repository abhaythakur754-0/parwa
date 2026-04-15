const BREVO_API_URL = "https://api.brevo.com/v3/smtp/email";
const BREVO_API_KEY = process.env.BREVO_API_KEY;
const FROM_EMAIL = process.env.FROM_EMAIL || "noreply@parwa.io";
const FROM_NAME = "PARWA";

export async function sendEmail(
  to: string,
  subject: string,
  htmlContent: string
): Promise<{ success: boolean; error?: string }> {
  if (!BREVO_API_KEY) {
    console.error("BREVO_API_KEY not set in environment variables");
    return { success: false, error: "Email service is not configured" };
  }

  try {
    const response = await fetch(BREVO_API_URL, {
      method: "POST",
      headers: {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        sender: {
          name: FROM_NAME,
          email: FROM_EMAIL,
        },
        to: [{ email: to }],
        subject,
        htmlContent,
      }),
    });

    if (response.ok) {
      return { success: true };
    }

    const errorData = await response.text();
    console.error("Brevo API error:", response.status, errorData);
    return { success: false, error: `Brevo API error: ${response.status}` };
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : "Unknown error";
    console.error("Email send error:", message);
    return { success: false, error: message };
  }
}
