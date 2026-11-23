/**
 * SHOBH Onboarding State API
 * 
 * GET /api/onboarding/state - Get current onboarding session
 * POST /api/onboarding/state - Create/update session
 * 
 * Uses Supabase for persistence (not just RAM/localStorage)
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAuthenticatedUserId } from '@/lib/api-auth';
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
    const allowedFields = [
      'current_step', 'completed_steps', 'details_completed',
      'integration_completed', 'kb_completed', 'first_victory_completed',
      'ai_name', 'selected_variant', 'selected_industry',
    ] as const;
    const safeUpdates: Record<string, unknown> = {};
    for (const field of allowedFields) {
      if (Object.prototype.hasOwnProperty.call(body, field)) {
        safeUpdates[field] = body[field];
      }
    }
    // Ownership, status, and verification flags are server-controlled.
    const session = await createOrUpdateOnboardingSession({
      user_id: userId,
      ...safeUpdates,
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
