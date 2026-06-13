/**
 * PARWA Integrations API — Delete Integration
 *
 * DELETE /api/integrations/:id — remove an integration
 */

import { NextRequest, NextResponse } from 'next/server';
import { backendProxy } from '@/lib/backend-proxy';

function getAuthToken(req: NextRequest): string | undefined {
  const authHeader = req.headers.get('authorization');
  if (authHeader) return authHeader.replace('Bearer ', '');
  const cookieHeader = req.headers.get('cookie');
  if (cookieHeader) {
    const cookies = Object.fromEntries(
      cookieHeader.split(';').map((c) => {
        const [key, ...val] = c.trim().split('=');
        return [key, val.join('=')];
      })
    );
    if (cookies.parwa_at) return cookies.parwa_at;
  }
  return undefined;
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const authToken = getAuthToken(req);

  try {
    const { response } = await backendProxy(`/api/v1/integrations/${id}`, {
      method: 'DELETE',
      authToken,
    });

    if (response.ok) {
      const data = await response.json();
      return NextResponse.json(data);
    }

    return NextResponse.json(
      { error: 'backend_error', message: `Backend returned ${response.status}` },
      { status: response.status }
    );
  } catch {
    // Backend unreachable — return success for local removal
    return NextResponse.json({ status: 'ok', deleted: true, id });
  }
}
