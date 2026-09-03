/**
 * PARWA — JWT Utility (Edge-compatible using jose)
 *
 * VERIFIES JWTs for the Next.js frontend auth layer. The frontend never
 * signs tokens — the PARWA backend is the sole issuer (the old frontend
 * signing functions caused the historic dual-JWT auth bug and were removed).
 * Supports both HS256 (symmetric) and RS256 (asymmetric) algorithms.
 * Algorithm is determined by NEXT_PUBLIC_JWT_ALGORITHM env var.
 *
 * HS256: Uses JWT_SECRET_KEY from environment (symmetric).
 * RS256: Uses JWT_PUBLIC_KEY (PEM or base64) for verification (asymmetric).
 *
 * Tokens include: sub (user_id), email, role, company_id, jti, iat, exp.
 */
import { jwtVerify, importSPKI } from "jose";
import type { CryptoKey } from "jose";
import type { NextRequest } from "next/server";

const JWT_SECRET =
  process.env.JWT_SECRET_KEY || "dev-jwt-secret-key-change-in-prod-32c";

/** JWT algorithm from env — defaults to HS256 for backward compatibility */
const JWT_ALGORITHM = (process.env.NEXT_PUBLIC_JWT_ALGORITHM || "HS256") as
  | "HS256"
  | "RS256";

function getSecret(): Uint8Array {
  return new TextEncoder().encode(JWT_SECRET);
}

/**
 * Load an RSA public key from PEM string or base64-encoded string.
 * Used for RS256 token verification on the frontend.
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

export interface JWTPayload {
  sub: string; // user id
  email: string;
  role?: string;
  company_id?: string;
  is_verified?: boolean;
}

/**
 * Get the JWT verification key(s) based on configured algorithm.
 * For RS256, loads the RSA public key; for HS256, uses the shared secret.
 */
async function getVerificationKey(): Promise<CryptoKey | Uint8Array> {
  if (JWT_ALGORITHM === "RS256") {
    const rsaKey = await loadRSAPublicKey();
    if (rsaKey) return rsaKey;
    // Fallback to HS256 if RSA key not available
    console.warn("RS256 configured but no public key found — falling back to HS256 for verification");
    return getSecret();
  }
  return getSecret();
}

export interface VerifiedToken {
  payload: JWTPayload & {
    jti: string;
    iat: number;
    exp: number;
    iss: string;
    aud: string;
    type?: string;
  };
}

/**
 * Verify a JWT token and return the decoded payload.
 * Supports both HS256 and RS256 tokens.
 *
 * IMPORTANT: Does NOT enforce issuer/audience claims so that tokens issued
 * by the PARWA backend (which doesn't set iss/aud) are accepted. The
 * backend is the sole token issuer — the frontend only verifies.
 * Returns null if invalid/expired.
 */
export async function verifyToken(
  token: string
): Promise<VerifiedToken | null> {
  try {
    const verificationKey = await getVerificationKey();
    // No issuer/audience check — backend tokens don't carry these claims.
    // Signature + expiry verification is sufficient for frontend route protection.
    const { payload } = await jwtVerify(token, verificationKey);
    return { payload: payload as unknown as VerifiedToken["payload"] };
  } catch {
    return null;
  }
}

/**
 * Validate password complexity.
 * Requires: 8+ chars, at least 1 uppercase, 1 lowercase, 1 digit, 1 special char.
 */
export function validatePasswordStrength(
  password: string
): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (password.length < 8) {
    errors.push("Password must be at least 8 characters long.");
  }
  if (!/[A-Z]/.test(password)) {
    errors.push("Password must contain at least one uppercase letter.");
  }
  if (!/[a-z]/.test(password)) {
    errors.push("Password must contain at least one lowercase letter.");
  }
  if (!/[0-9]/.test(password)) {
    errors.push("Password must contain at least one number.");
  }
  if (!/[^A-Za-z0-9]/.test(password)) {
    errors.push("Password must contain at least one special character (!@#$%^&* etc.).");
  }

  return { valid: errors.length === 0, errors };
}

/**
 * Extract the access token from httpOnly cookies in a NextRequest.
 * Looks for the "parwa_at" cookie.
 * Returns null if not found.
 */
export function getAccessTokenFromCookies(request: NextRequest): string | null {
  const token = request.cookies.get("parwa_at")?.value;
  return token || null;
}

/**
 * Timing-safe string comparison for OTP verification.
 * Prevents timing attacks that can leak OTP values character by character.
 */
export function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) {
    // Still do a constant-time comparison to avoid leaking length info
    return (crypto as any).timingSafeEqual(
      Buffer.from(a),
      Buffer.from(b.padEnd(a.length, "0").slice(0, a.length))
    ) && false;
  }
  return (crypto as any).timingSafeEqual(Buffer.from(a), Buffer.from(b));
}
