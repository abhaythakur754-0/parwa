import 'server-only';

import { NextRequest } from "next/server";
import { verifyAuth } from "@/lib/auth";
import { backendProxy } from "@/lib/backend-proxy";

/**
 * Resolve the account identity only from a cryptographically verified access
 * token. Never accept a user id from request data, query parameters, or a
 * cookie named user_id.
 */
export async function getAuthenticatedUserId(
  request: NextRequest
): Promise<string | null> {
  try {
    const user = await verifyAuth(request);
    if (!user || typeof user.sub !== "string" || !user.sub.trim()) {
      return null;
    }

    const authHeader = request.headers.get("authorization");
    const token = authHeader?.startsWith("Bearer ")
      ? authHeader.slice(7).trim()
      : request.cookies.get("parwa_at")?.value;
    if (!token) return null;

    // Cryptographic verification alone does not check logout revocation or
    // account deactivation. Ask the backend's authoritative auth dependency
    // to confirm the token's jti and current user status before using the
    // service-role Supabase client.
    const { response } = await backendProxy("/api/auth/me", {
      method: "GET",
      authToken: token,
    });
    if (!response.ok) return null;

    const profile = await response.json().catch(() => null);
    if (
      !profile ||
      String(profile.id || "") !== user.sub ||
      profile.is_active === false
    ) {
      return null;
    }

    return user.sub;
  } catch {
    // Fail closed when the backend cannot confirm active, non-revoked identity.
    return null;
  }
}
