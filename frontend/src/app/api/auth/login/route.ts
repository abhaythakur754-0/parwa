import { NextRequest, NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import crypto from "crypto";
import { db } from "@/lib/db";

// Simple in-memory rate limiter: 5 attempts per 15 minutes per email
const loginAttempts = new Map<string, number[]>();
const LOGIN_MAX_ATTEMPTS = 5;
const LOGIN_WINDOW_MS = 15 * 60 * 1000; // 15 minutes

// H1: TODO — In production, sessions should use Redis instead of an in-memory Map.
// The in-memory Map is NOT suitable for production because:
//   1. Sessions are lost on server restart / redeploy.
//   2. Sessions are not shared across multiple server instances (horizontal scaling).
//   3. Memory usage is unbounded without eviction.
// Replace with a Redis-backed session store before deploying to production.
// D10-P12 FIX: Server-side session tracking for logout invalidation.
// Maps session_token -> { email, createdAt }.
const serverSessions = new Map<string, { email: string; createdAt: number }>();
const SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

function generateSessionToken(): string {
  return crypto.randomBytes(32).toString('hex');
}

function cleanExpiredSessions(): void {
  const now = Date.now();
  for (const [token, data] of serverSessions.entries()) {
    if (now - data.createdAt > SESSION_TTL_MS) {
      serverSessions.delete(token);
    }
  }
}

function isLoginRateLimited(email: string): boolean {
  const now = Date.now();
  const attempts = loginAttempts.get(email) || [];
  const recent = attempts.filter((t) => now - t < LOGIN_WINDOW_MS);
  loginAttempts.set(email, recent);
  return recent.length >= LOGIN_MAX_ATTEMPTS;
}

function recordLoginAttempt(email: string): void {
  const now = Date.now();
  const attempts = loginAttempts.get(email) || [];
  attempts.push(now);
  // Prune old entries to prevent unbounded growth
  loginAttempts.set(
    email,
    attempts.filter((t) => now - t < LOGIN_WINDOW_MS),
  );
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email, password } = body;

    // Rate limit check
    if (typeof email === "string" && isLoginRateLimited(email.trim().toLowerCase())) {
      return NextResponse.json(
        { status: "error", message: "Too many login attempts. Please try again later." },
        { status: 429 }
      );
    }

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
    recordLoginAttempt(normalizedEmail);

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

    // D10-P12 FIX: Create server-side session and set httpOnly cookie
    cleanExpiredSessions();
    const sessionToken = generateSessionToken();
    serverSessions.set(sessionToken, { email: normalizedEmail, createdAt: Date.now() });

    const response = NextResponse.json({
      status: "success",
      user: {
        id: user.id,
        email: user.email,
        fullName: user.full_name,
        isVerified: user.is_verified,
      },
    });

    // Set httpOnly, Secure, SameSite cookie for server-side session validation
    response.cookies.set("parwa_session", sessionToken, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      maxAge: SESSION_TTL_MS / 1000,
      path: "/",
    });

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
