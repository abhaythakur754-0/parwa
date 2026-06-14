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
 * Allowed redirect path prefixes (whitelist).
 * Any redirect not matching these will be rejected.
 */
const ALLOWED_REDIRECT_PREFIXES = [
  "/models",
  "/tickets",
  "/settings",
  "/billing",
  "/analytics",
  "/channels",
  "/knowledge",
  "/jarvis",
  "/agents",
  "/profile",
  "/onboarding",
  "/monitoring",
];

/** Default safe redirect target when validation fails. */
const SAFE_REDIRECT_DEFAULT = "/models";

/**
 * Decode a URL string iteratively until it stops changing.
 * This prevents double-encoding attacks like %252F -> %2F -> /
 */
function fullyDecodeUri(str: string): string {
  let prev = "";
  let current = str;
  // Decode up to 5 rounds to catch multi-level encoding
  for (let i = 0; i < 5; i++) {
    prev = current;
    try {
      current = decodeURIComponent(current);
    } catch {
      // Invalid percent-encoding — stop decoding
      break;
    }
    if (current === prev) break;
  }
  return current;
}

/**
 * Validate a redirect URL to prevent open redirect attacks.
 *
 * Defense layers:
 * 1. Fully decode the URL to catch double/triple encoding (e.g., %252F)
 * 2. Only allows relative paths starting with /
 * 3. Blocks protocol-relative URLs (//evil.com)
 * 4. Blocks backslash-based paths (\\evil.com)
 * 5. Blocks any protocol scheme (://)
 * 6. Validates against a whitelist of allowed path prefixes
 */
export function isSafeRedirect(url: string): boolean {
  if (!url || typeof url !== "string") return false;

  // Step 1: Fully decode to catch multi-level encoding attacks
  const decoded = fullyDecodeUri(url);

  // Step 2: Must start with / after decoding
  if (!decoded.startsWith("/")) return false;

  // Step 3: Block protocol-relative URLs (//evil.com)
  if (decoded.startsWith("//")) return false;

  // Step 4: Block backslash-based paths (\\evil.com)
  if (decoded.startsWith("\\\\")) return false;

  // Step 5: Block encoded backslash variants
  if (/^\\/.test(decoded)) return false;

  // Step 6: Block any protocol scheme (http://, https://, javascript:, data:)
  if (decoded.includes("://")) return false;

  // Step 7: Block javascript: and data: URI schemes (even without ://)
  if (/^\s*(javascript|data|vbscript)\s*:/i.test(decoded)) return false;

  // Step 8: Validate against whitelist of allowed path prefixes
  // This is the final defense — even if all encoding tricks pass,
  // the path must start with a known safe prefix.
  const pathOnly = decoded.split("?")[0].split("#")[0];
  const isAllowed = ALLOWED_REDIRECT_PREFIXES.some(
    (prefix) => pathOnly === prefix || pathOnly.startsWith(prefix + "/")
  );

  return isAllowed;
}

/**
 * Get a safe redirect URL.
 *
 * Returns the original URL if it passes isSafeRedirect(),
 * otherwise returns the SAFE_REDIRECT_DEFAULT.
 *
 * Usage:
 *   const redirectTo = getSafeRedirect(searchParams.get('redirect'));
 *   router.push(redirectTo);
 */
export function getSafeRedirect(url: string | null | undefined): string {
  if (!url) return SAFE_REDIRECT_DEFAULT;
  if (isSafeRedirect(url)) return url;
  return SAFE_REDIRECT_DEFAULT;
}
