/**
 * PARWA Google OAuth API Route
 *
 * Handles Google Sign-In by:
 * 1. Verifying the Google id_token with Google's tokeninfo endpoint
 * 2. Creating/finding the user (via backend proxy or local Prisma)
 * 3. Signing our own JWT tokens and setting httpOnly cookies
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

    // Step 1: Verify the token with Google
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

    // Step 2: Create/find user via backend or local DB
    const userData = await findOrCreateUser(email, fullName);

    if (!userData) {
      return NextResponse.json(
        { status: "error", message: "Failed to create or find user account." },
        { status: 500 }
      );
    }

    // Step 3: Sign our own JWT tokens and set httpOnly cookies
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
 * Try to create/find user via backend proxy first.
 * If backend is unreachable, fall back to local Prisma.
 */
async function findOrCreateUser(
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
  // Try backend first (with CSRF token)
  try {
    const { response: res } = await backendProxy("/api/auth/google", {
      method: "POST",
      body: JSON.stringify({ id_token: "verified", email, full_name: fullName }),
    });

    if (res.ok) {
      const data = await res.json();
      if (data.user || data.data) {
        const user = data.user || data.data;
        return {
          id: user.id || user.user_id,
          email: user.email || email,
          full_name: user.full_name || user.fullName || fullName,
          is_verified: user.is_verified ?? user.isVerified ?? true,
          industry: user.industry || null,
          company_name: user.company_name || user.companyName || null,
          is_new_user: data.is_new_user ?? false,
        };
      }
    }
  } catch {
    // Backend unreachable — fall through to local
  }

  // Fallback: local Prisma
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
