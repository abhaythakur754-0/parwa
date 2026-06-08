/**
 * PARWA Register API Route
 *
 * Handles user registration by:
 * 1. Forwarding registration data to the backend (primary)
 * 2. Storing the backend's JWT tokens in httpOnly cookies
 * 3. Falling back to local Prisma if backend is unreachable (dev only)
 */

import { NextRequest, NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import crypto from "crypto";
import { db } from "@/lib/db";
import { signAccessToken, signRefreshToken, validatePasswordStrength } from "@/lib/jwt";
import { setAuthCookies } from "@/lib/auth-cookies";
import { backendProxy } from "@/lib/backend-proxy";

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
      const { response: backendRes } = await backendProxy("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({
          email: normalizedEmail,
          password,
          confirm_password: password,
          full_name: fullName || "User",
          company_name: companyName || `${fullName || "User"}'s Company`,
          industry: industry || "general",
        }),
      });

      if (backendRes.ok) {
        const data = await backendRes.json();

        // Backend returns AuthResponse: { user, tokens, is_new_user }
        const authData = data.data || data;
        const userObj = authData.user || data.user;
        const tokensObj = authData.tokens || data.tokens;
        const isNewUser = authData.is_new_user ?? data.is_new_user ?? true;

        if (userObj && tokensObj) {
          const userData = {
            id: userObj.id,
            email: userObj.email || normalizedEmail,
            fullName: userObj.full_name || fullName,
            isVerified: userObj.is_verified ?? false,
          };

          const response = NextResponse.json({
            status: "success",
            message: "Account created successfully! Please check your email to verify your account.",
            user: userData,
            is_new_user: isNewUser,
          });

          // Store BACKEND's tokens in cookies
          setAuthCookies(
            response,
            tokensObj.access_token,
            tokensObj.refresh_token,
            userData,
            tokensObj.expires_in,
          );

          return response;
        }
      }

      // Backend returned conflict (email exists)
      if (backendRes.status === 409) {
        let errorData: Record<string, unknown> = {};
        try { errorData = await backendRes.json(); } catch { /* ignore */ }
        const detail = errorData.detail;
        const message =
          (typeof detail === "object" && detail !== null && "message" in detail)
            ? String((detail as Record<string, unknown>).message)
            : (typeof detail === "string" ? detail : null)
            || (errorData as Record<string, unknown>).message
            || "An account with this email already exists.";
        return NextResponse.json(
          { status: "error", message },
          { status: 409 }
        );
      }

      // Backend validation errors
      if (backendRes.status === 422) {
        let errorData: Record<string, unknown> = {};
        try { errorData = await backendRes.json(); } catch { /* ignore */ }
        const detail = errorData.detail;
        let message = "Registration failed. Please check your inputs.";
        if (typeof detail === "string") {
          message = detail;
        } else if (Array.isArray(detail)) {
          message = detail.map((e: Record<string, unknown>) => e.msg || String(e)).join(". ");
        } else if (typeof detail === "object" && detail !== null && "message" in detail) {
          message = String((detail as Record<string, unknown>).message);
        }
        return NextResponse.json(
          { status: "error", message },
          { status: 400 }
        );
      }

      // CSRF / Origin errors — do NOT fall through to local Prisma
      // A 403 from the backend is a CSRF rejection, not a real auth error.
      // Falling through to Prisma causes a broken "server error" because
      // Prisma isn't configured on Vercel/Netlify deployments.
      if (backendRes.status === 403) {
        let errorData: Record<string, unknown> = {};
        try { errorData = await backendRes.json(); } catch { /* ignore */ }
        const detail = errorData.detail;
        const errorMsg = (errorData?.error as Record<string, unknown>)?.message || errorData?.message;
        const message =
          (typeof detail === "object" && detail !== null && "message" in detail)
            ? String((detail as Record<string, unknown>).message)
            : (typeof detail === "string" ? detail : null)
            || (typeof errorMsg === "string" ? errorMsg : null)
            || "Registration temporarily unavailable. Please try again.";
        return NextResponse.json(
          { status: "error", message },
          { status: 503 }
        );
      }

      // Other backend errors — fall through to local
      console.warn("[register] Backend returned", backendRes.status, "— falling back to local");
    } catch {
      // Backend unreachable — fall through to local DB
      console.warn("[register] Backend unreachable — falling back to local");
    }

    // ── Local Prisma fallback ──────────────────────────────────
    try {
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
        const verificationUrl = `/api/auth/verify-email?token=${verificationToken}`;
        const htmlContent = `
          <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #E06A00;">Welcome to PARWA!</h2>
            <p>Hi ${fullName || "there"},</p>
            <p>Please verify your email address by clicking the link below:</p>
            <p><a href="${verificationUrl}" style="display: inline-block; padding: 12px 24px; background: #E06A00; color: white; text-decoration: none; border-radius: 8px;">Verify Email</a></p>
            <p>This link expires in 24 hours.</p>
          </div>
        `;
        await sendEmail(normalizedEmail, "PARWA — Verify Your Email", htmlContent);
      } catch (emailError) {
        console.error("Failed to send verification email:", emailError);
      }

      // Sign our own JWT tokens (local fallback only)
      // NOTE: company_id must be a UUID-like string for the backend's
      // TenantMiddleware. Use user.id as company_id (1:1 company per user).
      const jwtPayload = {
        sub: user.id,
        email: user.email,
        role: "member",
        company_id: user.id,
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
    } catch (dbError) {
      // Prisma/DB not available (e.g., on Vercel without DATABASE_URL)
      console.error("[register] Local DB fallback failed:", dbError);
      return NextResponse.json(
        { status: "error", message: "The server is starting up — please wait a moment and try again." },
        { status: 503 }
      );
    }
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
