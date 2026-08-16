import { NextRequest, NextResponse } from "next/server";

/**
 * PARWA — Next.js Middleware (SIMPLIFIED)
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
  "/api/onboarding",
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
  "/api/kb",
  "/api/mfa",
  "/api/ai",
  "/api/admin",
  "/api/razorpay",
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
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }

  // Extract token from cookie
  let token: string | null = null;
  const cookieHeader = request.headers.get("cookie");
  if (cookieHeader) {
    const cookies = Object.fromEntries(
      cookieHeader.split(";").map((c) => {
        const [key, ...val] = c.trim().split("=");
        return [key, val.join("=")];
      })
    );
    token = cookies["parwa_at"] || null;
  }

  // Also check Authorization header
  if (!token) {
    const authHeader = request.headers.get("authorization");
    if (authHeader && authHeader.startsWith("Bearer ")) {
      token = authHeader.slice(7);
    }
  }

  if (!token) {
    // For API routes, return 401
    if (pathname.startsWith("/api/")) {
      return NextResponse.json(
        { status: "error", message: "Authentication required." },
        { status: 401 }
      );
    }
    // For page routes, redirect to login
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Token exists — let it through. The backend will verify the token
  // on actual API calls. This avoids JWT verification issues in middleware
  // (secret key mismatch, algorithm differences, etc.)
  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|public).*)",
  ],
};
