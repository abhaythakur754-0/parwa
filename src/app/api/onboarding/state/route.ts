/**
 * PARWA Onboarding State API
 * 
 * GET /api/onboarding/state - Get current onboarding session
 * POST /api/onboarding/state - Create/update session
 * 
 * Uses Supabase for persistence (not just RAM/localStorage)
 */

import { NextRequest, NextResponse } from 'next/server';
import { getOnboardingSession, createOrUpdateOnboardingSession } from '@/lib/supabase-db';

// Helper to get user ID from auth token/cookie
function getUserId(req: NextRequest): string | null {
  // Try Authorization header first
  const authHeader = req.headers.get('authorization');
  if (authHeader) {
    const token = authHeader.replace('Bearer ', '');
    return token;
  }

  // Try cookie
  const cookieHeader = req.headers.get('cookie');
  if (cookieHeader) {
    const cookies = Object.fromEntries(
      cookieHeader.split(';').map((c) => {
        const [key, ...val] = c.trim().split('=');
        return [key, val.join('=')];
      })
    );
    
    if (cookies.parwa_at) return cookies.parwa_at;
    if (cookies.user_id) return cookies.user_id;
    if (cookies.auth_token) return cookies.auth_token;
  }

  // Fallback: check query param (for testing)
  const url = new URL(req.url);
  const userId = url.searchParams.get('user_id');
  if (userId) return userId;

  return null;
}

export async function GET(request: NextRequest) {
  try {
    const userId = getUserId(request);
    
    if (!userId) {
      return NextResponse.json(
        { error: 'unauthorized', message: 'User not authenticated' },
        { status: 401 }
      );
    }

    // Fetch from Supabase
    const session = await getOnboardingSession(userId);

    if (!session) {
      // Return default state for new users
      return NextResponse.json({
        status: 'not_started',
        current_step: 1,
        completed_steps: [],
        details_completed: false,
        integration_completed: false,
        kb_completed: false,
        first_victory_completed: false,
        ai_name: 'Jarvis',
      });
    }

    return NextResponse.json(session);
  } catch (error) {
    console.error('[Onboarding API] Error fetching state:', error);
    return NextResponse.json(
      { error: 'internal_error', message: 'Failed to fetch onboarding state' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const userId = getUserId(request);
    
    if (!userId) {
      return NextResponse.json(
        { error: 'unauthorized', message: 'User not authenticated' },
        { status: 401 }
      );
    }

    const body = await request.json();
    
    // Save to Supabase
    const session = await createOrUpdateOnboardingSession({
      user_id: userId,
      ...body,
    });

    return NextResponse.json({
      success: true,
      data: session,
      message: 'Onboarding state saved successfully',
    });
  } catch (error) {
    console.error('[Onboarding API] Error saving state:', error);
    return NextResponse.json(
      { error: 'internal_error', message: 'Failed to save onboarding state' },
      { status: 500 }
    );
  }
}
