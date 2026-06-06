/**
 * PARWA Register API Route
 *
 * Handles user registration by:
 * 1. Trying the backend first (for Vercel deployment without local DB)
 * 2. Falling back to local Prisma if backend is unreachable
 * 3. Always signs our own JWT tokens and sets httpOnly cookies
 */

import { NextRequest, NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import crypto from "crypto";
import { getBackendUrl } from "@/lib/backend-url";
import { db } from "@/lib/db";
import { signAccessToken, signRefreshToken, validatePasswordStrength } from "@/lib/jwt";
import { setAuthCookies } from "@/lib/auth-cookies";

const BACKEND_URL = getBackendUrl();

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

    if (!password || typeof password !== "string") {
      return NextResponse.json(
        { status: "error", message: "Password is required." },
        { status: 400 }
      );
    }

    const passwordCheck = validatePasswordStrength(password);
    if (!passwordCheck.valid) {
      return NextResponse.json(
        { status: "error", message: passwordCheck.errors.join(" ") },
        { status: 400 }
      );
    }

    const normalizedEmail = email.trim().toLowerCase();

    // ── Try backend first ──────────────────────────────────────
    try {
      const backendRes = await fetch(`${BACKEND_URL}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: normalizedEmail,
          password,
          full_name: fullName,
          company_name: companyName,
          industry,
        }),
        signal: AbortSignal.timeout(8000),
      });

      if (backendRes.ok) {
        const backendData = await backendRes.json();
        if (backendData.user || backendData.data) {
          const user = backendData.user || backendData.data;
          const userData = {
            id: user.id || user.user_id,
            email: user.email || normalizedEmail,
            fullName: user.full_name || user.fullName || fullName,
            isVerified: user.is_verified ?? user.isVerified ?? false,
          };

          // Sign our own JWT for the frontend middleware
          const jwtPayload = {
            sub: userData.id,
            email: userData.email,
            role: "member",
            company_id: user.company_name || user.companyName || companyName || undefined,
            is_verified: userData.isVerified,
          };

          const accessToken = await signAccessToken(jwtPayload);
          const refreshToken = await signRefreshToken(jwtPayload);

          const response = NextResponse.json({
            status: "success",
            message: "Account created successfully! Please check your email to verify your account.",
            user: userData,
          });

          setAuthCookies(response, accessToken, refreshToken, userData);
          return response;
        }
      }

      // Backend returned conflict (email exists)
      if (backendRes.status === 409) {
        return NextResponse.json(
          { status: "error", message: "An account with this email already exists." },
          { status: 409 }
        );
      }

      // Other backend errors — fall through to local
    } catch {
      // Backend unreachable — fall through to local DB
    }

    // ── Local Prisma fallback ──────────────────────────────────

    // Check if email already exists
    const existingUser = await db.user.findUnique({
      where: { email: normalizedEmail },
    });

    if (existingUser) {
      return NextResponse.json(
        { status: "error", message: "An account with this email already exists." },
        { status: 409 }
      );
    }

    // Hash password
    const salt = await bcrypt.genSalt(12);
    const password_hash = await bcrypt.hash(password, salt);

    // New users start unverified
    const verificationToken = crypto.randomBytes(32).toString("hex");
    const verificationTokenExpires = new Date(Date.now() + 24 * 60 * 60 * 1000);

    const user = await db.user.create({
      data: {
        email: normalizedEmail,
        password_hash,
        full_name: fullName || null,
        company_name: companyName || null,
        industry: industry || null,
        is_verified: false,
        verification_token: verificationToken,
        verification_token_expires: verificationTokenExpires,
      },
    });

    // Send verification email (non-blocking)
    try {
      const { sendEmail } = await import("@/lib/email");
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
    }

    // Sign JWT tokens
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
