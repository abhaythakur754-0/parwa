/**
 * SHOBH Onboarding State API
 * 
 * GET /api/onboarding/state - Get current onboarding session
 * POST /api/onboarding/state - Create/update session
 * 
 * Uses Supabase for persistence (not just RAM/localStorage)
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAuthenticatedUserId } from '@/lib/authenticated-user';
import { getOnboardingSession, createOrUpdateOnboardingSession } from '@/lib/supabase-db';

// Helper to get user ID from auth token/cookie
export async function GET(request: NextRequest) {
  try {
    const userId = await getAuthenticatedUserId(request);
    
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
    const userId = await getAuthenticatedUserId(request);
    
    if (!userId) {
      return NextResponse.json(
        { error: 'unauthorized', message: 'User not authenticated' },
        { status: 401 }
      );
    }

    const body = await request.json();
    
    // Save to Supabase
    const session = await createOrUpdateOnboardingSession({
      ...body,
      user_id: userId,
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
