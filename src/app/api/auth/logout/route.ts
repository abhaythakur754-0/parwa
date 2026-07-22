import { NextRequest, NextResponse } from 'next/server';
import { clearAuthCookies } from '@/lib/auth-cookies';

export async function POST(request: NextRequest) {
  try {
    const backendUrl = process.env.BACKEND_URL || 'https://parwa-backend.onrender.com';
    const cookie = request.headers.get('cookie') || '';
    const refreshTokenMatch = cookie.match(/parwa_rt=([^;]+)/);
    const refreshToken = refreshTokenMatch ? refreshTokenMatch[1] : null;

    if (refreshToken) {
      try {
        await fetch(`${backendUrl}/api/auth/logout`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Cookie': cookie },
          body: JSON.stringify({ refresh_token: refreshToken }),
          signal: AbortSignal.timeout(5000),
        });
      } catch { }
    }
  } catch { }

  const response = NextResponse.json({ status: 'success', message: 'Logged out successfully.' });
  return clearAuthCookies(response);
}
