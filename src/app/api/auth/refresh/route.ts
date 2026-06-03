import { NextRequest, NextResponse } from "next/server";
import { proxyAuthRequest } from "@/lib/backend-proxy";
import { setAuthCookies } from "@/lib/auth-cookies";

/**
 * POST /api/auth/refresh
 * Proxies to backend: POST /api/auth/refresh
 * Sends the refresh token from parwa_rt cookie.
 * Sets new auth cookies on success.
 */
export async function POST(request: NextRequest) {
  try {
    // Get refresh token from cookie
    const cookieHeader = request.headers.get("cookie") || "";
    let refreshToken = "";
    for (const part of cookieHeader.split(";")) {
      const trimmed = part.trim();
      if (trimmed.startsWith("parwa_rt=")) {
        refreshToken = trimmed.slice("parwa_rt=".length);
        break;
      }
    }

    if (!refreshToken) {
      return NextResponse.json(
        { status: "error", message: "No refresh token provided." },
        { status: 401 }
      );
    }

    return proxyAuthRequest(request, {
      backendPath: "/api/auth/refresh",
      method: "POST",
      body: { refresh_token: refreshToken },
      // Custom transform: backend returns TokenResponse, we need to set cookies
      transformResponse: (data: Record<string, unknown>) => {
        return data; // Will be handled below
      },
      setCookies: false, // Handle cookies manually since response format differs
    }).then(async (response) => {
      // Check if the response was successful
      try {
        const body = await response.clone().json();

        // If backend returned tokens directly (TokenResponse format)
        if (body.access_token && body.refresh_token) {
          const nextResponse = NextResponse.json({
            status: "success",
            message: "Tokens refreshed.",
          });
          setAuthCookies(nextResponse, body.access_token, body.refresh_token, {});
          return nextResponse;
        }

        // If response already has our format (status field)
        if (body._tokens) {
          const tokens = body._tokens as { access_token: string; refresh_token: string };
          const nextResponse = NextResponse.json({
            status: "success",
            message: "Tokens refreshed.",
          });
          setAuthCookies(nextResponse, tokens.access_token, tokens.refresh_token, {});
          return nextResponse;
        }

        // Fallback: just return the response as-is
        return response;
      } catch {
        return response;
      }
    });
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Refresh error:", message);
    return NextResponse.json(
      { status: "error", message: "Token refresh failed." },
      { status: 500 }
    );
  }
}
