import type { NextRequest } from "next/server";
import { verifyToken, type VerifiedToken } from "@/lib/jwt";

/** Read an access token from the standard bearer header or httpOnly cookie. */
export function getRequestAccessToken(request: NextRequest): string | null {
  const authorization = request.headers.get("authorization");
  const bearer = authorization?.match(/^Bearer\\s+(.+)$/i)?.[1]?.trim();
  return bearer || request.cookies.get("parwa_at")?.value || null;
}

/** Verify the request's bearer/cookie JWT and return its authenticated claims. */
export async function getAuthenticatedUser(
  request: NextRequest,
): Promise<VerifiedToken["payload"] | null> {
  const token = getRequestAccessToken(request);
  if (!token) return null;

  const verified = await verifyToken(token);
  return verified?.payload ?? null;
}

/** Return only the subject from a cryptographically verified access token. */
export async function getAuthenticatedUserId(
  request: NextRequest,
): Promise<string | null> {
  const user = await getAuthenticatedUser(request);
  return user?.sub ?? null;
}
