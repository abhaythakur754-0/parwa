/**
 * PARWA Google OAuth API Route
 *
 * Handles Google Sign-In by:
 * 1. Forwarding the Google id_token to the backend (which verifies it and creates/finds user)
 * 2. Storing the backend's JWT tokens in httpOnly cookies
 * 3. Returning user data to the frontend
 *
 * If the backend is unreachable, falls back to:
 * - Verifying the Google token ourselves via Google's tokeninfo endpoint
 * - Creating a temporary in-memory user session (no DB required)
 * - Signing our own JWT tokens
 */

import { NextRequest, NextResponse } from "next/server";
import { signAccessToken, signRefreshToken } from "@/lib/jwt";
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

    // ── Step 1: Forward the actual id_token to the backend ──────
    // The backend will verify the token with Google and create/find the user.
    try {
      const { response: backendRes } = await backendProxy("/api/auth/google", {
        method: "POST",
        body: JSON.stringify({ id_token }),
      });

      if (backendRes.ok) {
        // Safely parse JSON — the backend should always return JSON,
        // but we guard against non-JSON responses (e.g. from a proxy/gateway)
        let data: Record<string, unknown>;
        try {
          data = await backendRes.json();
        } catch (parseErr) {
          console.warn("[google-auth] Backend returned 200 but non-JSON body — falling back to local");
          // Fall through to local fallback below
          data = {} as Record<string, unknown>;
        }

        // Backend returns AuthResponse: { user, tokens, is_new_user }
        // Some backend versions nest it under data, some return it flat
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

          // Store BACKEND's tokens in cookies — the backend can verify these
          setAuthCookies(
            response,
            String(tokensObj.access_token),
            String(tokensObj.refresh_token),
            userData,
            Number(tokensObj.expires_in) || undefined,
          );

          return response;
        }

        // Backend returned 200 but unexpected format — log and fall through
        console.warn("[google-auth] Backend returned 200 but unexpected format:", JSON.stringify(data).slice(0, 200));
      } else {
        // Backend returned an error — safely parse the error body
        let errorData: Record<string, unknown> = {};
        try {
          const text = await backendRes.text();
          try {
            errorData = JSON.parse(text);
          } catch {
            // Backend returned plain text error — wrap it
            errorData = { error: { message: text } };
          }
        } catch {
          // Can't read response body at all
        }

        // Extract error message from backend's structured error format:
        // {"error": {"code": "...", "message": "...", "details": ...}}
        const errorWrapper = errorData.error as Record<string, unknown> | undefined;
        const message = String(
          errorWrapper?.message ||
          errorData.detail ||
          errorData.message ||
          ""
        );

        // Auth errors (invalid token, banned user, etc.) — don't fall through, return the error
        if (backendRes.status === 401 || backendRes.status === 403) {
          return NextResponse.json(
            { status: "error", message: message || "Google sign-in failed. Please try again." },
            { status: backendRes.status }
          );
        }

        // Other errors (500, 502, 503) — fall through to local fallback
        console.warn("[google-auth] Backend returned", backendRes.status, message.slice(0, 100), "— falling back to local");
      }
    } catch (backendError) {
      console.warn("[google-auth] Backend unreachable — falling back to local:", backendError instanceof Error ? backendError.message : String(backendError));
    }

    // ── Step 2: Local fallback — verify Google token ourselves ──
    // We verify the token with Google's tokeninfo endpoint, then
    // create a JWT session without needing a database.
    const googleRes = await fetch(
      `https://oauth2.googleapis.com/tokeninfo?id_token=${encodeURIComponent(id_token)}`
    );

    if (!googleRes.ok) {
      // Try to extract a helpful error message from Google's response
      let googleErrorMsg = "Google token verification failed. Please try again.";
      try {
        const text = await googleRes.text();
        try {
          const errData = JSON.parse(text);
          googleErrorMsg = errData.error_description || errData.error || googleErrorMsg;
        } catch {
          // Non-JSON response from Google — use default message
          if (text) googleErrorMsg = text.slice(0, 200);
        }
      } catch {
        // Can't read response body
      }
      return NextResponse.json(
        { status: "error", message: googleErrorMsg },
        { status: 401 }
      );
    }

    // Safely parse Google's JSON response
    let googleUser: Record<string, unknown>;
    try {
      googleUser = await googleRes.json();
    } catch {
      return NextResponse.json(
        { status: "error", message: "Failed to parse Google's response. Please try again." },
        { status: 502 }
      );
    }

    const gEmail = String(googleUser.email || "");
    const gEmailVerified = googleUser.email_verified === true;
    const gName = String(googleUser.name || googleUser.given_name || "");
    const gSub = String(googleUser.sub || "");

    if (!gEmail) {
      return NextResponse.json(
        { status: "error", message: "Could not get email from Google account." },
        { status: 400 }
      );
    }

    if (!gEmailVerified) {
      return NextResponse.json(
        { status: "error", message: "Please verify your email with Google first." },
        { status: 403 }
      );
    }

    const email = gEmail.trim().toLowerCase();
    const fullName = gName || email.split("@")[0];

    // Create a user session directly — no DB needed for Google-authenticated users
    // The Google token itself is proof of identity
    const userData = {
      id: `google_${gSub || email.replace(/[^a-zA-Z0-9]/g, "_")}`,
      email,
      fullName,
      isVerified: true, // Google already verified the email
      industry: null as string | null,
      companyName: null as string | null,
    };

    // Sign our own JWT tokens (local fallback)
    // NOTE: company_id is required by the backend's TenantMiddleware for all
    // API calls. Without it, every dashboard API request returns 403 and the
    // dashboard renders empty/mock-looking data. We use the user's id as
    // company_id (1:1 company per user), matching the register route's pattern.
    const jwtPayload = {
      sub: userData.id,
      email: userData.email,
      role: "member",
      company_id: userData.id,
      is_verified: true,
      auth_provider: "google",
    };

    const accessToken = await signAccessToken(jwtPayload);
    const refreshToken = await signRefreshToken(jwtPayload);

    const response = NextResponse.json({
      status: "success",
      is_new_user: true, // Assume new user in fallback mode
      user: userData,
    });

    setAuthCookies(response, accessToken, refreshToken, userData);

    return response;
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
