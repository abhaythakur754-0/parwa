/**
 * PARWA Login API Route
 *
 * Handles email/password login by:
 * 1. Forwarding credentials to the backend (primary)
 * 2. Storing the backend's JWT tokens in httpOnly cookies
 * 3. Falling back to local Prisma if backend is unreachable (dev only)
 */

import { NextRequest, NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import { db } from "@/lib/db";
import { signAccessToken, signRefreshToken } from "@/lib/jwt";
import { setAuthCookies } from "@/lib/auth-cookies";
import { backendProxy } from "@/lib/backend-proxy";

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

    // ── Try backend first ──────────────────────────────────────
    try {
      const { response: backendRes } = await backendProxy("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: normalizedEmail, password }),
      });

      if (backendRes.ok) {
        const data = await backendRes.json();

        // Backend returns: { access_token, refresh_token, token_type, user }
        // Also support nested format: { tokens: { access_token, refresh_token } }
        const accessToken = data.access_token || data.tokens?.access_token;
        const refreshToken = data.refresh_token || data.tokens?.refresh_token;
        const userObj = data.user;
        const expiresIn = data.expires_in || data.tokens?.expires_in;

        if (userObj && accessToken) {
          const userData = {
            id: userObj.id,
            email: userObj.email || normalizedEmail,
            fullName: userObj.full_name || userObj.name,
            isVerified: userObj.is_verified ?? false,
          };

          const response = NextResponse.json({
            status: "success",
            message: "Login successful.",
            user: userData,
            is_new_user: data.is_new_user ?? false,
          });

          // Store BACKEND's tokens in cookies
          setAuthCookies(
            response,
            accessToken,
            refreshToken,
            userData,
            expiresIn,
          );

          return response;
        }
      }

      // Backend returned 403 — could be CSRF/origin error or forbidden
      // Do NOT fall through to local Prisma — return a clear error instead
      if (backendRes.status === 403) {
        let errorData: Record<string, unknown> = {};
        try { errorData = await backendRes.json(); } catch { /* ignore */ }
        const detail = errorData.detail;
        const errorMsg = (errorData?.error as Record<string, unknown>)?.message || errorData?.message;
        const rawMessage =
          (typeof detail === "object" && detail !== null && "message" in detail)
            ? String((detail as Record<string, unknown>).message)
            : (typeof detail === "string" ? detail : null)
            || (typeof errorMsg === "string" ? errorMsg : null);
        // If it's a CSRF/origin error, return 503 (service unavailable) not 403
        const isCSRF = rawMessage?.toLowerCase().includes('csrf') ||
          rawMessage?.toLowerCase().includes('invalid origin');
        if (isCSRF) {
          return NextResponse.json(
            { status: "error", message: "Login temporarily unavailable. Please try again." },
            { status: 503 }
          );
        }
        return NextResponse.json(
          { status: "error", message: rawMessage || "Access denied." },
          { status: 403 }
        );
      }

      // Backend returned 401 — invalid credentials
      if (backendRes.status === 401) {
        let errorData: Record<string, unknown> = {};
        try { errorData = await backendRes.json(); } catch { /* ignore */ }
        const detail = errorData.detail;
        const message =
          (typeof detail === "object" && detail !== null && "message" in detail)
            ? String((detail as Record<string, unknown>).message)
            : (typeof detail === "string" ? detail : null)
            || (errorData as Record<string, unknown>).message
            || "Invalid email or password.";
        return NextResponse.json(
          { status: "error", message },
          { status: 401 }
        );
      }

      // Other backend errors — fall through to local
      console.warn("[login] Backend returned", backendRes.status, "— falling back to local");
    } catch {
      // Backend unreachable — fall through to local DB
      console.warn("[login] Backend unreachable — falling back to local");
    }

    // ── Local Prisma fallback ──────────────────────────────────
    if (!db) {
      return NextResponse.json(
        { status: "error", message: "Backend unavailable. Please try again later." },
        { status: 503 }
      );
    }
    try {
      const user = await db.user.findUnique({
        where: { email: normalizedEmail },
      });

      if (!user) {
        return NextResponse.json(
          { status: "error", message: "Invalid email or password." },
          { status: 401 }
        );
      }

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

      if (!user.is_verified) {
        return NextResponse.json(
          {
            status: "error",
            message: "Please verify your email address before logging in.",
          },
          { status: 403 }
        );
      }

      // Sign our own JWT tokens (local fallback only)
      // NOTE: company_id must be a UUID-like string for the backend's
      // TenantMiddleware. The Prisma User model doesn't have a company_id
      // column, so we derive one deterministically from the user's email
      // to ensure consistency across login sessions.
      const jwtPayload = {
        sub: user.id,
        email: user.email,
        role: "member",
        company_id: user.id, // Use user.id as company_id (1:1 company per user)
        is_verified: user.is_verified,
      };

      const accessToken = await signAccessToken(jwtPayload);
      const refreshToken = await signRefreshToken(jwtPayload);

      const userData = {
        id: user.id,
        email: user.email,
        fullName: user.full_name || user.name,
        isVerified: user.is_verified,
      };

      const response = NextResponse.json({
        status: "success",
        message: "Login successful.",
        user: userData,
      });

      setAuthCookies(response, accessToken, refreshToken, userData);

      return response;
    } catch (dbError) {
      // Prisma/DB not available (e.g., on Vercel without DATABASE_URL)
      console.error("[login] Local DB fallback failed:", dbError);
      return NextResponse.json(
        { status: "error", message: "The server is starting up — please wait a moment and try again." },
        { status: 503 }
      );
    }
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
