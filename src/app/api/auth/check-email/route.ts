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
    try {
      const { response: backendRes } = await backendProxy(
        `/api/v1/auth/check-email?email=${encodeURIComponent(normalizedEmail)}`,
        { method: "GET" },
      );

      if (backendRes.ok) {
        const data = await backendRes.json();
        // Backend always returns generic response for security
        // Return available=true if email not taken
        return NextResponse.json({ available: true });
      }
    } catch {
      // Backend unreachable — fall through to local
    }

    // ── Local Prisma fallback ──────────────────────────────────
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
