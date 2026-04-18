import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import crypto from "crypto";

// In-memory rate limiter for OTP verification: 5 attempts per 15 min per email/IP
const otpAttempts = new Map<string, number[]>();
const OTP_MAX_ATTEMPTS = 5;
const OTP_WINDOW_MS = 15 * 60 * 1000; // 15 minutes

function getOtpRateLimitKey(email: string, ip: string): string {
  return `${email}:${ip}`;
}

function getClientIP(request: NextRequest): string {
  return (
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    request.headers.get("x-real-ip") ||
    "unknown"
  );
}

function isOtpRateLimited(key: string): boolean {
  const now = Date.now();
  const attempts = otpAttempts.get(key) || [];
  const recent = attempts.filter((t) => now - t < OTP_WINDOW_MS);
  otpAttempts.set(key, recent);
  return recent.length >= OTP_MAX_ATTEMPTS;
}

function recordOtpAttempt(key: string): void {
  const now = Date.now();
  const attempts = otpAttempts.get(key) || [];
  attempts.push(now);
  otpAttempts.set(
    key,
    attempts.filter((t) => now - t < OTP_WINDOW_MS),
  );
}

/**
 * POST /api/auth/verify-otp
 * Verifies the 6-digit OTP sent to the user's email.
 * On success, returns a verified flag so the frontend can proceed to reset password.
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email, otp } = body;

    // Rate limit check
    const clientIP = getClientIP(request);
    if (email) {
      const normalizedEmail = (email || "").trim().toLowerCase();
      const rateLimitKey = getOtpRateLimitKey(normalizedEmail, clientIP);
      if (isOtpRateLimited(rateLimitKey)) {
        return NextResponse.json(
          { status: "error", message: "Too many OTP verification attempts. Please try again later." },
          { status: 429 }
        );
      }
      recordOtpAttempt(rateLimitKey);
    }

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email || typeof email !== "string" || !emailRegex.test(email.trim())) {
      return NextResponse.json(
        { status: "error", message: "A valid email address is required." },
        { status: 400 }
      );
    }

    if (!otp || typeof otp !== "string" || !/^\d{6}$/.test(otp)) {
      return NextResponse.json(
        { status: "error", message: "Please enter a valid 6-digit OTP." },
        { status: 400 }
      );
    }

    const normalizedEmail = email.trim().toLowerCase();

    // Find user by email
    const user = await db.user.findUnique({
      where: { email: normalizedEmail },
    });

    if (!user) {
      return NextResponse.json(
        { status: "error", message: "No account found with this email." },
        { status: 400 }
      );
    }

    // Check if OTP exists
    if (!user.otp_code) {
      return NextResponse.json(
        { status: "error", message: "No OTP found. Please request a new one." },
        { status: 400 }
      );
    }

    // Check if OTP is expired
    if (user.otp_expires && new Date() > user.otp_expires) {
      // Clear expired OTP
      await db.user.update({
        where: { id: user.id },
        data: { otp_code: null, otp_expires: null },
      });
      return NextResponse.json(
        { status: "error", message: "OTP has expired. Please request a new one." },
        { status: 400 }
      );
    }

    // Verify OTP (timing-safe comparison to prevent timing side-channel attacks)
    const storedOtp = (user.otp_code || "").padStart(6, "0");
    const providedOtp = (otp || "").padStart(6, "0");
    if (storedOtp.length !== 6 || providedOtp.length !== 6 ||
        !crypto.timingSafeEqual(Buffer.from(storedOtp), Buffer.from(providedOtp))) {
      return NextResponse.json(
        { status: "error", message: "Incorrect OTP. Please try again." },
        { status: 400 }
      );
    }

    // OTP is valid — mark as verified by keeping the otp_code
    // The reset-password endpoint will check otp_code is set
    return NextResponse.json({
      status: "success",
      message: "OTP verified successfully.",
    });
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Verify OTP error:", message);
    return NextResponse.json(
      { status: "error", message: "An unexpected error occurred. Please try again." },
      { status: 500 }
    );
  }
}
