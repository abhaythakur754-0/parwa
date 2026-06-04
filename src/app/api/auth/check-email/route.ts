import { NextRequest, NextResponse } from "next/server";
import { proxyAuthRequest } from "@/lib/backend-proxy";

/**
 * POST /api/auth/check-email
 * Proxies to backend: GET /api/auth/check-email?email=...
 *
 * Checks if an email is available for registration.
 * The backend uses the actual Supabase PostgreSQL database.
 *
 * Frontend sends: { email }
 * Backend expects: GET /api/auth/check-email?email=...
 * Backend returns: { available: true } or { available: false, message: "..." }
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email } = body;

    if (!email || typeof email !== "string" || !email.includes("@")) {
      return NextResponse.json(
        { status: "error", message: "A valid email address is required." },
        { status: 400 }
      );
    }

    // Proxy to backend check-email endpoint
    return proxyAuthRequest(request, {
      backendPath: `/api/auth/check-email?email=${encodeURIComponent(email.trim().toLowerCase())}`,
      method: "GET",
    });
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Check email error:", message);
    return NextResponse.json(
      { status: "error", message: "An unexpected error occurred." },
      { status: 500 }
    );
  }
}

/**
 * GET /api/auth/check-email?email=...
 * Also supports GET requests for compatibility.
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const email = searchParams.get("email");

    if (!email || !email.includes("@")) {
      return NextResponse.json(
        { status: "error", message: "A valid email address is required." },
        { status: 400 }
      );
    }

    // Proxy to backend check-email endpoint
    return proxyAuthRequest(request, {
      backendPath: `/api/auth/check-email?email=${encodeURIComponent(email.trim().toLowerCase())}`,
      method: "GET",
    });
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Check email error:", message);
    return NextResponse.json(
      { status: "error", message: "An unexpected error occurred." },
      { status: 500 }
    );
  }
}
