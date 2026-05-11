/**
 * PARWA Dashboard — JWT Auth Verification (C-01 Fix)
 *
 * Real JWT verification using jose. Replaces the previous security-theater
 * requireAuth() that only checked for header existence.
 *
 * Supports tokens from both:
 *   - Next.js frontend (issuer: "parwa:frontend", audience: "parwa:app")
 *   - Python backend (no issuer/audience, type: "access")
 *
 * Token sources (tried in order):
 *   1. Authorization: Bearer <token> header
 *   2. parwa_at httpOnly cookie
 */
import { jwtVerify } from "jose";
import { NextRequest, NextResponse } from "next/server";

const JWT_SECRET =
  process.env.JWT_SECRET_KEY || "dev-jwt-secret-key-change-in-prod-32c";

function getSecret(): Uint8Array {
  return new TextEncoder().encode(JWT_SECRET);
}

export interface VerifiedUser {
  sub: string;
  email: string;
  role?: string;
  company_id?: string;
  is_verified?: boolean;
  jti?: string;
  iat?: number;
  exp?: number;
  iss?: string;
  aud?: string;
  type?: string;
  plan?: string;
}

/**
 * Extract JWT token from a request.
 * Checks Authorization header first, then parwa_at cookie.
 */
function extractToken(request: NextRequest): string | null {
  // 1. Try Authorization: Bearer <token> header
  const authHeader = request.headers.get("authorization");
  if (authHeader && authHeader.startsWith("Bearer ")) {
    const token = authHeader.slice(7).trim();
    if (token) return token;
  }

  // 2. Fallback to parwa_at httpOnly cookie
  const cookieHeader = request.headers.get("cookie");
  if (cookieHeader) {
    const cookies = Object.fromEntries(
      cookieHeader.split(";").map((c) => {
        const [key, ...val] = c.trim().split("=");
        return [key, val.join("=")];
      })
    );
    const token = cookies["parwa_at"] || null;
    if (token) return token;
  }

  return null;
}

/**
 * Verify a JWT from a request using jose.
 * Accepts tokens from both the Next.js frontend and the Python backend.
 *
 * Verification strategy:
 *   - Try with strict issuer/audience first (frontend tokens)
 *   - If that fails, try with relaxed verification (backend tokens)
 *
 * Returns the decoded payload or null if invalid/expired.
 */
export async function verifyAuth(
  request: NextRequest
): Promise<VerifiedUser | null> {
  const token = extractToken(request);
  if (!token) return null;

  // Strategy 1: Verify with strict issuer/audience (frontend-issued tokens)
  try {
    const { payload } = await jwtVerify(token, getSecret(), {
      issuer: "parwa:frontend",
      audience: "parwa:app",
    });
    return payload as unknown as VerifiedUser;
  } catch {
    // Not a frontend token — try relaxed verification
  }

  // Strategy 2: Verify signature only (backend-issued tokens)
  // Backend tokens don't set issuer/audience but have type: "access"
  try {
    const { payload } = await jwtVerify(token, getSecret());
    const p = payload as unknown as VerifiedUser;
    // Reject refresh tokens — only access tokens are valid for API calls
    if (p.type === "refresh") return null;
    return p;
  } catch {
    return null;
  }
}

/**
 * Auth guard for API routes.
 * Returns null if auth succeeds (caller should proceed).
 * Returns a 401 NextResponse if auth fails (caller should return this).
 *
 * Usage:
 *   const authError = requireAuth(request);
 *   if (authError) return authError;
 *   // ... proceed with handler
 */
export async function requireAuth(
  request: NextRequest
): Promise<NextResponse | null> {
  const user = await verifyAuth(request);
  if (!user) {
    return NextResponse.json(
      { success: false, error: "Authentication required" },
      { status: 401 }
    );
  }
  return null;
}
