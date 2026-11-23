import { NextRequest, NextResponse } from "next/server";
import { verifyAuth } from "@/lib/auth";

/**
 * SHOBH — Next.js Middleware (SIMPLIFIED)
 *
 * Route protection for authenticated routes.
 * Public paths bypass auth. Everything else requires a valid parwa_at cookie.
 *
 * IMPORTANT: All API routes used by public pages (login, signup, onboarding)
 * MUST be listed in PUBLIC_PATHS to avoid 401 loops.
 */

const PUBLIC_PATHS = [
  // Auth pages
  "/",
  "/login",
  "/signup",
  "/forgot-password",
  "/reset-password",
  "/auth/verify-email",
  "/auth/mfa-verify",
  "/auth/mfa-setup",
  // Marketing pages
  "/contact",
  "/pricing",
  "/about",
  "/roi-calculator",
  "/models",
  // Onboarding (needs to be accessible for new users)
  "/onboarding",
  "/jarvis",
  "/welcome",
  // API routes that must work without auth
  "/api/auth",
  "/api/health",
  "/api/demo",
  "/api/v1",
  "/api/billing",
  "/api/jarvis",
  "/api/chat",
  "/api/book-demo",
  "/api/user",
  "/api/integrations",
  "/api/public",
  "/api/pricing",
  "/api/send-email",
  "/api/send-sms",
  "/api/verification",
  "/api/forgot-password",
  "/api/channel-status",
  "/api/ticket-solve",
  "/api/analytics",
  "/api/voice",
  "/api/mfa",
  "/api/ai",
  // Test page (still requires backend auth via cookie, but page itself is public)
  "/test-razorpay",
  // Static assets
  "/_next",
  "/favicon.ico",
  "/robots.txt",
];

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PATHS.some(
    (path) => pathname === path || pathname.startsWith(path + "/")
  );
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public paths without auth
  if (isPublicPath(pathname)) {
    return NextResponse.next();
  }

  // Allow static assets
  if (
    pathname.startsWith("/_next/") ||
    pathname.startsWith("/static/") ||
    (pathname.includes(".") && !pathname.startsWith("/api/"))
  ) {
    return NextResponse.next();
  }

  // Verify the access token cryptographically; token presence alone is not auth.
  const user = await verifyAuth(request);
  if (!user || typeof user.sub !== "string" || !user.sub) {
    if (pathname.startsWith("/api/")) {
      return NextResponse.json(
        { status: "error", message: "Authentication required." },
        { status: 401 }
      );
    }
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|public).*)",
  ],
};
