import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  // FIX A4: Check for the correct httpOnly session cookie
  // Previously checked 'parwa_access_token' which was wrong —
  // the login route sets 'parwa_session' as an httpOnly cookie.
  const token = request.cookies.get('parwa_session');
  const { pathname } = request.nextUrl;

  // Protect dashboard routes
  if (pathname.startsWith('/dashboard') && !token) {
    const loginUrl = new URL('/login', request.url);
    loginUrl.searchParams.set('redirect', pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Protect API routes that need auth (but skip public ones)
  // Public: /api/auth/login, /api/auth/register, /api/auth/check-email
  // Public: /api/onboarding/state, /api/onboarding/prerequisites (for onboarding wizard)
  if (pathname.startsWith('/api/') && !token) {
    const publicPaths = ['/api/auth/login', '/api/auth/register', '/api/auth/check-email', '/api/auth/google'];
    const isPublicApi = publicPaths.some(p => pathname.startsWith(p));
    if (!isPublicApi && !pathname.startsWith('/api/auth/verify-otp') && !pathname.startsWith('/api/auth/reset-password') && !pathname.startsWith('/api/auth/forgot-password')) {
      return NextResponse.json({ detail: 'Authentication required' }, { status: 401 });
    }
  }

  return NextResponse.next();
}

// FIX A4: Expanded matcher to cover both dashboard AND API routes
export const config = {
  matcher: ['/dashboard/:path*', '/api/:path*'],
};
