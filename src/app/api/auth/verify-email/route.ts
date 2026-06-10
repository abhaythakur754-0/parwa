import { NextRequest, NextResponse } from "next/server";

/**
 * GET /api/auth/verify-email
 * Verifies a user's email using a token.
 * Proxies to the Python backend at /api/auth/verify.
 */
import { getBackendUrl } from '@/lib/backend-url';
const BACKEND_URL = getBackendUrl();

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const token = searchParams.get("token");

    if (!token) {
      return NextResponse.json(
        { status: "error", message: "Verification token is required." },
        { status: 400 }
      );
    }

    // Proxy to backend
    const backendRes = await fetch(
      `${BACKEND_URL}/api/auth/verify?token=${encodeURIComponent(token)}`,
      { method: "GET" }
    );

    const contentType = backendRes.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const data = await backendRes.json();
      if (backendRes.ok) {
        return NextResponse.json({
          status: "success",
          message: data.message || "Email verified successfully.",
        });
      }
      return NextResponse.json(
        {
          status: "error",
          message: data.detail || data.message || "Invalid or expired token.",
        },
        { status: backendRes.status }
      );
    }

    // Non-JSON response
    const text = await backendRes.text();
    return NextResponse.json(
      { status: "error", message: text || "Verification failed." },
      { status: backendRes.status }
    );
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Verify email error:", message);
    return NextResponse.json(
      { status: "error", message: "An unexpected error occurred. Please try again." },
      { status: 500 }
    );
  }
}
