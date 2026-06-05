import { NextRequest, NextResponse } from "next/server";
import { proxyAuthRequest, transformMeResponse } from "@/lib/backend-proxy";

/**
 * GET /api/auth/me-proxy
 * Proxies to backend: GET /api/auth/me
 *
 * This route exists so the AuthContext can verify the current user
 * via the Next.js proxy (avoids CORS issues with direct backend calls).
 * The access token is forwarded from the httpOnly cookie.
 */
export async function GET(request: NextRequest) {
  try {
    return proxyAuthRequest(request, {
      backendPath: "/api/auth/me",
      method: "GET",
      forwardAuth: true,
      transformResponse: transformMeResponse,
    });
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Me-proxy error:", message);
    return NextResponse.json(
      { status: "error", message: "Authentication check failed." },
      { status: 401 }
    );
  }
}
