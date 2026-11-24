import 'server-only';

import { NextRequest } from "next/server";
import { verifyAuth } from "@/lib/auth";

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
    return user.sub;
  } catch {
    return null;
  }
}
