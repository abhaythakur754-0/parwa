/**
 * PARWA Google OAuth API Route
 *
 * Handles Google Sign-In by:
 * 1. Forwarding the Google id_token to the backend (which verifies it and creates/finds user)
 * 2. Storing the backend's JWT tokens in httpOnly cookies
 * 3. Returning user data to the frontend
 *
 * If the backend is unreachable, falls back to:
 * - Verifying the Google token ourselves
 * - Creating/finding the user in local Prisma DB (dev only)
 * - Signing our own JWT tokens
 */

import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
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
        body: JSON.stringify({ id_token }), // Send REAL id_token, not "verified"
      });

      if (backendRes.ok) {
        const data = await backendRes.json();

        // Backend returns AuthResponse: { user, tokens, is_new_user }
        if (data.user && data.tokens) {
          const userData = {
            id: data.user.id,
            email: data.user.email,
            fullName: data.user.full_name,
            isVerified: data.user.is_verified,
            industry: data.user.company_name ? undefined : undefined,
            companyName: data.user.company_name,
          };

          const response = NextResponse.json({
            status: "success",
            is_new_user: data.is_new_user ?? false,
            user: userData,
          });

          // Store BACKEND's tokens in cookies — the backend can verify these
          setAuthCookies(
            response,
            data.tokens.access_token,
            data.tokens.refresh_token,
            userData,
            data.tokens.expires_in,
          );

          return response;
        }
      }

      // Backend returned an error — try to extract the message
      if (backendRes.status === 401 || backendRes.status === 403) {
        let errorData: Record<string, unknown> = {};
        try { errorData = await backendRes.json(); } catch { /* ignore */ }
        const message =
          (errorData as Record<string, unknown>).detail
          || (errorData as Record<string, unknown>).message
          || "Google sign-in failed. Please try again.";
        return NextResponse.json(
          { status: "error", message: String(message) },
          { status: backendRes.status }
        );
      }

      // Other backend errors — fall through to local fallback
      console.warn("[google-auth] Backend returned", backendRes.status, "— falling back to local");
    } catch (backendError) {
      console.warn("[google-auth] Backend unreachable — falling back to local:", backendError);
    }

    // ── Step 2: Local fallback (dev / backend down) ─────────────
    // Verify the Google token ourselves, then use Prisma
    const googleRes = await fetch(
      `https://oauth2.googleapis.com/tokeninfo?id_token=${encodeURIComponent(id_token)}`
    );

    if (!googleRes.ok) {
      return NextResponse.json(
        { status: "error", message: "Google token verification failed." },
        { status: 401 }
      );
    }

    const googleUser = await googleRes.json();

    if (!googleUser.email) {
      return NextResponse.json(
        { status: "error", message: "Could not get email from Google account." },
        { status: 400 }
      );
    }

    if (!googleUser.email_verified) {
      return NextResponse.json(
        { status: "error", message: "Please verify your email with Google first." },
        { status: 403 }
      );
    }

    const email = googleUser.email.trim().toLowerCase();
    const fullName = googleUser.name || googleUser.given_name || null;

    const userData = await findOrCreateUserLocal(email, fullName);

    if (!userData) {
      return NextResponse.json(
        { status: "error", message: "Failed to create or find user account. The backend may be unavailable — please try again later." },
        { status: 500 }
      );
    }

    // Sign our own JWT tokens (local fallback only)
    const jwtPayload = {
      sub: userData.id,
      email: userData.email,
      role: "member",
      company_id: userData.company_name || undefined,
      is_verified: userData.is_verified,
    };

    const accessToken = await signAccessToken(jwtPayload);
    const refreshToken = await signRefreshToken(jwtPayload);

    const responseData = {
      id: userData.id,
      email: userData.email,
      fullName: userData.full_name,
      isVerified: userData.is_verified,
      industry: userData.industry,
      companyName: userData.company_name,
    };

    const response = NextResponse.json({
      status: "success",
      is_new_user: userData.is_new_user,
      user: responseData,
    });

    setAuthCookies(response, accessToken, refreshToken, responseData);

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

/**
 * Local Prisma fallback for creating/finding a user.
 * Only used when the backend is unreachable.
 */
async function findOrCreateUserLocal(
  email: string,
  fullName: string | null
): Promise<{
  id: string;
  email: string;
  full_name: string | null;
  is_verified: boolean;
  industry: string | null;
  company_name: string | null;
  is_new_user: boolean;
} | null> {
  try {
    let user = await db.user.findUnique({ where: { email } });
    const isNewUser = !user;

    if (!user) {
      user = await db.user.create({
        data: {
          email,
          full_name: fullName,
          is_verified: true,
          industry: null,
          company_name: null,
        },
      });
    } else {
      if (fullName && !user.full_name) {
        await db.user.update({
          where: { email },
          data: { full_name: fullName },
        });
        user.full_name = fullName;
      }
    }

    return {
      ...user,
      is_new_user: isNewUser,
    };
  } catch (dbError) {
    console.error("Local DB fallback failed:", dbError);
    return null;
  }
}
