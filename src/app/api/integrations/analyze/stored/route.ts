/**
 * GET /api/integrations/analyze/stored
 *
 * Retrieves the most recent CRM analysis that was saved during onboarding.
 * Used by Dashboard to show recommendations without re-running analysis.
 *
 * Business Value:
 * - Shows onboarding-time recommendations in dashboard
 * - Persists insights across sessions
 * - Avoids redundant LLM calls
 */

import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://parwa-backend.onrender.com';

export async function GET(request: NextRequest) {
  try {
    // Get auth token from request
    const authHeader = request.headers.get('authorization');
    
    // Forward to backend
    const response = await fetch(`${BACKEND_URL}/api/integrations/analyze/stored`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        ...(authHeader ? { Authorization: authHeader } : {}),
        // Forward session cookie if present
        'Cookie': request.headers.get('cookie') || '',
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { 
          error: 'Failed to retrieve stored analysis', 
          details: errorData,
          status: response.status 
        },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);

  } catch (error) {
    console.error('Stored CRM Analysis proxy error:', error);
    return NextResponse.json(
      { error: 'Failed to connect to analysis service' },
      { status: 500 }
    );
  }
}
