import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { verifyToken, getAccessTokenFromCookies } from "@/lib/jwt";

/**
 * GET /api/auth/me
 * Returns the currently authenticated user's profile.
 * Verifies JWT from Authorization header or httpOnly cookie.
 */
export async function GET(request: NextRequest) {
  try {
    // ── C-02 FIX: Verify real JWT instead of returning hardcoded mock ──

    // Try Authorization header first
    const authHeader = request.headers.get("authorization");
    let token: string | null = null;

    if (authHeader && authHeader.startsWith("Bearer ")) {
      token = authHeader.slice(7);
    }

    // Fall back to httpOnly cookie
    if (!token) {
      token = getAccessTokenFromCookies(request);
    }

    if (!token) {
      return NextResponse.json(
        { status: "error", message: "Authentication required." },
        { status: 401 }
      );
    }

    const verified = await verifyToken(token);
    if (!verified) {
      return NextResponse.json(
        { status: "error", message: "Token is invalid or expired." },
        { status: 401 }
      );
    }

    // Look up user from database
    const user = await db.user.findUnique({
      where: { id: verified.payload.sub },
      select: {
        id: true,
        email: true,
        full_name: true,
        company_name: true,
        industry: true,
        phone: true,
        avatar_url: true,
        is_active: true,
        is_verified: true,
        created_at: true,
      },
    });

    if (!user || !user.is_active) {
      return NextResponse.json(
        { status: "error", message: "User not found or inactive." },
        { status: 401 }
      );
    }

    return NextResponse.json({
      id: user.id,
      email: user.email,
      full_name: user.full_name,
      phone: user.phone,
      avatar_url: user.avatar_url,
      role: "member",
      is_active: user.is_active,
      is_verified: user.is_verified,
      company_id: user.company_name || null,
      company_name: user.company_name,
      industry: user.industry,
      created_at: user.created_at,
    });
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Auth me error:", message);
    return NextResponse.json(
      { status: "error", message: "An unexpected error occurred." },
      { status: 500 }
    );
  }
}
