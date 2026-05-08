import { NextRequest, NextResponse } from "next/server";
import { verifyToken } from "@/lib/jwt";

/**
 * PARWA — Next.js Middleware
 *
 * Provides route protection for authenticated routes.
 * Verifies JWT from Authorization header or httpOnly cookie.
 *
 * Protected routes:
 *   /models, /tickets, /settings, /billing, /analytics, /channels,
 *   /knowledge, /api/chat, /api/tickets/* (except public API routes)
 *
 * Public routes (no auth needed):
 *   /, /login, /signup, /forgot-password, /reset-password,
 *   /api/auth/*, /api/health, /contact, /pricing, /about
 */

const PUBLIC_PATHS = [
  "/",
  "/login",
  "/signup",
  "/forgot-password",
  "/reset-password",
  "/contact",
  "/pricing",
  "/about",
  "/api/auth",
  "/api/health",
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
    pathname.includes(".") // favicon, robots, etc.
  ) {
    return NextResponse.next();
  }

  // Extract token from Authorization header or cookie
  const authHeader = request.headers.get("authorization");
  let token: string | null = null;

  if (authHeader && authHeader.startsWith("Bearer ")) {
    token = authHeader.slice(7);
  }

  if (!token) {
    // Try httpOnly cookie
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

  // Verify token
  const verified = await verifyToken(token);
  if (!verified) {
    // Token invalid/expired
    if (pathname.startsWith("/api/")) {
      return NextResponse.json(
        { status: "error", message: "Token is invalid or expired." },
        { status: 401 }
      );
    }
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Inject user info into request headers for downstream handlers
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-user-id", verified.payload.sub);
  requestHeaders.set("x-user-email", verified.payload.email || "");

  return NextResponse.next({
    request: { headers: requestHeaders },
  });
}

export const config = {
  matcher: [
    /*
     * Match all request paths except:
     * - _next/static (static files)
     * - _next/image (image optimization)
     * - public files (public directory)
     */
    "/((?!_next/static|_next/image|public).*)",
  ],
};
