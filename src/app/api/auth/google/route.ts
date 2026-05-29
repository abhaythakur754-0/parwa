import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { signAccessToken, signRefreshToken } from "@/lib/jwt";
import { setAuthCookies } from "@/lib/auth-cookies";

/**
 * Google OAuth endpoint.
 * Verifies the Google id_token, then creates or returns the local user.
 * Sets JWT tokens as httpOnly cookies for authentication.
 */
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

    // Verify audience matches our Google Client ID
    const expectedClientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || process.env.GOOGLE_CLIENT_ID;
    if (expectedClientId && googleUser.aud !== expectedClientId) {
      return NextResponse.json(
        { status: "error", message: "Google token audience mismatch." },
        { status: 401 }
      );
    }

    // Google returns: sub, email, email_verified, name, given_name, family_name, picture
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
    const avatarUrl = googleUser.picture || null;

    // Step 2: Find or create user in local DB
    let user = await db.user.findUnique({
      where: { email },
    });

    const isNewUser = !user;

    if (!user) {
      user = await db.user.create({
        data: {
          email,
          full_name: fullName,
          avatar_url: avatarUrl,
          is_verified: true, // Google-verified emails are auto-verified
          is_active: true,
          role: "member",
          industry: null,
          company_name: null,
          // No password for Google users — they login via Google
        },
      });
    } else {
      // Update name and avatar if we got them from Google
      const updateData: Record<string, unknown> = {};
      if (fullName && !user.full_name) updateData.full_name = fullName;
      if (avatarUrl && !user.avatar_url) updateData.avatar_url = avatarUrl;
      if (!user.is_verified) updateData.is_verified = true; // Auto-verify Google-authenticated users

      if (Object.keys(updateData).length > 0) {
        await db.user.update({
          where: { email },
          data: updateData,
        });
        user = { ...user, ...updateData } as typeof user;
      }
    }

    // Step 3: Sign JWT tokens
    const jwtPayload = {
      sub: user.id,
      email: user.email,
      role: user.role || "member",
      company_id: user.company_name || undefined,
      is_verified: user.is_verified,
    };

    const accessToken = await signAccessToken(jwtPayload);
    const refreshToken = await signRefreshToken(jwtPayload);

    const userData = {
      id: user.id,
      email: user.email,
      fullName: user.full_name,
      isVerified: user.is_verified,
      industry: user.industry,
      companyName: user.company_name,
    };

    // Step 4: Set auth cookies and return response
    const response = NextResponse.json({
      status: "success",
      is_new_user: isNewUser,
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
