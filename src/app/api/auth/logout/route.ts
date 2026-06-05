import { NextRequest, NextResponse } from "next/server";
import { proxyAuthRequest } from "@/lib/backend-proxy";
import { clearAuthCookies } from "@/lib/auth-cookies";

/**
 * POST /api/auth/logout
 * Proxies to backend: POST /api/auth/logout
 * Requires Bearer token + refresh token.
 * Clears auth cookies on success.
 */
export async function POST(request: NextRequest) {
  try {
    const response = await proxyAuthRequest(request, {
      backendPath: "/api/auth/logout",
      method: "POST",
      body: {},
      clearCookies: true,
      forwardAuth: true,
    });

    // Always clear cookies on the client side, even if backend logout fails
    if (response.status === 200 || response.status === 401) {
      const cleanResponse = NextResponse.json({
        status: "success",
        message: "Logged out successfully.",
      });
      clearAuthCookies(cleanResponse);
      return cleanResponse;
    }

    return response;
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Logout error:", message);
    // Still clear cookies on error
    const response = NextResponse.json(
      { status: "success", message: "Logged out." },
      { status: 200 }
    );
    clearAuthCookies(response);
    return response;
  }
}
