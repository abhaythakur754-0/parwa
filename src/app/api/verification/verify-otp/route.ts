/**
 * SHOBH Verify OTP (business email verification)
 *
 * POST /api/verification/verify-otp
 *
 * Proxies to the backend (POST /api/verification/verify-otp), which checks
 * the code against hashed OTPs in Postgres (max 5 attempts, 10-min expiry).
 * Verification lives on the backend so the code can never be bypassed here.
 */

import { NextRequest, NextResponse } from "next/server";
import { backendProxy } from "@/lib/backend-proxy";
import { getAuthenticatedUserId } from "@/lib/api-auth";
import { db } from "@/lib/supabase-db";

function getAuthToken(req: NextRequest): string | null {
  const authHeader = req.headers.get("authorization");
  if (authHeader?.startsWith("Bearer ")) return authHeader.slice(7);
  return req.cookies.get("parwa_at")?.value ?? null;
}

export async function POST(request: NextRequest) {
  const token = getAuthToken(request);
  const userId = await getAuthenticatedUserId(request);
  if (!token || !userId) {
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
      if (data.status !== "verified") {
        return NextResponse.json(
          { error: "verification_unconfirmed", message: "The verification service did not confirm this email." },
          { status: 502 },
        );
      }

      // The backend OTP service is authoritative. Mirror its successful
      // result only onto this authenticated user's matching work-email row.
      const details = await db.from("user_details").select("*", {
        filter: { user_id: userId },
        single: true,
      });
      if (!details || String(details.work_email || "").toLowerCase() !== email) {
        return NextResponse.json(
          { error: "work_email_mismatch", message: "The verified email does not match your saved work email." },
          { status: 409 },
        );
      }

      let persisted = false;
      try {
        const updated = await db.from("user_details").update(
          {
            work_email_verified: true,
            updated_at: new Date().toISOString(),
          },
          { user_id: userId, work_email: email },
        );
        persisted = Array.isArray(updated) && updated.length > 0;
      } catch (persistenceError) {
        console.error("[Verification] OTP succeeded but local status mirror failed:", persistenceError);
      }

      // The backend remains authoritative. If the mirror write failed,
      // complete-step rechecks the backend status and retries persistence.
      return NextResponse.json({
        success: true,
        verified: true,
        persistence_pending: !persisted,
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
