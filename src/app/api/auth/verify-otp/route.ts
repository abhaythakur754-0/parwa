import { NextRequest, NextResponse } from "next/server";

/**
 * POST /api/auth/verify-otp
 * Verifies the 6-digit OTP sent to the user's email.
 * Proxies to the Python backend.
 */
import { getBackendUrl } from '@/lib/backend-url';
const BACKEND_URL = getBackendUrl();

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email, otp } = body;

    if (!email || typeof email !== "string" || !email.includes("@")) {
      return NextResponse.json(
        { status: "error", message: "A valid email address is required." },
        { status: 400 }
      );
    }

    if (!otp || typeof otp !== "string" || !/^\d{6}$/.test(otp)) {
      return NextResponse.json(
        { status: "error", message: "Please enter a valid 6-digit OTP." },
        { status: 400 }
      );
    }

    // Proxy to backend
    const backendRes = await fetch(`${BACKEND_URL}/api/auth/phone/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: email.trim().toLowerCase(), code: otp }),
    });

    const contentType = backendRes.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const data = await backendRes.json();
      if (backendRes.ok) {
        return NextResponse.json({
          status: "success",
          message: data.message || "OTP verified successfully.",
        });
      }
      return NextResponse.json(
        {
          status: "error",
          message: data.detail || data.message || "Invalid OTP. Please try again.",
        },
        { status: backendRes.status }
      );
    }

    return NextResponse.json(
      { status: "error", message: "Invalid OTP. Please try again." },
      { status: 400 }
    );
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Verify OTP error:", message);
    return NextResponse.json(
      { status: "error", message: "An unexpected error occurred. Please try again." },
      { status: 500 }
    );
  }
}
