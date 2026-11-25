/**
 * SHOBH Onboarding Activate API
 * 
 * POST /api/onboarding/activate - Complete onboarding and activate account
 * Called after Step 3 (Knowledge Base) to move to Step 4 (First Victory)
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAuthenticatedUserId } from '@/lib/api-auth';
import { createOrUpdateOnboardingSession, getOnboardingSession, getUserDetails } from '@/lib/supabase-db';

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
    const { variant, industry } = body;

    const existing = await getOnboardingSession(userId);
    if (!existing || !existing.details_completed || !existing.integration_completed || !existing.kb_completed) {
      return NextResponse.json({ error: 'onboarding_incomplete', message: 'Complete the required onboarding steps first' }, { status: 409 });
    }
    const userDetails = await getUserDetails(userId);
    if (!userDetails || userDetails.work_email_verified !== true) {
      return NextResponse.json(
        { error: 'email_not_verified', message: 'Verify your saved work email before activating the account.' },
        { status: 409 }
      );
    }

    // Preserve verified progress; do not manufacture completed steps.
    const session = await createOrUpdateOnboardingSession({
      user_id: userId,
      status: 'completed',
      current_step: 4,
      completed_steps: existing.completed_steps || [],
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
