/**
 * SHOBH Onboarding Complete Step API
 * 
 * POST /api/onboarding/complete-step?step=N - Mark a step as completed
 * Updates onboarding session in Supabase
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAuthenticatedUserId } from '@/lib/api-auth';
import { completeOnboardingStep, getOnboardingSession, getUserDetails, getIntegrations, getKnowledgeBases } from '@/lib/supabase-db';

export async function POST(request: NextRequest) {
  try {
    const userId = await getAuthenticatedUserId(request);
    
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

    // A client cannot self-certify a step without the corresponding saved data.
    if (step === 4) {
      return NextResponse.json({ error: 'forbidden', message: 'This step is completed by the first-victory workflow' }, { status: 403 });
    }
    const evidence = step === 1
      ? await getUserDetails(userId)
      : step === 2
        ? await getIntegrations(userId)
        : await getKnowledgeBases(userId);
    if (!evidence || (Array.isArray(evidence) && evidence.length === 0)) {
      return NextResponse.json({ error: 'step_incomplete', message: 'Complete and save this step before marking it complete' }, { status: 409 });
    }
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
