import { NextRequest, NextResponse } from "next/server";

/**
 * POST /api/auth/reset-password
 * Resets the user's password.
 * Proxies to the Python backend at /api/auth/reset-password.
 */
const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Proxy to backend
    const backendRes = await fetch(`${BACKEND_URL}/api/auth/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const contentType = backendRes.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      const data = await backendRes.json();
      if (backendRes.ok) {
        return NextResponse.json({
          status: "success",
          message: data.message || "Password has been reset successfully.",
        });
      }
      return NextResponse.json(
        {
          status: "error",
          message: data.detail || data.message || "Password reset failed.",
        },
        { status: backendRes.status }
      );
    }

    const text = await backendRes.text();
    return NextResponse.json(
      { status: "error", message: text || "Password reset failed." },
      { status: backendRes.status }
    );
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Reset password error:", message);
    return NextResponse.json(
      { status: "error", message: "An unexpected error occurred. Please try again." },
      { status: 500 }
    );
  }
}
