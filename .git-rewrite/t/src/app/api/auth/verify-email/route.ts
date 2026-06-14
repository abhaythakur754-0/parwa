import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const token = searchParams.get("token");

    if (!token) {
      return NextResponse.json(
        { status: "error", message: "Verification token is required." },
        { status: 400 }
      );
    }

    // Find user by verification token
    const user = await db.user.findUnique({
      where: { verification_token: token },
    });

    if (!user) {
      return NextResponse.json(
        { status: "error", message: "Invalid or expired token." },
        { status: 400 }
      );
    }

    // Check if token is expired
    if (
      user.verification_token_expires &&
      new Date() > user.verification_token_expires
    ) {
      return NextResponse.json(
        { status: "error", message: "Verification token has expired. Please request a new one." },
        { status: 400 }
      );
    }

    // Mark user as verified and clear token
    await db.user.update({
      where: { id: user.id },
      data: {
        is_verified: true,
        verification_token: null,
        verification_token_expires: null,
      },
    });

    return NextResponse.json({
      status: "success",
      message: "Email verified successfully.",
    });
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Verify email error:", message);
    return NextResponse.json(
      { status: "error", message: "An unexpected error occurred. Please try again." },
      { status: 500 }
    );
  }
}
