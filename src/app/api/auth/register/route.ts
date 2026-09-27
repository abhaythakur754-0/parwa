/**
 * PARWA Register API Route
 *
 * Forwards registration data to the backend (sole token issuer) and stores
 * the backend's JWT tokens in httpOnly cookies. The frontend never mints
 * its own tokens — this was the root cause of the dual-JWT auth bug.
 *
 * If the backend is unreachable, returns 503 (no local fallback that
 * would create divergent auth state).
 */

import { NextRequest, NextResponse } from "next/server";
import { validatePasswordStrength } from "@/lib/jwt";
import { setAuthCookies } from "@/lib/auth-cookies";
import { backendProxy } from "@/lib/backend-proxy";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email, password, fullName, companyName, industry, uniqueId } = body;

    // Validate required fields
    if (!email || typeof email !== "string" || !email.includes("@")) {
      return NextResponse.json(
        { status: "error", message: "A valid email address is required." },
        { status: 400 }
      );
    }

    if (!password || typeof password !== "string") {
      return NextResponse.json(
        { status: "error", message: "Password is required." },
        { status: 400 }
      );
    }

    const passwordCheck = validatePasswordStrength(password);
    if (!passwordCheck.valid) {
      return NextResponse.json(
        { status: "error", message: passwordCheck.errors.join(" ") },
        { status: 400 }
      );
    }

    const normalizedEmail = email.trim().toLowerCase();

    // ── Backend is the sole token issuer ──────────────────────
    try {
      const { response: backendRes } = await backendProxy("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({
          email: normalizedEmail,
          password,
          confirm_password: password,
          full_name: fullName || "User",
          company_name: companyName || `${fullName || "User"}'s Company`,
          unique_id: uniqueId || "",
          industry: industry || "general",
        }),
      });

      if (backendRes.ok) {
        const data = await backendRes.json();

        const authData = data.data || data;
        const userObj = authData.user || data.user;
        const tokensObj = authData.tokens || data.tokens;
        const isNewUser = authData.is_new_user ?? data.is_new_user ?? true;

        if (userObj && tokensObj) {
          const userData = {
            id: userObj.id,
            email: userObj.email || normalizedEmail,
            fullName: userObj.name || fullName,
            isVerified: userObj.emailVerified ?? false,
          };

          const response = NextResponse.json({
            status: "success",
            message: "Account created successfully! Please check your email to verify your account.",
            user: userData,
            is_new_user: isNewUser,
          });

          setAuthCookies(
            response,
            tokensObj.access_token,
            tokensObj.refresh_token,
            userData,
            tokensObj.expires_in,
          );

          return response;
        }
      }

      // Backend returned conflict (email exists) OR validation error.
      if (backendRes.status === 409 || backendRes.status === 422) {
        let errorData: Record<string, unknown> = {};
        try { errorData = await backendRes.json(); } catch { /* ignore */ }

        const errorWrapper = errorData.error as Record<string, unknown> | undefined;
        const detail = errorData.detail;
        let message = "";
        if (typeof errorWrapper?.message === "string") {
          message = errorWrapper.message;
        } else if (typeof detail === "string") {
          message = detail;
        } else if (Array.isArray(detail)) {
          message = detail.map((e: Record<string, unknown>) => e.msg || String(e)).join(". ");
        } else if (typeof detail === "object" && detail !== null && "message" in detail) {
          message = String((detail as Record<string, unknown>).message);
        } else if (typeof errorData.message === "string") {
          message = errorData.message;
        }

        if (!message || /email already|already registered|already exists/i.test(message)) {
          message = "An account with this email already exists. Please sign in instead.";
        }

        return NextResponse.json(
          { status: "error", message },
          { status: backendRes.status === 409 ? 409 : 400 }
        );
      }

      // CSRF / Origin errors — return 503
      if (backendRes.status === 403) {
        let errorData: Record<string, unknown> = {};
        try { errorData = await backendRes.json(); } catch { /* ignore */ }
        const detail = errorData.detail;
        const errorMsg = (errorData?.error as Record<string, unknown>)?.message || errorData?.message;
        const message =
          (typeof detail === "object" && detail !== null && "message" in detail)
            ? String((detail as Record<string, unknown>).message)
            : (typeof detail === "string" ? detail : null)
            || (typeof errorMsg === "string" ? errorMsg : null)
            || "Registration temporarily unavailable. Please try again.";
        return NextResponse.json(
          { status: "error", message },
          { status: 503 }
        );
      }

      // Other backend errors — no local fallback
      console.error("[register] Backend returned", backendRes.status);
      return NextResponse.json(
        { status: "error", message: "Registration service unavailable. Please try again." },
        { status: 503 }
      );
    } catch {
      console.error("[register] Backend unreachable");
      return NextResponse.json(
        { status: "error", message: "Registration service unavailable. Please try again." },
        { status: 503 }
      );
    }
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Register error:", message);
    return NextResponse.json(
      { status: "error", message: "An unexpected error occurred. Please try again." },
      { status: 500 }
    );
  }
}
