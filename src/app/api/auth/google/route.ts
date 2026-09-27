/**
 * PARWA Google OAuth API Route
 *
 * Forwards the Google id_token to the backend (sole token issuer), which
 * verifies it with Google and returns PARWA JWT tokens. The frontend never
 * mints its own tokens — this was the root cause of the dual-JWT auth bug.
 *
 * If the backend is unreachable, returns 503 (no local fallback that
 * would create divergent auth state).
 */

import { NextRequest, NextResponse } from "next/server";
import { setAuthCookies } from "@/lib/auth-cookies";
import { backendProxy } from "@/lib/backend-proxy";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { id_token } = body;

    if (!id_token || typeof id_token !== "string") {
      return NextResponse.json(
        { status: "error", message: "Google ID token is required." },
        { status: 400 }
      );
    }

    // ── Backend is the sole token issuer ──────────────────────
    try {
      const { response: backendRes } = await backendProxy("/api/auth/google", {
        method: "POST",
        body: JSON.stringify({ id_token }),
      });

      if (backendRes.ok) {
        let data: Record<string, unknown>;
        try {
          data = await backendRes.json();
        } catch {
          console.error("[google-auth] Backend returned 200 but non-JSON body");
          return NextResponse.json(
            { status: "error", message: "Google sign-in service unavailable. Please try again." },
            { status: 503 }
          );
        }

        const authData = (data.data || data) as Record<string, unknown>;
        const userObj = (authData.user || data.user) as Record<string, unknown> | undefined;
        const tokensObj = (authData.tokens || data.tokens) as Record<string, unknown> | undefined;
        const isNewUser = (authData.is_new_user ?? data.is_new_user ?? true) as boolean;

        if (userObj && tokensObj) {
          const userData = {
            id: userObj.id,
            email: userObj.email,
            fullName: userObj.full_name || userObj.name,
            isVerified: userObj.is_verified ?? true,
            industry: userObj.industry,
            companyName: userObj.company_name,
          };

          const response = NextResponse.json({
            status: "success",
            is_new_user: isNewUser,
            user: userData,
          });

          setAuthCookies(
            response,
            String(tokensObj.access_token),
            String(tokensObj.refresh_token),
            userData,
            Number(tokensObj.expires_in) || undefined,
          );

          return response;
        }

        console.error("[google-auth] Backend returned 200 but unexpected format");
        return NextResponse.json(
          { status: "error", message: "Google sign-in service unavailable. Please try again." },
          { status: 503 }
        );
      } else {
        // Backend returned an error
        let errorData: Record<string, unknown> = {};
        try {
          const text = await backendRes.text();
          try {
            errorData = JSON.parse(text);
          } catch {
            errorData = { error: { message: text } };
          }
        } catch {
          // Can't read response body
        }

        const errorWrapper = errorData.error as Record<string, unknown> | undefined;
        const message = String(
          errorWrapper?.message ||
          errorData.detail ||
          errorData.message ||
          ""
        );

        if (backendRes.status === 401 || backendRes.status === 403) {
          return NextResponse.json(
            { status: "error", message: message || "Google sign-in failed. Please try again." },
            { status: backendRes.status }
          );
        }

        console.error("[google-auth] Backend returned", backendRes.status);
        return NextResponse.json(
          { status: "error", message: "Google sign-in service unavailable. Please try again." },
          { status: 503 }
        );
      }
    } catch {
      console.error("[google-auth] Backend unreachable");
      return NextResponse.json(
        { status: "error", message: "Google sign-in service unavailable. Please try again." },
        { status: 503 }
      );
    }
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
