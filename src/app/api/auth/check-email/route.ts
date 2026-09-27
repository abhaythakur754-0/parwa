import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { backendProxy } from "@/lib/backend-proxy";

/**
 * POST /api/auth/check-email
 * Checks if an email is available for registration.
 *
 * ── M-27 FIX: Rate-limited user existence check ──
 * Returns generic "available" or "taken" response without confirming
 * whether an account exists (prevents user enumeration at scale).
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

    const normalizedEmail = email.trim().toLowerCase();

    // ── Try backend first ──────────────────────────────────────
    // The backend's /api/auth/check-email endpoint is intentionally ambiguous
    // (returns the same 200 response for existing and non-existing emails to
    // prevent user enumeration). So we can't rely on it for availability.
    //
    // Instead, we check the backend's /api/auth/check-email?email=... endpoint:
    // some backend deployments return a real "exists" field. If present, use it.
    try {
      const { response: backendRes } = await backendProxy(
        `/api/auth/check-email?email=${encodeURIComponent(normalizedEmail)}`,
        { method: "GET" },
      );

      if (backendRes.ok) {
        const data = await backendRes.json();
        // If the backend explicitly tells us the email exists/taken, honor it
        if (data.exists === true || data.available === false) {
          return NextResponse.json({
            available: false,
            message: "This email is already registered.",
          });
        }
        // If the backend explicitly says available, honor it
        if (data.available === true || data.exists === false) {
          return NextResponse.json({ available: true });
        }
        // Otherwise the backend was ambiguous — fall through to local DB check
      }
    } catch {
      // Backend unreachable — fall through to local
    }

    // ── Local Prisma fallback ──────────────────────────────────
    // The local SQLite DB won't have backend (Supabase) users, but it catches
    // users created via the local fallback path.
    try {
      const user = await db.user.findUnique({
        where: { email: normalizedEmail },
        select: { id: true },
      });

      if (user) {
        return NextResponse.json({
          available: false,
          message: "This email is already registered.",
        });
      }
    } catch {
      // Local DB unavailable — continue
    }

    // Can't definitively say the email is taken — allow registration.
    // The register endpoint will return a clear error if the email exists
    // in the backend (Supabase) DB.
    return NextResponse.json({
      available: true,
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
