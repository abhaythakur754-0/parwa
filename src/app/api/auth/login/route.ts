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
      const { response: backendRes } = await backendProxy("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: normalizedEmail, password }),
      });

      if (backendRes.ok) {
        const data = await backendRes.json();

        // Backend returns AuthResponse: { user, tokens, is_new_user }
        if (data.user && data.tokens) {
          const userData = {
            id: data.user.id,
            email: data.user.email || normalizedEmail,
            fullName: data.user.full_name,
            isVerified: data.user.is_verified ?? false,
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
            data.tokens.access_token,
            data.tokens.refresh_token,
            userData,
            data.tokens.expires_in,
          );

          return response;
        }
      }

      // Backend returned error (invalid credentials, locked, etc.)
      if (backendRes.status === 401 || backendRes.status === 403) {
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
          { status: backendRes.status === 403 ? 403 : 401 }
        );
      }

      // Other backend errors — fall through to local
      console.warn("[login] Backend returned", backendRes.status, "— falling back to local");
    } catch {
      // Backend unreachable — fall through to local DB
      console.warn("[login] Backend unreachable — falling back to local");
    }

    // ── Local Prisma fallback ──────────────────────────────────
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
