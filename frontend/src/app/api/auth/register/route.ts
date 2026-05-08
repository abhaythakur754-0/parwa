import { NextRequest, NextResponse } from "next/server";
import bcrypt from "bcryptjs";
import { db } from "@/lib/db";

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

    // Password complexity requirements
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
    if (!/[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>?\/]/.test(password)) {
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

    // User must verify email before logging in
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

    return NextResponse.json({
      status: "success",
      message: "Account created! Please check your email to verify your account.",
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
