import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import crypto from "crypto";

/**
 * POST /api/auth/verify-otp
 * Verifies the 6-digit OTP sent to the user's email.
 * On success, returns a verified flag so the frontend can proceed to reset password.
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email, otp } = body;

    if (!email || typeof email !== "string" || !email.includes("@")) {
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
