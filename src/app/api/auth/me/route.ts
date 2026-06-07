import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { verifyToken, getAccessTokenFromCookies } from "@/lib/jwt";
import { getBackendUrl } from "@/lib/backend-url";

/**
 * GET /api/auth/me
 * Returns the currently authenticated user's profile.
 *
 * Strategy:
 * 1. First try to forward the token to the backend's /api/auth/me
 *    (works when parwa_at contains a backend-issued JWT)
 * 2. If backend is unreachable, verify the frontend-signed JWT locally
 *    and look up user via Prisma (dev fallback only)
 */
export async function GET(request: NextRequest) {
  try {
    // Extract token from cookie or Authorization header
    const authHeader = request.headers.get("authorization");
    let token: string | null = null;

    if (authHeader && authHeader.startsWith("Bearer ")) {
      token = authHeader.slice(7);
    }

    if (!token) {
      token = getAccessTokenFromCookies(request);
    }

    if (!token) {
      return NextResponse.json(
        { status: "error", message: "Authentication required." },
        { status: 401 }
      );
    }

    // ── Try backend first ──────────────────────────────────────
    try {
      const backendUrl = getBackendUrl();
      // Dynamic origin — matches whatever deployment we're on
      const origin = process.env.FRONTEND_URL
        || (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : '')
        || (process.env.NODE_ENV === 'production' ? 'https://parwa.ai' : 'http://localhost:3000');
      const res = await fetch(`${backendUrl}/api/auth/me`, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
          "Origin": origin,
        },
        signal: AbortSignal.timeout(8000),
      });

      if (res.ok) {
        const data = await res.json();
        // Normalize backend response to frontend format
        return NextResponse.json({
          id: data.id,
          email: data.email,
          full_name: data.full_name,
          phone: data.phone,
          avatar_url: data.avatar_url,
          role: data.role,
          is_active: data.is_active,
          is_verified: data.is_verified,
          company_id: data.company_id,
          company_name: data.company_name,
          industry: data.industry,
          created_at: data.created_at,
        });
      }

      // Backend returned 401 — token is genuinely invalid
      if (res.status === 401) {
        return NextResponse.json(
          { status: "error", message: "Token is invalid or expired." },
          { status: 401 }
        );
      }

      // Other errors — fall through to local verification
    } catch {
      // Backend unreachable — fall through to local verification
    }

    // ── Local fallback (dev only) ──────────────────────────────
    const verified = await verifyToken(token);
    if (!verified) {
      return NextResponse.json(
        { status: "error", message: "Token is invalid or expired." },
        { status: 401 }
      );
    }

    // Look up user from local database
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
