/**
 * PARWA — HTTP-only Cookie Helpers
 *
 * All auth tokens should be set as httpOnly cookies to prevent XSS theft.
 * The frontend reads user data from a separate non-httpOnly cookie or from the /me endpoint.
 */
import { NextResponse } from "next/server";

const COOKIE_OPTIONS = {
  path: "/",
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: process.env.NODE_ENV === "production" ? ("strict" as const) : ("lax" as const),
  maxAge: 15 * 60, // 15 minutes for access token
};

const REFRESH_COOKIE_OPTIONS = {
  path: "/",
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: process.env.NODE_ENV === "production" ? ("strict" as const) : ("lax" as const),
  maxAge: 7 * 24 * 60 * 60, // 7 days for refresh token
};

/**
 * Set auth tokens on a response as httpOnly cookies.
 * Also sets a non-httpOnly user cookie so the frontend can read user info.
 */
export function setAuthCookies(
  response: NextResponse,
  accessToken: string,
  refreshToken: string,
  userData: Record<string, unknown>
): NextResponse {
  response.cookies.set("parwa_at", accessToken, COOKIE_OPTIONS);
  response.cookies.set("parwa_rt", refreshToken, REFRESH_COOKIE_OPTIONS);

  // Non-httpOnly cookie for frontend user state (no secrets, just display info)
  response.cookies.set("parwa_user", JSON.stringify(userData), {
    path: "/",
    httpOnly: false,
    secure: process.env.NODE_ENV === "production",
    sameSite: process.env.NODE_ENV === "production" ? ("strict" as const) : ("lax" as const),
    maxAge: 7 * 24 * 60 * 60,
  });

  return response;
}

/**
 * Clear all auth cookies (for logout).
 */
export function clearAuthCookies(response: NextResponse): NextResponse {
  response.cookies.set("parwa_at", "", {
    path: "/",
    httpOnly: true,
    maxAge: 0,
  });
  response.cookies.set("parwa_rt", "", {
    path: "/",
    httpOnly: true,
    maxAge: 0,
  });
  response.cookies.set("parwa_user", "", {
    path: "/",
    httpOnly: false,
    maxAge: 0,
  });
  return response;
}

/**
 * Extract the access token from cookies in a request.
 */
export function getAccessTokenFromCookies(
  request: Request
): string | null {
  const cookieHeader = request.headers.get("cookie");
  if (!cookieHeader) return null;

  const cookies = Object.fromEntries(
    cookieHeader.split(";").map((c) => {
      const [key, ...val] = c.trim().split("=");
      return [key, val.join("=")];
    })
  );

  return cookies["parwa_at"] || null;
}

/**
 * Validate a redirect URL to prevent open redirect attacks.
 * Only allows relative paths starting with /.
 */
export function isSafeRedirect(url: string): boolean {
  // Must start with / and not be a protocol-relative URL
  if (!url.startsWith("/")) return false;
  // Block protocol-relative URLs (//evil.com)
  if (url.startsWith("//")) return false;
  // Block backslash-based paths (\\evil.com)
  if (url.startsWith("\\\\")) return false;
  // Block encoded variants
  if (/^\\/.test(url)) return false;
  // Must be a valid relative path
  if (url.includes("://")) return false;
  return true;
}
