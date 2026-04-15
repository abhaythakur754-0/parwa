import { NextRequest, NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import crypto from "crypto";
import { db } from "@/lib/db";

/**
 * POST /api/auth/reset-password
 * Resets the user's password after OTP verification.
 * Requires email + otp + new_password.
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email, otp, new_password, confirm_password } = body;

    // Validate inputs
    if (!email || typeof email !== "string" || !email.includes("@")) {
      return NextResponse.json(
        { status: "error", message: "A valid email address is required." },
        { status: 400 }
      );
    }

    if (!otp || typeof otp !== "string" || !/^\d{6}$/.test(otp)) {
      return NextResponse.json(
        { status: "error", message: "A valid 6-digit OTP is required." },
        { status: 400 }
      );
    }

    if (
      !new_password ||
      typeof new_password !== "string" ||
      new_password.length < 8
    ) {
      return NextResponse.json(
        {
          status: "error",
          message: "New password must be at least 8 characters long.",
        },
        { status: 400 }
      );
    }

    if (new_password !== confirm_password) {
      return NextResponse.json(
        { status: "error", message: "Passwords do not match." },
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

    // Check OTP exists and hasn't expired
    if (!user.otp_code) {
      return NextResponse.json(
        { status: "error", message: "No OTP found. Please request a new one." },
        { status: 400 }
      );
    }

    if (user.otp_expires && new Date() > user.otp_expires) {
      await db.user.update({
        where: { id: user.id },
        data: { otp_code: null, otp_expires: null },
      });
      return NextResponse.json(
        { status: "error", message: "OTP has expired. Please request a new one." },
        { status: 400 }
      );
    }

    // Verify OTP (timing-safe comparison)
    const storedOtp = (user.otp_code || "").padStart(6, "0");
    const providedOtp = (otp || "").padStart(6, "0");
    if (storedOtp.length !== 6 || providedOtp.length !== 6 ||
        !crypto.timingSafeEqual(Buffer.from(storedOtp), Buffer.from(providedOtp))) {
      return NextResponse.json(
        { status: "error", message: "Incorrect OTP. Please try again." },
        { status: 400 }
      );
    }

    // Hash new password
    const salt = await bcrypt.genSalt(12);
    const password_hash = await bcrypt.hash(new_password, salt);

    // Update user — set new password and clear OTP
    await db.user.update({
      where: { id: user.id },
      data: {
        password_hash,
        otp_code: null,
        otp_expires: null,
        reset_token: null,
        reset_token_expires: null,
      },
    });

    return NextResponse.json({
      status: "success",
      message: "Password has been reset successfully.",
    });
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Reset password error:", message);
    return NextResponse.json(
      { status: "error", message: "An unexpected error occurred. Please try again." },
      { status: 500 }
    );
  }
}
