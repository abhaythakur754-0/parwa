import 'server-only';

/**
 * SHOBH Dashboard — JWT Auth Verification (C-01 Fix + Week 6 RS256)
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
 *
 * Week 6: Supports dual-algorithm (HS256 + RS256) verification.
 */
import { jwtVerify, importSPKI } from "jose";
import type { CryptoKey } from "jose";
import { NextRequest, NextResponse } from "next/server";

const JWT_SECRET = process.env.JWT_SECRET_KEY;

/** JWT algorithm from env — defaults to HS256 for backward compatibility */
const JWT_ALGORITHM = (process.env.NEXT_PUBLIC_JWT_ALGORITHM || "HS256") as
  | "HS256"
  | "RS256";

function getSecret(): Uint8Array {
  if (!JWT_SECRET) throw new Error("JWT_SECRET_KEY is not configured");
  return new TextEncoder().encode(JWT_SECRET);
}

/**
 * Load an RSA public key from PEM string or base64-encoded string.
 * Used for RS256 token verification.
 */
async function loadRSAPublicKey(): Promise<CryptoKey | null> {
  // Try PEM string first
  const pemKey = process.env.JWT_PUBLIC_KEY || "";
  if (pemKey && pemKey.includes("-----BEGIN")) {
    try {
      return await importSPKI(pemKey, "RS256");
    } catch (e) {
      console.error("Failed to import RSA public key from PEM:", e);
      return null;
    }
  }

  // Try base64-encoded key
  const b64Key = process.env.JWT_PUBLIC_KEY_BASE64 || "";
  if (b64Key) {
    try {
      const pem = Buffer.from(b64Key, "base64").toString("utf-8");
      return await importSPKI(pem, "RS256");
    } catch (e) {
      console.error("Failed to import RSA public key from base64:", e);
      return null;
    }
  }

  return null;
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
 * Get the verification key based on algorithm configuration.
 * For RS256, loads the RSA public key; for HS256, uses the shared secret.
 * Fails closed when the configured verification key is unavailable.
 */
async function getVerificationKey(): Promise<CryptoKey | Uint8Array> {
  if (JWT_ALGORITHM === "RS256") {
    const rsaKey = await loadRSAPublicKey();
    if (rsaKey) return rsaKey;
    throw new Error("RS256 is configured but JWT_PUBLIC_KEY is not configured");
  }
  return getSecret();
}

/**
 * Verify a JWT from a request using jose.
 * Accepts tokens from both the Next.js frontend and the Python backend.
 * Supports both HS256 and RS256 algorithms.
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

  let verificationKey: CryptoKey | Uint8Array;
  try {
    verificationKey = await getVerificationKey();
  } catch {
    return null;
  }

  // Strategy 1: Verify with strict issuer/audience (frontend-issued tokens)
  try {
    const { payload } = await jwtVerify(token, verificationKey, {
      issuer: "parwa:frontend",
      audience: "parwa:app",
      algorithms: [JWT_ALGORITHM],
    });
    const p = payload as unknown as VerifiedUser;
    // Require an identity and explicit expiry. A correctly signed token
    // without exp must not become a non-expiring session.
    if (
      typeof p.sub !== "string" ||
      !p.sub.trim() ||
      typeof p.exp !== "number" ||
      typeof p.jti !== "string" ||
      !p.jti.trim() ||
      p.type !== "access"
    ) return null;
    return p;
  } catch {
    // Not a frontend token — try relaxed verification
  }

  // Strategy 2: Verify signature only (backend-issued tokens)
  // Backend tokens don't set issuer/audience but have type: "access"
  // Backend tokens omit issuer/audience; the signature and expiry remain mandatory.
  try {
    const { payload } = await jwtVerify(token, verificationKey, {
      algorithms: [JWT_ALGORITHM],
    });
    const p = payload as unknown as VerifiedUser;
    if (
      typeof p.sub !== "string" ||
      !p.sub.trim() ||
      typeof p.exp !== "number" ||
      typeof p.jti !== "string" ||
      !p.jti.trim() ||
      p.type !== "access"
    ) return null;
    return p;
  } catch {
  }

  return null;
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
