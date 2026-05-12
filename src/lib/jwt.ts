/**
 * PARWA — JWT Utility (Edge-compatible using jose)
 *
 * Signs and verifies JWTs for the Next.js frontend auth layer.
 * Supports both HS256 (symmetric) and RS256 (asymmetric) algorithms.
 * Algorithm is determined by NEXT_PUBLIC_JWT_ALGORITHM env var.
 *
 * HS256: Uses JWT_SECRET_KEY from environment (symmetric).
 * RS256: Uses JWT_PUBLIC_KEY (PEM or base64) for verification (asymmetric).
 *
 * Tokens include: sub (user_id), email, role, company_id, jti, iat, exp.
 */
import { SignJWT, jwtVerify, importSPKI, importPKCS8 } from "jose";
import type { CryptoKey } from "jose";

const JWT_SECRET =
  process.env.JWT_SECRET_KEY || "dev-jwt-secret-key-change-in-prod-32c";
const JWT_ACCESS_EXPIRY = "15m"; // Access token: 15 minutes
const JWT_REFRESH_EXPIRY = "7d"; // Refresh token: 7 days

/** JWT algorithm from env — defaults to HS256 for backward compatibility */
const JWT_ALGORITHM = (process.env.NEXT_PUBLIC_JWT_ALGORITHM || "HS256") as
  | "HS256"
  | "RS256";

/** JWT Key ID from env — included in token header for RS256 */
const JWT_KID = process.env.NEXT_PUBLIC_JWT_KID || "parwa-key-v1";

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

/**
 * Load an RSA private key from PEM string or base64-encoded string.
 * Used for RS256 token signing on the frontend (rare — mostly backend signs).
 */
async function loadRSAPrivateKey(): Promise<CryptoKey | null> {
  // Try PEM string first
  const pemKey = process.env.JWT_PRIVATE_KEY || "";
  if (pemKey && pemKey.includes("-----BEGIN")) {
    try {
      return await importPKCS8(pemKey, "RS256");
    } catch (e) {
      console.error("Failed to import RSA private key from PEM:", e);
      return null;
    }
  }

  // Try base64-encoded key
  const b64Key = process.env.JWT_PRIVATE_KEY_BASE64 || "";
  if (b64Key) {
    try {
      const pem = Buffer.from(b64Key, "base64").toString("utf-8");
      return await importPKCS8(pem, "RS256");
    } catch (e) {
      console.error("Failed to import RSA private key from base64:", e);
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
 * Get the JWT signing key based on configured algorithm.
 * For RS256, loads the RSA private key; for HS256, uses the shared secret.
 */
async function getSigningKey(): Promise<CryptoKey | Uint8Array> {
  if (JWT_ALGORITHM === "RS256") {
    const rsaKey = await loadRSAPrivateKey();
    if (rsaKey) return rsaKey;
    // Fallback to HS256 if RSA key not available
    console.warn("RS256 configured but no private key found — falling back to HS256 for signing");
    return getSecret();
  }
  return getSecret();
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

/**
 * Resolve the algorithm to use, falling back to HS256 if RS256 keys are unavailable.
 */
async function resolveAlgorithm(): Promise<string> {
  if (JWT_ALGORITHM === "RS256") {
    const pubKey = await loadRSAPublicKey();
    if (pubKey) return "RS256";
    return "HS256"; // Fallback
  }
  return "HS256";
}

/**
 * Build JWT protected headers with algorithm and optional kid.
 */
function buildProtectedHeader(alg: string): { alg: string; kid?: string } {
  const header: { alg: string; kid?: string } = { alg };
  if (alg === "RS256" || JWT_KID) {
    header.kid = JWT_KID;
  }
  return header;
}

/**
 * Sign a JWT access token.
 */
export async function signAccessToken(payload: JWTPayload): Promise<string> {
  const jti = crypto.randomUUID();
  const algorithm = await resolveAlgorithm();
  const signingKey = await getSigningKey();

  return new SignJWT({ ...payload, jti })
    .setProtectedHeader(buildProtectedHeader(algorithm))
    .setIssuedAt()
    .setIssuer("parwa:frontend")
    .setAudience("parwa:app")
    .setExpirationTime(JWT_ACCESS_EXPIRY)
    .sign(signingKey);
}

/**
 * Sign a JWT refresh token.
 */
export async function signRefreshToken(payload: JWTPayload): Promise<string> {
  const jti = crypto.randomUUID();
  const algorithm = await resolveAlgorithm();
  const signingKey = await getSigningKey();

  return new SignJWT({ ...payload, jti, type: "refresh" })
    .setProtectedHeader(buildProtectedHeader(algorithm))
    .setIssuedAt()
    .setIssuer("parwa:frontend")
    .setAudience("parwa:app")
    .setExpirationTime(JWT_REFRESH_EXPIRY)
    .sign(signingKey);
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
 * Returns null if invalid/expired.
 */
export async function verifyToken(
  token: string
): Promise<VerifiedToken | null> {
  try {
    const verificationKey = await getVerificationKey();
    const { payload } = await jwtVerify(token, verificationKey, {
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
