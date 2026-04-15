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

    // Validate required fields
    if (!email || typeof email !== "string" || !email.includes("@")) {
      return NextResponse.json(
        { status: "error", message: "A valid email address is required." },
        { status: 400 }
      );
    }

    if (
      !password ||
      typeof password !== "string" ||
      password.length < 8
    ) {
      return NextResponse.json(
        {
          status: "error",
          message: "Password must be at least 8 characters long.",
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

    // Create user (auto-verified for immediate login)
    const user = await db.user.create({
      data: {
        email: normalizedEmail,
        password_hash,
        full_name: fullName || null,
        company_name: companyName || null,
        industry: industry || null,
        is_verified: true,
      },
    });

    return NextResponse.json({
      status: "success",
      message: "Account created successfully!",
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
