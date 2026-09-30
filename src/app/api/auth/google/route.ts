/**
 * PARWA Google OAuth API Route
 *
 * Primary path: forwards the Google id_token to the backend (sole token
 * issuer), which verifies it with Google and returns PARWA JWT tokens.
 *
 * Fallback path (only when ENABLE_LOCAL_GOOGLE_AUTH=1): when the backend is
 * unreachable or rejects the token (e.g. missing GOOGLE_CLIENT_ID on the
 * backend), the id_token is verified SERVER-SIDE against Google's tokeninfo
 * endpoint (same checks as the backend) and a local session is issued.
 * Production deployments do not set the flag, so behaviour there is unchanged.
 */

import { NextRequest, NextResponse } from "next/server";
import { setAuthCookies } from "@/lib/auth-cookies";
import { backendProxy } from "@/lib/backend-proxy";
import {
  isLocalAuthEnabled,
  verifyGoogleIdTokenLocally,
  upsertLocalGoogleUser,
  mintLocalTokens,
} from "@/lib/local-auth";

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
    let backendFailed = false;
    let backendErrorStatus = 503;
    let backendErrorMessage =
      "Google sign-in service unavailable. Please try again.";

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
          backendFailed = true;
          data = {};
        }

        if (!backendFailed) {
          const authData = (data.data || data) as Record<string, unknown>;
          const userObj = (authData.user || data.user) as
            | Record<string, unknown>
            | undefined;
          const tokensObj = (authData.tokens || data.tokens) as
            | Record<string, unknown>
            | undefined;
          const isNewUser = (authData.is_new_user ??
            data.is_new_user ??
            true) as boolean;

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
          backendFailed = true;
        }
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
          backendFailed = true;
          backendErrorStatus = backendRes.status;
          backendErrorMessage =
            message || "Google sign-in failed. Please try again.";
        } else {
          console.error("[google-auth] Backend returned", backendRes.status);
          backendFailed = true;
        }
      }
    } catch {
      console.error("[google-auth] Backend unreachable");
      backendFailed = true;
    }

    // ── Local fallback (gated): verify with Google directly ────
    if (backendFailed && isLocalAuthEnabled()) {
      const claims = await verifyGoogleIdTokenLocally(id_token);
      if (claims) {
        const user = await upsertLocalGoogleUser(claims);
        if (user) {
          try {
            const tokens = await mintLocalTokens(user.id, user.email);

            const userData = {
              id: user.id,
              email: user.email,
              fullName: user.full_name || user.email.split("@")[0],
              isVerified: user.is_verified,
              industry: user.industry,
              companyName: user.company_name,
            };

            const response = NextResponse.json({
              status: "success",
              is_new_user: false,
              user: userData,
              session: "local",
            });

            setAuthCookies(
              response,
              tokens.accessToken,
              tokens.refreshToken,
              userData,
              tokens.expiresIn,
            );

            console.info(
              "[google-auth] Local session issued (backend unavailable) for %s",
              user.email,
            );
            return response;
          } catch (err) {
            console.error("[google-auth] Local token minting failed:", err);
          }
        } else {
          console.error("[google-auth] Local user upsert failed");
        }
      } else {
        console.error("[google-auth] Local fallback: Google rejected the token");
        return NextResponse.json(
          { status: "error", message: "Google sign-in failed. Please try again." },
          { status: 401 },
        );
      }
    }

    return NextResponse.json(
      { status: "error", message: backendErrorMessage },
      { status: backendErrorStatus },
    );
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
