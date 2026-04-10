import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";

/**
 * Google OAuth endpoint.
 * Verifies the Google id_token, then creates or returns the local user.
 * Works standalone — no Parwa backend required.
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
          is_verified: true,
          industry: null,
          company_name: null,
          // No password for Google users — they login via Google
        },
      });
    } else {
      // Update name if we got one from Google and user doesn't have one
      if (fullName && !user.full_name) {
        await db.user.update({
          where: { email },
          data: { full_name: fullName },
        });
        user.full_name = fullName;
      }
    }

    // Step 3: Return user data
    return NextResponse.json({
      status: "success",
      is_new_user: isNewUser,
      user: {
        id: user.id,
        email: user.email,
        fullName: user.full_name,
        isVerified: user.is_verified,
        industry: user.industry,
        companyName: user.company_name,
      },
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
