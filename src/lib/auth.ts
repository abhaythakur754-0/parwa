/**
 * Shared Next.js API authentication guard.
 *
 * Token signature, expiry, subject, and configured algorithm are verified by
 * the single verifier in jwt.ts; refresh tokens are never accepted here.
 */
import { NextRequest, NextResponse } from "next/server";
import { verifyToken } from "@/lib/jwt";

export interface VerifiedUser {
  sub: string;
  email?: string;
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

function extractToken(request: NextRequest): string | null {
  const authorization = request.headers.get("authorization");
  const bearer = authorization?.match(/^Bearer\\s+(.+)$/i)?.[1]?.trim();
  if (bearer) return bearer;

  return request.cookies.get("parwa_at")?.value ?? null;
}

export async function verifyAuth(
  request: NextRequest,
): Promise<VerifiedUser | null> {
  const token = extractToken(request);
  if (!token) return null;

  const verified = await verifyToken(token);
  return (verified?.payload as VerifiedUser | undefined) ?? null;
}

/** Return null when auth succeeds, otherwise a standard 401 response. */
export async function requireAuth(
  request: NextRequest,
): Promise<NextResponse | null> {
  const user = await verifyAuth(request);
  if (!user) {
    return NextResponse.json(
      { success: false, error: "Authentication required" },
      { status: 401 },
    );
  }
  return null;
}
