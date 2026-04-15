import { NextRequest, NextResponse } from "next/server";
import crypto from "crypto";
import { db } from "@/lib/db";
import { sendEmail } from "@/lib/email";

/**
 * POST /api/forgot-password
 * Sends a 6-digit OTP to the user's email via Brevo API.
 * Checks if user exists in database, generates OTP, and saves it.
 */

function generateOTP(): string {
  // Generate a cryptographically secure 6-digit OTP
  const bytes = crypto.randomBytes(3);
  const num = bytes.readUIntBE(0, 3);
  return (num % 1000000).toString().padStart(6, "0");
}

function getOTPEmailHTML(userName: string, otp: string): string {
  return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PARWA Password Reset OTP</title>
</head>
<body style="margin:0; padding:0; background-color:#1A1A1A; font-family:'Inter','Segoe UI',system-ui,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px; margin:0 auto; padding:40px 20px;">
    <!-- Header -->
    <tr>
      <td style="text-align:center; padding-bottom:32px;">
        <div style="display:inline-flex; align-items:center; gap:10px;">
          <div style="width:40px; height:40px; border-radius:10px; background:linear-gradient(135deg,#E06A00,#FF7F11); display:flex; align-items:center; justify-content:center;">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2.25 2.25 0 002-2V5a2.25 2.25 0 00-2-2H5a2.25 2.25 0 00-2 2v10a2.25 2.25 0 002 2z"/>
            </svg>
          </div>
          <span style="font-size:22px; font-weight:800; color:#ffffff;">PARWA</span>
        </div>
      </td>
    </tr>

    <!-- Main Card -->
    <tr>
      <td style="background:linear-gradient(135deg, rgba(255,255,255,0.08) 0%, rgba(255,255,255,0.03) 100%); border-radius:16px; padding:40px; border:1px solid rgba(255,127,17,0.25); box-shadow:0 4px 24px rgba(0,0,0,0.2);">
        <h1 style="margin:0 0 8px; font-size:24px; font-weight:700; color:#ffffff;">Password Reset</h1>
        <p style="margin:0 0 28px; font-size:15px; color:rgba(255,255,255,0.5); line-height:1.6;">
          Hi ${userName},<br><br>
          We received a request to reset your password. Use the OTP below to verify your identity:
        </p>

        <!-- OTP Display -->
        <div style="text-align:center; padding:28px 0; background:rgba(255,127,17,0.1); border-radius:12px; border:1px solid rgba(255,127,17,0.2); margin-bottom:24px;">
          <p style="margin:0 0 8px; font-size:13px; color:rgba(255,255,255,0.4); text-transform:uppercase; letter-spacing:2px; font-weight:600;">Your OTP Code</p>
          <p style="margin:0; font-size:36px; font-weight:800; color:#FF7F11; letter-spacing:12px; font-family:'Courier New',monospace;">
            ${otp}
          </p>
        </div>

        <p style="margin:20px 0 0; font-size:13px; color:rgba(255,255,255,0.35); line-height:1.5;">
          This OTP expires in <strong style="color:rgba(255,255,255,0.5);">10 minutes</strong>.
        </p>
        <p style="margin:16px 0 0; font-size:13px; color:rgba(255,255,255,0.35); line-height:1.5;">
          If you did not request this, you can safely ignore this email. Your password will not change.
        </p>
      </td>
    </tr>

    <!-- Footer -->
    <tr>
      <td style="text-align:center; padding-top:24px;">
        <p style="margin:0; font-size:12px; color:rgba(255,255,255,0.25);">
          &copy; ${new Date().getFullYear()} PARWA AI Workforce. All rights reserved.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>`;
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email } = body;

    if (!email || typeof email !== "string" || !email.includes("@")) {
      return NextResponse.json(
        { status: "error", message: "Please provide a valid email address." },
        { status: 400 }
      );
    }

    const normalizedEmail = email.trim().toLowerCase();

    // Check if user exists
    const user = await db.user.findUnique({
      where: { email: normalizedEmail },
    });

    // FIX A6: Use ambiguous response to prevent email enumeration.
    // Do NOT reveal whether an account with this email exists.
    if (!user) {
      return NextResponse.json(
        {
          status: "success",
          message: "If an account with this email exists, an OTP has been sent.",
        },
        { status: 200 }
      );
    }

    // Generate 6-digit OTP
    const otp = generateOTP();
    const otpExpires = new Date(Date.now() + 10 * 60 * 1000); // 10 minutes

    // Save OTP to database
    await db.user.update({
      where: { id: user.id },
      data: {
        otp_code: otp,
        otp_expires: otpExpires,
        reset_token: null,
        reset_token_expires: null,
      },
    });

    // Send OTP email
    const htmlContent = getOTPEmailHTML(user.full_name || "User", otp);
    const emailResult = await sendEmail(
      normalizedEmail,
      "PARWA Password Reset - Your OTP Code",
      htmlContent
    );

    if (!emailResult.success) {
      console.error("Failed to send OTP email:", emailResult.error);
      return NextResponse.json(
        { status: "error", message: "Failed to send OTP email. Please try again." },
        { status: 500 }
      );
    }

    return NextResponse.json({
      status: "success",
      message: "OTP has been sent to your email.",
    });
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Forgot password error:", message);
    return NextResponse.json(
      { status: "error", message: "An unexpected error occurred. Please try again." },
      { status: 500 }
    );
  }
}
