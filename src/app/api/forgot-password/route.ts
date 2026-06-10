import { NextRequest, NextResponse } from "next/server";

/**
 * POST /api/forgot-password
 * Sends a password reset email/OTP to the user.
 * Proxies to the Python backend at /api/auth/forgot-password.
 */
import { getBackendUrl } from '@/lib/backend-url';
const BACKEND_URL = getBackendUrl();

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email } = body;

    if (!email || typeof email !== "string" || !email.includes("@")) {
      return NextResponse.json(
        { status: "error", message: "Please provide a valid email address." },
        { status: 400 }
      );
    }

    // Proxy to backend
    try {
      const backendRes = await fetch(`${BACKEND_URL}/api/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });

      const contentType = backendRes.headers.get("content-type") || "";
      if (contentType.includes("application/json")) {
        const data = await backendRes.json();
        return NextResponse.json({
          status: "success",
          message: data.message || "If an account with this email exists, further instructions have been sent.",
        });
      }
    } catch {
      // Backend unavailable — return generic message
    }

    // Generic response that doesn't reveal whether email exists
    return NextResponse.json({
      status: "success",
      message: "If an account with this email exists, further instructions have been sent.",
    });
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Forgot password error:", message);
    return NextResponse.json(
      { status: "error", message: "An unexpected error occurred. Please try again." },
      { status: 500 }
    );
  }
}
