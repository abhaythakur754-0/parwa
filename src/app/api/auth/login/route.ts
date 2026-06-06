/**
 * PARWA Login API Route
 *
 * Handles email/password login by:
 * 1. Trying the backend first (for Vercel deployment without local DB)
 * 2. Falling back to local Prisma if backend is unreachable
 * 3. Always signs our own JWT tokens and sets httpOnly cookies
 */

import { NextRequest, NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import { getBackendUrl } from "@/lib/backend-url";
import { db } from "@/lib/db";
import { signAccessToken, signRefreshToken } from "@/lib/jwt";
import { setAuthCookies } from "@/lib/auth-cookies";

const BACKEND_URL = getBackendUrl();

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
      const backendRes = await fetch(`${BACKEND_URL}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: normalizedEmail, password }),
        signal: AbortSignal.timeout(8000),
      });

      if (backendRes.ok) {
        const backendData = await backendRes.json();

        // Backend verified the credentials — sign our own JWT and set cookies
        if (backendData.user || backendData.data) {
          const user = backendData.user || backendData.data;
          const userData = {
            id: user.id || user.user_id,
            email: user.email || normalizedEmail,
            fullName: user.full_name || user.fullName,
            isVerified: user.is_verified ?? user.isVerified ?? false,
          };

          const jwtPayload = {
            sub: userData.id,
            email: userData.email,
            role: "member",
            company_id: user.company_name || user.companyName || undefined,
            is_verified: userData.isVerified,
          };

          const accessToken = await signAccessToken(jwtPayload);
          const refreshToken = await signRefreshToken(jwtPayload);

          const response = NextResponse.json({
            status: "success",
            message: "Login successful.",
            user: userData,
            is_new_user: backendData.is_new_user ?? false,
          });

          setAuthCookies(response, accessToken, refreshToken, userData);
          return response;
        }
      }
      // Backend returned error (invalid credentials, etc.)
      if (backendRes.status === 401 || backendRes.status === 403) {
        const errorData = await backendRes.json().catch(() => ({}));
        return NextResponse.json(
          {
            status: "error",
            message: errorData.message || errorData.detail || "Invalid email or password.",
          },
          { status: backendRes.status }
        );
      }
      // Other backend errors — fall through to local
    } catch {
      // Backend unreachable — fall through to local DB
    }

    // ── Local Prisma fallback ──────────────────────────────────
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
