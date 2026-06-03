import { NextRequest, NextResponse } from "next/server";
import { proxyAuthRequest, transformLoginBody, transformAuthResponse } from "@/lib/backend-proxy";

/**
 * POST /api/auth/login
 * Proxies to backend: POST /api/auth/login
 *
 * Both frontend and backend use: { email, password }
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    return proxyAuthRequest(request, {
      backendPath: "/api/auth/login",
      method: "POST",
      body,
      transformBody: transformLoginBody,
      transformResponse: transformAuthResponse,
      setCookies: true,
    });
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Login error:", message);
    return NextResponse.json(
      { status: "error", message: "An unexpected error occurred. Please try again." },
      { status: 500 }
    );
  }
}
