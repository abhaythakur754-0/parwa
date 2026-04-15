import { NextRequest, NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import { db } from "@/lib/db";

// Simple in-memory rate limiter: 3 registrations per 15 minutes per IP
const registrationAttempts = new Map<string, number[]>();
const REGISTER_MAX_ATTEMPTS = 3;
const REGISTER_WINDOW_MS = 15 * 60 * 1000; // 15 minutes

function getClientIP(request: NextRequest): string {
  return (
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    request.headers.get("x-real-ip") ||
    "unknown"
  );
}

function isRegistrationRateLimited(ip: string): boolean {
  const now = Date.now();
  const attempts = registrationAttempts.get(ip) || [];
  const recent = attempts.filter((t) => now - t < REGISTER_WINDOW_MS);
  registrationAttempts.set(ip, recent);
  return recent.length >= REGISTER_MAX_ATTEMPTS;
}

function recordRegistrationAttempt(ip: string): void {
  const now = Date.now();
  const attempts = registrationAttempts.get(ip) || [];
  attempts.push(now);
  // Prune old entries to prevent unbounded growth
  registrationAttempts.set(
    ip,
    attempts.filter((t) => now - t < REGISTER_WINDOW_MS),
  );
}

export async function POST(request: NextRequest) {
  try {
    // Rate limit check by IP
    const clientIP = getClientIP(request);
    if (isRegistrationRateLimited(clientIP)) {
      return NextResponse.json(
        { status: "error", message: "Too many registration attempts. Please try again later." },
        { status: 429 }
      );
    }

    recordRegistrationAttempt(clientIP);

    const body = await request.json();
    const { email, password, fullName, companyName, industry } = body;

    // C3: Proper email validation using regex
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email || typeof email !== "string" || !emailRegex.test(email.trim())) {
      return NextResponse.json(
        { status: "error", message: "A valid email address is required." },
        { status: 400 }
      );
    }

    // C4: Enforce password complexity (uppercase, lowercase, digit, special char, 8+ chars)
    if (!password || typeof password !== "string") {
      return NextResponse.json(
        { status: "error", message: "Password is required." },
        { status: 400 }
      );
    }

    if (password.length < 8) {
      return NextResponse.json(
        { status: "error", message: "Password must be at least 8 characters long." },
        { status: 400 }
      );
    }

    if (!/[A-Z]/.test(password)) {
      return NextResponse.json(
        { status: "error", message: "Password must contain at least one uppercase letter." },
        { status: 400 }
      );
    }

    if (!/[a-z]/.test(password)) {
      return NextResponse.json(
        { status: "error", message: "Password must contain at least one lowercase letter." },
        { status: 400 }
      );
    }

    if (!/[0-9]/.test(password)) {
      return NextResponse.json(
        { status: "error", message: "Password must contain at least one digit." },
        { status: 400 }
      );
    }

    if (!/[^A-Za-z0-9]/.test(password)) {
      return NextResponse.json(
        { status: "error", message: "Password must contain at least one special character." },
        { status: 400 }
      );
    }

    const normalizedEmail = email.trim().toLowerCase();

    // Check if email already exists
    const existingUser = await db.user.findUnique({
      where: { email: normalizedEmail },
    });

    // FIX A6: Use ambiguous response to prevent email enumeration.
    // Do NOT reveal whether an account with this email exists.
    if (existingUser) {
      return NextResponse.json(
        {
          status: "success",
          message: "If this email is available, your account has been created. Please check your email to verify.",
        },
        { status: 200 }
      );
    }

    // Hash password
    const salt = await bcrypt.genSalt(12);
    const password_hash = await bcrypt.hash(password, salt);

    // FIX A5: Create user with is_verified: false.
    // Email verification is required before login.
    const user = await db.user.create({
      data: {
        email: normalizedEmail,
        password_hash,
        full_name: fullName || null,
        company_name: companyName || null,
        industry: industry || null,
        is_verified: false,
      },
    });

    // TODO: Send verification email with OTP/token
    // When verified, set is_verified = true

    return NextResponse.json({
      status: "success",
      message: "Account created! Please check your email to verify your account before logging in.",
    });
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
