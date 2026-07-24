/**
 * PARWA Login API Route
 *
 * Forwards credentials to the backend (sole token issuer) and stores the
 * backend's JWT tokens in httpOnly cookies. The frontend never mints its
 * own tokens — this was the root cause of the dual-JWT auth bug.
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
    const { email, password } = body;

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

    const normalizedEmail = email.trim().toLowerCase();

    // ── Backend is the sole token issuer ──────────────────────
    try {
      const { response: backendRes } = await backendProxy("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: normalizedEmail, password }),
      });

      if (backendRes.ok) {
        const data = await backendRes.json();

        // Backend returns AuthResponse: { user, tokens, is_new_user }
        if (data.user && data.tokens) {
          const userData = {
            id: data.user.id,
            email: data.user.email || normalizedEmail,
            fullName: data.user.full_name,
            isVerified: data.user.is_verified ?? false,
          };

          const response = NextResponse.json({
            status: "success",
            message: "Login successful.",
            user: userData,
            is_new_user: data.is_new_user ?? false,
          });

          // Store BACKEND's tokens in cookies
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

      // Backend returned 403 — could be CSRF/origin error or forbidden
      if (backendRes.status === 403) {
        let errorData: Record<string, unknown> = {};
        try { errorData = await backendRes.json(); } catch { /* ignore */ }
        const detail = errorData.detail;
        const errorMsg = (errorData?.error as Record<string, unknown>)?.message || errorData?.message;
        const rawMessage =
          (typeof detail === "object" && detail !== null && "message" in detail)
            ? String((detail as Record<string, unknown>).message)
            : (typeof detail === "string" ? detail : null)
            || (typeof errorMsg === "string" ? errorMsg : null);
        const isCSRF = rawMessage?.toLowerCase().includes('csrf') ||
          rawMessage?.toLowerCase().includes('invalid origin');
        if (isCSRF) {
          return NextResponse.json(
            { status: "error", message: "Login temporarily unavailable. Please try again." },
            { status: 503 }
          );
        }
        return NextResponse.json(
          { status: "error", message: rawMessage || "Access denied." },
          { status: 403 }
        );
      }

      // Backend returned 401 — invalid credentials
      if (backendRes.status === 401) {
        let errorData: Record<string, unknown> = {};
        try { errorData = await backendRes.json(); } catch { /* ignore */ }
        const errorWrapper = errorData.error as Record<string, unknown> | undefined;
        const detail = errorData.detail;
        const message =
          (typeof errorWrapper?.message === "string" ? errorWrapper.message : null)
          || (typeof detail === "object" && detail !== null && "message" in detail
            ? String((detail as Record<string, unknown>).message) : null)
          || (typeof detail === "string" ? detail : null)
          || (typeof errorData.message === "string" ? errorData.message : null)
          || "Invalid email or password.";
        return NextResponse.json(
          { status: "error", message },
          { status: 401 }
        );
      }

      // Other backend errors — no local fallback (backend is sole issuer)
      console.error("[login] Backend returned", backendRes.status);
      return NextResponse.json(
        { status: "error", message: "Login service unavailable. Please try again." },
        { status: 503 }
      );
    } catch {
      // Backend unreachable — no local fallback (would create divergent auth)
      console.error("[login] Backend unreachable");
      return NextResponse.json(
        { status: "error", message: "Login service unavailable. Please try again." },
        { status: 503 }
      );
    }
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Login error:", message);
    return NextResponse.json(
      { status: "error", message: "An unexpected error occurred. Please try again." },
      { status: 500 }
    );
  }
}
