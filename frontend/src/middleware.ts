import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const STORAGE_KEY = 'parwa_auth';

// Routes that require authentication
const PROTECTED_ROUTES = ['/chat'];
// Routes that should redirect to dashboard if already authenticated
const AUTH_ROUTES = ['/onboarding'];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Read the auth token from cookies (we set it on login)
  // Since Next.js middleware runs on the edge, we can't use localStorage
  // Instead, we mirror the auth state into a cookie
  const authToken = request.cookies.get('parwa_auth_jwt')?.value;
  const isAuthenticated = !!authToken;

  // Protect dashboard/chat routes
  if (PROTECTED_ROUTES.some(route => pathname.startsWith(route)) && !isAuthenticated) {
    const url = request.nextUrl.clone();
    url.pathname = '/';
    return NextResponse.redirect(url);
  }

  // If already authenticated and trying to access onboarding, redirect to dashboard
  if (AUTH_ROUTES.some(route => pathname.startsWith(route)) && isAuthenticated) {
    const url = request.nextUrl.clone();
    url.pathname = '/';
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/chat/:path*', '/onboarding/:path*'],
};
