import { NextResponse } from 'next/server';

/**
 * Stub /api/v1/presence endpoint.
 *
 * The frontend (src/lib/presence-store.ts) calls this to get a list of
 * currently-online agents. The backend does not yet have this endpoint
 * implemented, so we return an empty list instead of letting the request
 * fall through to a 404.
 *
 * Once the backend implements /api/v1/presence, this stub can be deleted
 * and the catch-all proxy at /api/v1/[...path]/route.ts will forward
 * the request automatically.
 */

export async function GET() {
  return NextResponse.json({ agents: [] });
}

export async function POST() {
  return NextResponse.json({ ok: true });
}
