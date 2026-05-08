import { NextResponse } from 'next/server';

/**
 * POST /api/auth/login (Dashboard)
 *
 * ── H-20 FIX: Removed mock login that accepted ANY credentials ──
 * Dashboard auth routes should NOT exist in production — use the main
 * frontend auth API at /api/auth/login instead.
 */
export async function POST(request: Request) {
  return NextResponse.json(
    {
      status: 'error',
      message: 'Dashboard mock login has been removed. Use the main frontend authentication API.',
    },
    { status: 410 } // Gone — this endpoint is intentionally disabled
  );
}
