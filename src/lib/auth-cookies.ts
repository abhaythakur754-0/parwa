import 'server-only';

/**
 * SHOBH — HTTP-only Cookie Helpers
 *
 * All auth tokens should be set as httpOnly cookies to prevent XSS theft.
 * The frontend reads user data from a separate non-httpOnly cookie or from the /me endpoint.
 *
 * IMPORTANT: parwa_at and parwa_rt contain the BACKEND's JWT tokens (not
 * frontend-signed ones). This ensures the backend can verify tokens when
 * they are forwarded via me-proxy or other API proxy routes.
 */

import { NextResponse } from "next/server";

const COOKIE_OPTIONS = {
  path: "/",
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: process.env.NODE_ENV === "production" ? ("lax" as const) : ("lax" as const),
  maxAge: 15 * 60, // 15 minutes default for access token
};

const REFRESH_COOKIE_OPTIONS = {
  path: "/",
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: process.env.NODE_ENV === "production" ? ("lax" as const) : ("lax" as const),
  maxAge: 7 * 24 * 60 * 60, // 7 days for refresh token
};

/**
 * Set auth tokens on a response as httpOnly cookies.
 * Also sets a non-httpOnly user cookie so the frontend can read user info.
 *
 * @param response - The NextResponse to set cookies on
 * @param accessToken - The BACKEND's access token (JWT)
 * @param refreshToken - The BACKEND's refresh token
 * @param userData - Non-sensitive user display data for frontend
 * @param expiresIn - Access token expiry in seconds (defaults to 15 min)
 */
export function setAuthCookies(
  response: NextResponse,
  accessToken: string,
  refreshToken: string,
  userData: Record<string, unknown>,
  expiresIn?: number,
): NextResponse {
  // Access token cookie
  response.cookies.set("parwa_at", accessToken, {
    ...COOKIE_OPTIONS,
    maxAge: expiresIn || COOKIE_OPTIONS.maxAge,
  });

  // Refresh token cookie
  response.cookies.set("parwa_rt", refreshToken, REFRESH_COOKIE_OPTIONS);

  // Non-httpOnly cookie for frontend user state (no secrets, just display info)
  response.cookies.set("parwa_user", JSON.stringify(userData), {
    path: "/",
    httpOnly: false,
    secure: process.env.NODE_ENV === "production",
    sameSite: process.env.NODE_ENV === "production" ? ("lax" as const) : ("lax" as const),
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
 * Looks for the "parwa_at" cookie.
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
 * Allowed redirect path prefixes (whitelist).
 * Any redirect not matching these will be rejected.
 */
