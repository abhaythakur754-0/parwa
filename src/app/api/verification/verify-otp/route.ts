/**
 * PARWA Verify OTP (business email verification)
 *
 * POST /api/verification/verify-otp
 *
 * Proxies to the backend (POST /api/verification/verify-otp), which checks
 * the code against hashed OTPs in Postgres (max 5 attempts, 10-min expiry).
 * Verification lives on the backend so the code can never be bypassed here.
 */

import { NextRequest, NextResponse } from "next/server";
import { backendProxy } from "@/lib/backend-proxy";

function getAuthToken(req: NextRequest): string | null {
  const authHeader = req.headers.get("authorization");
  if (authHeader?.startsWith("Bearer ")) return authHeader.slice(7);
  return req.cookies.get("parwa_at")?.value ?? null;
}

export async function POST(request: NextRequest) {
  const token = getAuthToken(request);
  if (!token) {
    return NextResponse.json(
      { error: "unauthorized", message: "Please sign in to verify your email." },
      { status: 401 },
    );
  }

  const body = await request.json().catch(() => null);
  const email = typeof body?.email === "string" ? body.email.trim().toLowerCase() : "";
  const otp = typeof body?.otp === "string" ? body.otp.trim() : "";

  if (!email.includes("@") || !/^\d{6}$/.test(otp)) {
    return NextResponse.json(
      { error: "validation_error", message: "Email and a 6-digit OTP are required" },
      { status: 400 },
    );
  }

  try {
    const { response } = await backendProxy("/api/verification/verify-otp", {
      method: "POST",
      body: JSON.stringify({ email, otp_code: otp }),
      authToken: token,
    });

    const data = await response.json().catch(() => ({}));

    if (response.ok) {
      return NextResponse.json({
        success: true,
        verified: true,
        message: data.message || "Email verified successfully",
      });
    }

    // Backend error envelope: { error: { code, message } } — or FastAPI { detail }
    const detail = typeof data?.detail === "string" ? data.detail : null;
    return NextResponse.json(
      {
        error: data?.error?.code || "invalid_otp",
        message: data?.error?.message || detail || "Invalid or expired OTP",
      },
      { status: response.status },
    );
  } catch {
    // Backend unreachable — honest failure, no fake success
    return NextResponse.json(
      {
        error: "backend_unavailable",
        message: "We could not reach the verification service. Please try again shortly.",
      },
      { status: 502 },
    );
  }
}
