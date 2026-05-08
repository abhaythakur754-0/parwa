/**
 * PARWA — JWT Utility (Edge-compatible using jose)
 *
 * Signs and verifies JWTs for the Next.js frontend auth layer.
 * Uses HS256 with JWT_SECRET_KEY from environment.
 * Tokens include: sub (user_id), email, role, company_id, jti, iat, exp.
 */
import { SignJWT, jwtVerify } from "jose";

const JWT_SECRET =
  process.env.JWT_SECRET_KEY || "dev-jwt-secret-key-change-in-prod-32c";
const JWT_ACCESS_EXPIRY = "15m"; // Access token: 15 minutes
const JWT_REFRESH_EXPIRY = "7d"; // Refresh token: 7 days

function getSecret(): Uint8Array {
  return new TextEncoder().encode(JWT_SECRET);
}

export interface JWTPayload {
  sub: string; // user id
  email: string;
  role?: string;
  company_id?: string;
  is_verified?: boolean;
}

/**
 * Sign a JWT access token.
 */
export async function signAccessToken(payload: JWTPayload): Promise<string> {
  const jti = crypto.randomUUID();
  return new SignJWT({ ...payload, jti })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setIssuer("parwa:frontend")
    .setAudience("parwa:app")
    .setExpirationTime(JWT_ACCESS_EXPIRY)
    .sign(getSecret());
}

/**
 * Sign a JWT refresh token.
 */
export async function signRefreshToken(payload: JWTPayload): Promise<string> {
  const jti = crypto.randomUUID();
  return new SignJWT({ ...payload, jti, type: "refresh" })
    .setProtectedHeader({ alg: "HS256" })
    .setIssuedAt()
    .setIssuer("parwa:frontend")
    .setAudience("parwa:app")
    .setExpirationTime(JWT_REFRESH_EXPIRY)
    .sign(getSecret());
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
 * Returns null if invalid/expired.
 */
export async function verifyToken(
  token: string
): Promise<VerifiedToken | null> {
  try {
    const { payload } = await jwtVerify(token, getSecret(), {
      issuer: "parwa:frontend",
      audience: "parwa:app",
    });
    return { payload: payload as VerifiedToken["payload"] };
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
 * Timing-safe string comparison for OTP verification.
 * Prevents timing attacks that can leak OTP values character by character.
 */
export function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) {
    // Still do a constant-time comparison to avoid leaking length info
    return crypto.timingSafeEqual(
      Buffer.from(a),
      Buffer.from(b.padEnd(a.length, "0").slice(0, a.length))
    ) && false;
  }
  return crypto.timingSafeEqual(Buffer.from(a), Buffer.from(b));
}
