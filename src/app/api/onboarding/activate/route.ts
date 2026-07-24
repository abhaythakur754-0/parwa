/**
 * PARWA Onboarding Activate API
 * 
 * POST /api/onboarding/activate - Complete onboarding and activate account
 * Called after Step 3 (Knowledge Base) to move to Step 4 (First Victory)
 */

import { NextRequest, NextResponse } from 'next/server';
import { createOrUpdateOnboardingSession } from '@/lib/supabase-db';

function getUserId(req: NextRequest): string | null {
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
    if (cookies.user_id) return cookies.user_id;
  }

  const url = new URL(req.url);
  return url.searchParams.get('user_id');
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
    const { variant, industry } = body;

    // Update session with final data and mark as ready for FirstVictory
    const session = await createOrUpdateOnboardingSession({
      user_id: userId,
      status: 'completed',
      current_step: 4,
      completed_steps: [1, 2, 3],
      details_completed: true,
      integration_completed: true,
      kb_completed: true,
      selected_variant: variant || 'parwa',
      selected_industry: industry || 'other',
    });

    console.log(`[Onboarding] 🎉 Account activated for user ${userId}`, { variant, industry });

    return NextResponse.json({
      success: true,
      data: session,
      message: 'Account activated! Ready for First Victory.',
      redirect_to: '/onboarding?step=4', // Redirect to FirstVictory
    });
  } catch (error) {
    console.error('[Onboarding API] Error activating:', error);
    return NextResponse.json(
      { error: 'internal_error', message: 'Failed to activate account' },
      { status: 500 }
    );
  }
}
