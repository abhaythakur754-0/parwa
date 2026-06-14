import { NextRequest, NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import { db } from "@/lib/db";
import { signAccessToken, signRefreshToken, validatePasswordStrength } from "@/lib/jwt";
import { setAuthCookies } from "@/lib/auth-cookies";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email, password } = body;

    if (!email || typeof email !== "string" || !email.includes("@")) {
      return NextResponse.json(
        { status: "error", message: "A valid email address is required." },
        { status: 400 }
      );
    }

    if (!password || typeof password !== "string") {
      return NextResponse.json(
        { status: "error", message: "Password is required." },
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
        { status: "error", message: "Invalid email or password." },
        { status: 401 }
      );
    }

    // Check password
    if (!user.password_hash) {
      return NextResponse.json(
        { status: "error", message: "Invalid email or password." },
        { status: 401 }
      );
    }

    const isPasswordValid = await bcrypt.compare(password, user.password_hash);
    if (!isPasswordValid) {
      return NextResponse.json(
        { status: "error", message: "Invalid email or password." },
        { status: 401 }
      );
    }

    // Check if verified
    if (!user.is_verified) {
      return NextResponse.json(
        {
          status: "error",
          message: "Please verify your email address before logging in.",
        },
        { status: 403 }
      );
    }

    // ── C-02 FIX: Real signed JWT tokens instead of fake UUIDs ──
    const jwtPayload = {
      sub: user.id,
      email: user.email,
      role: "member",
      company_id: user.company_name || undefined,
      is_verified: user.is_verified,
    };

    const accessToken = await signAccessToken(jwtPayload);
    const refreshToken = await signRefreshToken(jwtPayload);

    const userData = {
      id: user.id,
      email: user.email,
      fullName: user.full_name,
      isVerified: user.is_verified,
    };

    // ── C-03 FIX: Set tokens as httpOnly cookies ──
    const response = NextResponse.json({
      status: "success",
      message: "Login successful.",
      user: userData,
    });

    setAuthCookies(response, accessToken, refreshToken, userData);

    return response;
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Login error:", message);
    return NextResponse.json(
      { status: "error", message: "An unexpected error occurred. Please try again." },
      { status: 500 }
    );
  }
}
