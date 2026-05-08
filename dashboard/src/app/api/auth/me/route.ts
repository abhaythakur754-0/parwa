import { NextResponse } from 'next/server';

/**
 * GET /api/auth/me (Dashboard)
 *
 * ── H-20 FIX: Removed hardcoded mock user response ──
 * Use the main frontend /api/auth/me endpoint with proper JWT auth.
 */
export async function GET() {
  return NextResponse.json(
    {
      status: 'error',
      message: 'Dashboard mock auth endpoint has been removed. Use the main frontend authentication API.',
    },
    { status: 410 }
  );
}
