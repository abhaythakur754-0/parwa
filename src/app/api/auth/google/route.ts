import { NextRequest, NextResponse } from "next/server";
import { proxyAuthRequest, transformGoogleBody, transformAuthResponse } from "@/lib/backend-proxy";

/**
 * POST /api/auth/google
 * Proxies to backend: POST /api/auth/google
 *
 * Supports two Google auth flows:
 *   1. id_token (JWT from Google One Tap) — proxied directly to backend
 *   2. access_token (from OAuth2 popup) — also proxied to backend
 *      The backend now handles both token types in _verify_google_token.
 */
export async function POST(request: NextRequest) {
  // Read body ONCE (Next.js 16 body-is-unusable fix)
  let body: Record<string, unknown>;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json(
      { status: "error", message: "Invalid request body." },
      { status: 400 }
    );
  }

  const token = body.id_token || body.access_token;

  if (!token) {
    return NextResponse.json(
      { status: "error", message: "Google token is required." },
      { status: 400 }
    );
  }

  try {
    // Proxy directly to backend — the backend's _verify_google_token
    // now handles both JWT id_tokens and access_tokens
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
