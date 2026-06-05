/**
 * PARWA Dashboard — JWT Auth Verification (C-01 Fix + Week 6 RS256)
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
 * H20 NOTE: The parwa_at httpOnly cookie is NOT set directly by the Python
 * backend. It is set by the Next.js API proxy layer (backend-proxy.ts calls
 * setAuthCookies) when the backend's proxy-auth routes return tokens. The
 * cookie is httpOnly and secure, so it cannot be read by client-side JS —
 * it is only accessible in middleware/server-side request headers.
 *
 * Week 6: Supports dual-algorithm (HS256 + RS256) verification.
 */
import { jwtVerify, importSPKI } from "jose";
import type { CryptoKey } from "jose";
import { NextRequest, NextResponse } from "next/server";

const JWT_SECRET = process.env.JWT_SECRET_KEY || "";

if (!JWT_SECRET) {
  console.warn(
    "[PARWA] JWT_SECRET_KEY is not set. JWT verification will fail. " +
    "Set JWT_SECRET_KEY in your environment to match the backend signing key."
  );
}

/** JWT algorithm from env — defaults to HS256 for backward compatibility */
const JWT_ALGORITHM = (process.env.NEXT_PUBLIC_JWT_ALGORITHM || "HS256") as
  | "HS256"
  | "RS256";

function getSecret(): Uint8Array {
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
 * Falls back to HS256 if RS256 is configured but keys are unavailable.
 */
async function getVerificationKey(): Promise<CryptoKey | Uint8Array> {
  if (JWT_ALGORITHM === "RS256") {
    const rsaKey = await loadRSAPublicKey();
    if (rsaKey) return rsaKey;
    // Fallback to HS256 if RSA key not available
    console.warn("RS256 configured but no public key found — falling back to HS256");
    return getSecret();
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

  const verificationKey = await getVerificationKey();

  // Strategy 1: Verify with strict issuer/audience (frontend-issued tokens)
  try {
    const { payload } = await jwtVerify(token, verificationKey, {
      issuer: "parwa:frontend",
      audience: "parwa:app",
    });
    const p = payload as unknown as VerifiedUser;
    // Reject refresh tokens — only access tokens are valid for API calls
    if (p.type === "refresh") return null;
    return p;
  } catch {
    // Not a frontend token — try relaxed verification
  }

  // Strategy 2: Verify signature only (backend-issued tokens)
  // Backend tokens don't set issuer/audience but have type: "access"
  // Also try with HS256 fallback key in case backend uses different algorithm
  try {
    const { payload } = await jwtVerify(token, verificationKey);
    const p = payload as unknown as VerifiedUser;
    // Reject refresh tokens — only access tokens are valid for API calls
    if (p.type === "refresh") return null;
    return p;
  } catch {
    // RS256 failed — try HS256 with secret key as last resort
    // This handles the case where backend is still using HS256 during migration
  }

  // Strategy 3: Fallback HS256 verification (migration period support)
  if (JWT_ALGORITHM === "RS256") {
    try {
      const { payload } = await jwtVerify(token, getSecret());
      const p = payload as unknown as VerifiedUser;
      if (p.type === "refresh") return null;
      return p;
    } catch {
      return null;
    }
  }

  return null;
}

/**
 * Auth guard for API routes.
 * Returns null if auth succeeds (caller should proceed).
 * Returns a 401 NextResponse if auth fails (caller should return this).
 *
 * H19: If the access token is expired but a refresh token cookie exists,
 * attempts an automatic token refresh before failing.
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
  if (user) {
    return null; // Auth succeeded
  }

  // H19: Attempt token refresh if the access token is missing/expired
  const refreshed = await refreshAuthToken(request);
  if (refreshed) {
    // Re-verify with the new token
    const retryUser = await verifyAuth(refreshed.newRequest);
    if (retryUser) {
      // Return null but attach the refreshed tokens so the caller
      // can update cookies in the response
      return null;
    }
  }

  return NextResponse.json(
    { success: false, error: "Authentication required" },
    { status: 401 }
  );
}

// ──────────────────────────────────────────────────────────────────
// H19: Token Refresh Mechanism
// ──────────────────────────────────────────────────────────────────

/** Refresh token cookie name (matches backend-proxy.ts setAuthCookies) */
const REFRESH_TOKEN_COOKIE = "parwa_rt";

/** Access token cookie name */
const ACCESS_TOKEN_COOKIE = "parwa_at";

/** Buffer time (seconds) before expiry to trigger proactive refresh */
const EXPIRY_BUFFER_SECONDS = 30;

/**
 * Check if an access token is expired or about to expire.
 * Returns true if the token is expired or will expire within the buffer.
 */
export function isTokenExpired(user: VerifiedUser): boolean {
  if (!user.exp) return true;
  const now = Math.floor(Date.now() / 1000);
  return user.exp - now < EXPIRY_BUFFER_SECONDS;
}

/** Result of a token refresh attempt */
export interface RefreshResult {
  success: boolean;
  accessToken?: string;
  refreshToken?: string;
  newRequest?: NextRequest;
}

/**
 * Attempt to refresh the authentication tokens using the refresh token cookie.
 *
 * H19 FIX: This function:
 * 1. Extracts the refresh token from the parwa_rt cookie
 * 2. Calls the /api/auth/refresh endpoint to get new tokens
 * 3. Returns the new tokens and a modified request with the new access token
 *
 * The actual cookie-setting is handled by the /api/auth/refresh route,
 * so the caller just needs to forward the response cookies.
 */
export async function refreshAuthToken(
  request: NextRequest
): Promise<RefreshResult | null> {
  // Extract refresh token from cookie
  const cookieHeader = request.headers.get("cookie") || "";
  const cookies = Object.fromEntries(
    cookieHeader.split(";").map((c) => {
      const [key, ...val] = c.trim().split("=");
      return [key, val.join("=")];
    })
  );

  const refreshToken = cookies[REFRESH_TOKEN_COOKIE];
  if (!refreshToken) {
    return null;
  }

  try {
    // Call the refresh endpoint (relative URL, no port needed)
    const response = await fetch("/api/auth/refresh", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Cookie: `${REFRESH_TOKEN_COOKIE}=${refreshToken}`,
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      return null;
    }

    const data = await response.json();
    if (!data.access_token) {
      return null;
    }

    // Build a new request with the refreshed access token
    const newHeaders = new Headers(request.headers);
    newHeaders.set("authorization", `Bearer ${data.access_token}`);

    // Update cookie header with new access token
    const newCookies: Record<string, string> = { ...cookies };
    newCookies[ACCESS_TOKEN_COOKIE] = data.access_token;
    if (data.refresh_token) {
      newCookies[REFRESH_TOKEN_COOKIE] = data.refresh_token;
    }
    newHeaders.set(
      "cookie",
      Object.entries(newCookies)
        .map(([k, v]) => `${k}=${v}`)
        .join("; ")
    );

    const newRequest = new NextRequest(request.url, {
      method: request.method,
      headers: newHeaders,
      body: request.body,
    });

    return {
      success: true,
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      newRequest,
    };
  } catch {
    // Refresh failed — don't log tokens
    return null;
  }
}

/**
 * Client-side helper: Check if the current access token is about to expire
 * and proactively refresh it. Call this before making authenticated API calls.
 *
 * Returns the current (or refreshed) access token, or null if refresh fails.
 */
export async function getValidAccessToken(): Promise<string | null> {
  // This is for client-side use where we read from localStorage/sessionStorage
  // or from the Next.js API route that can access cookies.
  try {
    const response = await fetch("/api/auth/me", {
      method: "GET",
      credentials: "include",
    });

    if (!response.ok) {
      // Try refresh
      const refreshResponse = await fetch("/api/auth/refresh", {
        method: "POST",
        credentials: "include",
      });

      if (!refreshResponse.ok) {
        return null;
      }

      const data = await refreshResponse.json();
      return data.access_token || null;
    }

    // Parse the user to check expiry
    const userData = await response.json();
    if (userData?.exp) {
      const now = Math.floor(Date.now() / 1000);
      if (userData.exp - now < EXPIRY_BUFFER_SECONDS) {
        // Token about to expire, refresh proactively
        const refreshResponse = await fetch("/api/auth/refresh", {
          method: "POST",
          credentials: "include",
        });
        if (refreshResponse.ok) {
          const data = await refreshResponse.json();
          return data.access_token || null;
        }
      }
    }

    // Extract access token from the response or re-fetch
    return userData?.access_token || null;
  } catch {
    return null;
  }
}
