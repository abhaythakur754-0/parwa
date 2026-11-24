/**
 * SHOBH Onboarding Details API (Step 1)
 * 
 * POST /api/onboarding/details - Save user details from Step 1
 * Saves to Supabase: full_name, company_url, work_email, legal consents
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAuthenticatedUserId, getRequestAccessToken } from '@/lib/authenticated-user';
import { backendProxy } from '@/lib/backend-proxy';
import { saveUserDetails, saveLegalConsent, completeOnboardingStep } from '@/lib/supabase-db';

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
    const { 
      full_name, 
      company_url, 
      work_email,
      accept_terms,
      accept_privacy,
      accept_ai_data,
    } = body;

    // Validate required fields
    if (!full_name || !company_url || !work_email) {
      return NextResponse.json(
        { error: 'validation_error', message: 'Missing required fields: full_name, company_url, work_email' },
        { status: 400 }
      );
    }

    // Confirm OTP state with the backend; never trust a client-side flag.
    const authToken = getRequestAccessToken(request);
    if (!authToken) {
      return NextResponse.json(
        { error: 'unauthorized', message: 'User not authenticated' },
        { status: 401 },
      );
    }

    const { response: verificationResponse } = await backendProxy(
      `/api/verification/status/${encodeURIComponent(work_email.toLowerCase())}`,
      { method: 'GET', authToken },
    );
    const verification = await verificationResponse.json().catch(() => ({}));
    if (!verificationResponse.ok || verification?.verified !== true) {
      return NextResponse.json(
        { error: 'email_not_verified', message: 'Verify your work email before saving onboarding details.' },
        { status: 403 },
      );
    }

    // Persist as verified only after the backend confirms the OTP.
    const userDetails = await saveUserDetails({
      user_id: userId,
      full_name,
      company_url,
      work_email: work_email.toLowerCase(),
      work_email_verified: true,
    });

    // Save legal consents if accepted
    if (accept_terms || accept_privacy || accept_ai_data) {
      // Get the created/updated user details ID
      const detailsId = userDetails?.id || userId;
      
      if (accept_terms) {
        await saveLegalConsent(detailsId, 'terms', request.headers.get('x-forwarded-for') || undefined);
      }
      if (accept_privacy) {
        await saveLegalConsent(detailsId, 'privacy', request.headers.get('x-forwarded-for') || undefined);
      }
      if (accept_ai_data) {
        await saveLegalConsent(detailsId, 'ai_data', request.headers.get('x-forwarded-for') || undefined);
      }
    }

    // Mark Step 1 as completed in onboarding session
    await completeOnboardingStep(userId, 1);

    console.log(`[Onboarding] ✅ Step 1 completed for user ${userId}:`, { full_name, company_url });

    return NextResponse.json({
      success: true,
      data: userDetails,
      message: 'Details saved successfully',
    });
  } catch (error) {
    console.error('[Onboarding API] Error saving details:', error);
    return NextResponse.json(
      { error: 'internal_error', message: 'Failed to save details' },
      { status: 500 }
    );
  }
}
