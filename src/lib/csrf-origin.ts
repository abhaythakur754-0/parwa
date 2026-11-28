/**
 * Validate browser origin metadata for cookie-authenticated state changes.
 * Origin is preferred; Referer is used only when Origin is absent.
 */
export function isValidCookieAuthOrigin(
  requestUrl: string,
  originHeader: string | null,
  refererHeader: string | null,
): boolean {
  try {
    const expectedOrigin = new URL(requestUrl).origin;
    const sourceUrl = originHeader || refererHeader;
    if (!sourceUrl || sourceUrl === 'null') return false;
    return new URL(sourceUrl).origin === expectedOrigin;
  } catch {
    return false;
  }
}
