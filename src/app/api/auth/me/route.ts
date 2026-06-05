import { NextRequest, NextResponse } from "next/server";
import { proxyAuthRequest, transformMeResponse } from "@/lib/backend-proxy";

/**
 * GET /api/auth/me
 * Proxies to backend: GET /api/auth/me
 * Forwards the Bearer token from the parwa_at cookie.
 */
export async function GET(request: NextRequest) {
  try {
    return proxyAuthRequest(request, {
      backendPath: "/api/auth/me",
      method: "GET",
      transformResponse: transformMeResponse,
      forwardAuth: true,
    });
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Auth me error:", message);
    return NextResponse.json(
      { status: "error", message: "An unexpected error occurred." },
      { status: 500 }
    );
  }
}
