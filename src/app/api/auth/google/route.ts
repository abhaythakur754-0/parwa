import { NextRequest, NextResponse } from "next/server";
import { proxyAuthRequest, transformGoogleBody, transformAuthResponse } from "@/lib/backend-proxy";

/**
 * POST /api/auth/google
 * Proxies to backend: POST /api/auth/google
 *
 * Both frontend and backend use: { id_token }
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    return proxyAuthRequest(request, {
      backendPath: "/api/auth/google",
      method: "POST",
      body,
      transformBody: transformGoogleBody,
      transformResponse: transformAuthResponse,
      setCookies: true,
    });
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Google auth error:", message);
    return NextResponse.json(
      { status: "error", message: "Google sign-in failed. Please try again." },
      { status: 500 }
    );
  }
}
