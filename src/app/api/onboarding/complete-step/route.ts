/**
 * SHOBH Onboarding Complete Step API
 * 
 * POST /api/onboarding/complete-step?step=N - Mark a step as completed
 * Updates onboarding session in Supabase
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAuthenticatedUserId } from '@/lib/api-auth';
import { completeOnboardingStep, getOnboardingSession, getUserDetails, getIntegrations, getKnowledgeBases, db } from '@/lib/supabase-db';
import { backendProxy } from '@/lib/backend-proxy';

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
    if (step === 1 && evidence.work_email_verified !== true) {
      const token =
        request.headers.get('authorization')?.replace(/^Bearer\s+/i, '') ||
        request.cookies.get('parwa_at')?.value;
      const workEmail = String(evidence.work_email || '').trim().toLowerCase();
      if (!token || !workEmail) {
        return NextResponse.json(
          { error: 'email_not_verified', message: 'Verify the saved work email before completing this step.' },
          { status: 409 }
        );
      }

      // Reconcile a backend-confirmed OTP if the earlier mirror write failed.
      const { response } = await backendProxy(
        `/api/verification/status/${encodeURIComponent(workEmail)}`,
        { method: 'GET', authToken: token }
      );
      const verification = await response.json().catch(() => ({}));
      if (!response.ok || verification.verified !== true) {
        return NextResponse.json(
          { error: 'email_not_verified', message: 'Verify the saved work email before completing this step.' },
          { status: 409 }
        );
      }

      const mirrored = await db.from('user_details').update(
        { work_email_verified: true, updated_at: new Date().toISOString() },
        { user_id: userId, work_email: workEmail }
      );
      if (!Array.isArray(mirrored) || mirrored.length === 0) {
        return NextResponse.json(
          { error: 'verification_persistence_pending', message: 'Email is verified, but onboarding could not save the verification state. Please retry.' },
          { status: 503 }
        );
      }
      evidence.work_email_verified = true;
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
