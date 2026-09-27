/**
 * PARWA Send OTP (business email verification)
 *
 * POST /api/verification/send-otp
 *
 * Proxies to the backend (POST /api/verification/send-otp), which owns OTP
 * generation, hashed storage, rate limiting, and Brevo delivery.
 *
 * WHY the backend sends the email: Brevo blocks API calls from Vercel's
 * rotating server IPs ("Authorised IPs" security), but Render's egress IP
 * is static and can be allowlisted. OTP codes also never touch this server.
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
  if (!email.includes("@")) {
    return NextResponse.json(
      { error: "validation_error", message: "Valid email address is required" },
      { status: 400 },
    );
  }

  try {
    const { response } = await backendProxy("/api/verification/send-otp", {
      method: "POST",
      body: JSON.stringify({ email }),
      authToken: token,
    });

    const data = await response.json().catch(() => ({}));

    if (response.ok) {
      return NextResponse.json({
        success: true,
        message: "OTP sent successfully",
        expires_in: data.expires_in ?? 600,
      });
    }

    // Backend error envelope: { error: { code, message } } — or FastAPI { detail }
    const detail = typeof data?.detail === "string" ? data.detail : null;
    return NextResponse.json(
      {
        error: data?.error?.code || "send_failed",
        message: data?.error?.message || detail || "Failed to send OTP email",
      },
      { status: response.status },
    );
  } catch {
    // Backend unreachable (likely Render cold start) — honest failure, no fake success
    return NextResponse.json(
      {
        error: "backend_unavailable",
        message: "We could not reach the verification service. Please try again shortly.",
      },
      { status: 502 },
    );
  }
}
