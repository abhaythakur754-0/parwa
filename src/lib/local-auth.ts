/**
 * PARWA — Local Auth Fallback (sandbox / dev resilience)
 *
 * When the PARWA backend (the sole production token issuer) is unreachable
 * or not configured for the current Google OAuth client, these helpers let
 * the Next.js layer authenticate users directly:
 *
 *   1. Google id_token is verified SERVER-SIDE against Google's own
 *      tokeninfo endpoint (signature, audience, email verification, expiry)
 *      — identical checks to backend `_verify_google_token`.
 *   2. The user is upserted in the local Prisma database.
 *   3. A local HS256 session (access 15 min / refresh 7 d) is minted with
 *      `jose` and stored in the standard parwa_at / parwa_rt httpOnly
 *      cookies. lib/jwt.ts verifyToken() accepts these tokens.
 *
 * SECURITY: every path here is gated behind ENABLE_LOCAL_GOOGLE_AUTH=1.
 * Production (Render/Vercel) does NOT set it, so the backend remains the
 * sole token issuer there and none of this code executes.
 */

import { SignJWT } from "jose";
import { db } from "@/lib/db";
import { verifyToken } from "@/lib/jwt";

const LOCAL_JWT_SECRET =
  process.env.JWT_SECRET_KEY || "dev-jwt-secret-key-change-in-prod-32c";

const ACCESS_TTL_S = 15 * 60; // 15 minutes
const REFRESH_TTL_S = 7 * 24 * 60 * 60; // 7 days

export function isLocalAuthEnabled(): boolean {
  return process.env.ENABLE_LOCAL_GOOGLE_AUTH === "1";
}

function getSecretKey(): Uint8Array {
  return new TextEncoder().encode(LOCAL_JWT_SECRET);
}

/** Local user record shaped like the backend's /api/auth/me response. */
export interface LocalMeUser {
  id: string;
  email: string;
  full_name: string | null;
  phone: string | null;
  avatar_url: string | null;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  company_id: string | null;
  company_name: string | null;
  industry: string | null;
  created_at: string | null;
}

export interface LocalGoogleClaims {
  aud: string;
  email: string;
  email_verified: boolean | string;
  exp: string | number;
  sub?: string;
  name?: string;
  picture?: string;
}

/**
 * Verify a Google id_token with Google's tokeninfo endpoint.
 * Returns the claims when the token is genuinely Google-signed, issued for
 * our client, from a verified email, and not expired. Returns null otherwise.
 */
export async function verifyGoogleIdTokenLocally(
  idToken: string,
): Promise<LocalGoogleClaims | null> {
  const clientId =
    process.env.GOOGLE_CLIENT_ID || process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID;
  if (!clientId || !idToken) return null;

  try {
    const res = await fetch("https://oauth2.googleapis.com/tokeninfo", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ id_token: idToken }).toString(),
      signal: AbortSignal.timeout(10_000),
    });

    if (!res.ok) return null; // Google rejected the token (bad signature etc.)

    let claims: LocalGoogleClaims;
    try {
      claims = (await res.json()) as LocalGoogleClaims;
    } catch {
      return null;
    }

    // Audience must be OUR client id (same check as the backend)
    if (claims.aud !== clientId) return null;

    // Email must be verified by Google
    const emailVerified =
      claims.email_verified === true || claims.email_verified === "true";
    if (!emailVerified) return null;

    // Token must not be expired
    const exp = Number(claims.exp || 0);
    if (!exp || exp * 1000 < Date.now()) return null;

    return claims;
  } catch {
    return null;
  }
}

/** Upsert the locally-verified Google user in the local database. */
export async function upsertLocalGoogleUser(
  claims: LocalGoogleClaims,
): Promise<LocalMeUser | null> {
  const email = String(claims.email || "")
    .trim()
    .toLowerCase();
  if (!email) return null;

  const displayName = claims.name || email.split("@")[0];

  try {
    const user = await db.user.upsert({
      where: { email },
      update: {
        full_name: displayName,
        emailVerified: true,
        isActive: true,
      },
      create: {
        email,
        name: displayName,
        full_name: displayName,
        emailVerified: true,
        isActive: true,
        role: "user",
      },
    });

    if (!user.isActive) return null;

    return toLocalMeUser(user);
  } catch (err) {
    console.error("[local-auth] user upsert failed:", err);
    return null;
  }
}

function toLocalMeUser(user: {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  isActive: boolean;
  emailVerified: boolean;
  industry: string | null;
  createdAt: Date;
}): LocalMeUser {
  return {
    id: user.id,
    email: user.email,
    full_name: user.full_name,
    phone: null,
    avatar_url: null,
    role: user.role || "member",
    is_active: user.isActive,
    is_verified: user.emailVerified,
    company_id: null,
    company_name: null,
    industry: user.industry ?? null,
    created_at: user.createdAt ? user.createdAt.toISOString() : null,
  };
}

/** Mint a local HS256 session token (access or refresh). */
async function mintLocalToken(
  userId: string,
  email: string,
  type: "access" | "refresh",
): Promise<string> {
  const now = Math.floor(Date.now() / 1000);
  const ttl = type === "access" ? ACCESS_TTL_S : REFRESH_TTL_S;

  return new SignJWT({ email, role: "member", type })
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(userId)
    .setIssuedAt(now)
    .setExpirationTime(now + ttl)
    .setJti(crypto.randomUUID())
    .sign(getSecretKey());
}

/** Mint both local session tokens for a user. */
export async function mintLocalTokens(
  userId: string,
  email: string,
): Promise<{ accessToken: string; refreshToken: string; expiresIn: number }> {
  const [accessToken, refreshToken] = await Promise.all([
    mintLocalToken(userId, email, "access"),
    mintLocalToken(userId, email, "refresh"),
  ]);
  return { accessToken, refreshToken, expiresIn: ACCESS_TTL_S };
}

/**
 * Resolve a local session token to a user (for me/refresh fallbacks).
 * Returns null when the token is not a valid locally-issued token.
 */
export async function getLocalUserFromToken(
  token: string | null | undefined,
  expectedType: "access" | "refresh" = "access",
): Promise<LocalMeUser | null> {
  if (!token || !isLocalAuthEnabled()) return null;

  const verified = await verifyToken(token);
  if (!verified) return null;
  if (verified.payload.type && verified.payload.type !== expectedType) {
    return null;
  }

  try {
    const user = await db.user.findUnique({
      where: { id: verified.payload.sub },
    });
    if (!user || !user.isActive) return null;
    return toLocalMeUser(user);
  } catch {
    return null;
  }
}
