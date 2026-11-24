import { NextRequest, NextResponse } from "next/server";

/**
 * POST /api/forgot-password
 * Sends a password reset email/OTP to the user.
 * Proxies to the Python backend at /api/auth/forgot-password.
 */
const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email } = body;

    if (!email || typeof email !== "string" || !/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email)) {
      return NextResponse.json(
        { status: "error", message: "Please provide a valid email address." },
        { status: 400, headers: { "Cache-Control": "no-store" } }
      );
    }

    try {
      const backendRes = await fetch(`${BACKEND_URL}/api/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
        signal: AbortSignal.timeout(15_000),
        redirect: "manual",
      });

      if (backendRes.status === 429) {
        return NextResponse.json(
          { status: "error", message: "Too many reset attempts. Please try again later." },
          {
            status: 429,
            headers: {
              "Retry-After": backendRes.headers.get("retry-after") || "60",
              "Cache-Control": "no-store",
            },
          }
        );
      }

      if (!backendRes.ok) {
        console.error("Forgot password backend returned status:", backendRes.status);
        return NextResponse.json(
          { status: "error", message: "Password reset is temporarily unavailable. Please try again." },
          { status: 503, headers: { "Cache-Control": "no-store" } }
        );
      }

      // Keep the response identical for existing and unknown accounts.
      return NextResponse.json(
        {
          status: "success",
          message: "If an account with this email exists, further instructions have been sent.",
        },
        { headers: { "Cache-Control": "no-store" } }
      );
    } catch (error: unknown) {
      console.error(
        "Forgot password backend unavailable:",
        error instanceof Error ? error.name : "UnknownError"
      );
      return NextResponse.json(
        { status: "error", message: "Password reset is temporarily unavailable. Please try again." },
        { status: 503, headers: { "Cache-Control": "no-store" } }
      );
    }
  } catch (error: unknown) {
    if (error instanceof SyntaxError) {
      return NextResponse.json(
        { status: "error", message: "Invalid request body." },
        { status: 400, headers: { "Cache-Control": "no-store" } }
      );
    }
    console.error(
      "Forgot password request error:",
      error instanceof Error ? error.name : "UnknownError"
    );
    return NextResponse.json(
      { status: "error", message: "An unexpected error occurred. Please try again." },
      { status: 500, headers: { "Cache-Control": "no-store" } }
    );
  }
}
