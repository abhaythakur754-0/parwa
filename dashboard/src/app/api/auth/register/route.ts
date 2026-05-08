import { NextResponse } from 'next/server';

/**
 * POST /api/auth/register (Dashboard)
 *
 * ── H-20 FIX: Removed mock registration endpoint ──
 * Use the main frontend registration API at /api/auth/register instead.
 */
export async function POST(request: Request) {
  return NextResponse.json(
    {
      status: 'error',
      message: 'Dashboard mock registration has been removed. Use the main frontend authentication API.',
    },
    { status: 410 }
  );
}
