/**
 * Client-safe redirect validation.
 * Keep this module free of Next.js server APIs so client pages can use it.
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
  "/welcome",
  "/monitoring",
  "/dashboard",
];

/** Default safe redirect target when validation fails. */
const SAFE_REDIRECT_DEFAULT = "/";

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
