/**
 * PARWA Onboarding Complete Step API
 * 
 * POST /api/onboarding/complete-step?step=N - Mark a step as completed
 * Updates onboarding session in Supabase
 */

import { NextRequest, NextResponse } from 'next/server';
import { completeOnboardingStep, getOnboardingSession } from '@/lib/supabase-db';

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

    // Get step number from query parameter
    const url = new URL(request.url);
    const stepParam = url.searchParams.get('step');
    
    if (!stepParam || isNaN(parseInt(stepParam))) {
      return NextResponse.json(
        { error: 'validation_error', message: 'Missing or invalid "step" query parameter' },
        { status: 400 }
      );
    }

    const step = parseInt(stepParam);

    if (step < 1 || step > 4) {
      return NextResponse.json(
        { error: 'validation_error', message: 'Step must be between 1 and 4' },
        { status: 400 }
      );
    }

    // Complete the step in Supabase
    const session = await completeOnboardingStep(userId, step);

    console.log(`[Onboarding] ✅ Step ${step} completed for user ${userId}`);

    return NextResponse.json({
      success: true,
      data: session,
      message: `Step ${step} marked as completed`,
      next_step: Math.min(step + 1, 4),
    });
  } catch (error) {
    console.error('[Onboarding API] Error completing step:', error);
    return NextResponse.json(
      { error: 'internal_error', message: 'Failed to complete step' },
      { status: 500 }
    );
  }
}
