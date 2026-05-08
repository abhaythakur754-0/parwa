import { NextRequest, NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import crypto from "crypto";
import { db } from "@/lib/db";
import { signAccessToken, signRefreshToken, validatePasswordStrength } from "@/lib/jwt";
import { setAuthCookies } from "@/lib/auth-cookies";
import { sendEmail } from "@/lib/email";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email, password, fullName, companyName, industry } = body;

    // Validate required fields
    if (!email || typeof email !== "string" || !email.includes("@")) {
      return NextResponse.json(
        { status: "error", message: "A valid email address is required." },
        { status: 400 }
      );
    }

    // ── M-20 FIX: Password complexity requirements ──
    if (!password || typeof password !== "string") {
      return NextResponse.json(
        { status: "error", message: "Password is required." },
        { status: 400 }
      );
    }

    const passwordCheck = validatePasswordStrength(password);
    if (!passwordCheck.valid) {
      return NextResponse.json(
        {
          status: "error",
          message: passwordCheck.errors.join(" "),
        },
        { status: 400 }
      );
    }

    const normalizedEmail = email.trim().toLowerCase();

    // Check if email already exists
    const existingUser = await db.user.findUnique({
      where: { email: normalizedEmail },
    });

    if (existingUser) {
      return NextResponse.json(
        {
          status: "error",
          message: "An account with this email already exists.",
        },
        { status: 409 }
      );
    }

    // Hash password
    const salt = await bcrypt.genSalt(12);
    const password_hash = await bcrypt.hash(password, salt);

    // ── H-03 FIX: New users start unverified, require email verification ──
    const verificationToken = crypto.randomBytes(32).toString("hex");
    const verificationTokenExpires = new Date(Date.now() + 24 * 60 * 60 * 1000); // 24 hours

    const user = await db.user.create({
      data: {
        email: normalizedEmail,
        password_hash,
        full_name: fullName || null,
        company_name: companyName || null,
        industry: industry || null,
        is_verified: false, // FIX: Require email verification
        verification_token: verificationToken,
        verification_token_expires: verificationTokenExpires,
      },
    });

    // Send verification email
    try {
      const verificationUrl = `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:3000"}/api/auth/verify-email?token=${verificationToken}`;
      const htmlContent = `
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
          <h2 style="color: #E06A00;">Welcome to PARWA!</h2>
          <p>Hi ${fullName || "there"},</p>
          <p>Please verify your email address by clicking the link below:</p>
          <p><a href="${verificationUrl}" style="display: inline-block; padding: 12px 24px; background: #E06A00; color: white; text-decoration: none; border-radius: 8px;">Verify Email</a></p>
          <p>This link expires in 24 hours.</p>
          <p style="color: #888; font-size: 12px;">If you didn't create an account, please ignore this email.</p>
        </div>
      `;
      await sendEmail(normalizedEmail, "PARWA — Verify Your Email", htmlContent);
    } catch (emailError) {
      console.error("Failed to send verification email:", emailError);
      // Don't block registration if email fails — user can request a new verification
    }

    // ── C-02 FIX: Real signed JWT tokens ──
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

    const response = NextResponse.json({
      status: "success",
      message: "Account created successfully! Please check your email to verify your account.",
      user: userData,
    });

    setAuthCookies(response, accessToken, refreshToken, userData);

    return response;
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Register error:", message);
    return NextResponse.json(
      { status: "error", message: "An unexpected error occurred. Please try again." },
      { status: 500 }
    );
  }
}
