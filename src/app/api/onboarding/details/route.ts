/**
 * SHOBH Onboarding Details API (Step 1)
 * 
 * POST /api/onboarding/details - Save user details from Step 1
 * Saves to Supabase: full_name, company_url, work_email, legal consents
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAuthenticatedUserId } from '@/lib/api-auth';
import { saveUserDetails, saveLegalConsent } from '@/lib/supabase-db';

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

    // Save user details to Supabase
    const userDetails = await saveUserDetails({
      user_id: userId,
      full_name,
      company_url,
      work_email: work_email.toLowerCase(),
      work_email_verified: false, // Must be set by the server-side OTP verification flow
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

    console.log(`[Onboarding] ✅ Step 1 completed for user ${userId}:`, { full_name, company_url });

    return NextResponse.json({
      success: true,
      data: userDetails,
      message: 'Details saved. Verify your work email to complete this step.',
      step_completed: false,
    });
  } catch (error) {
    console.error('[Onboarding API] Error saving details:', error);
    return NextResponse.json(
      { error: 'internal_error', message: 'Failed to save details' },
      { status: 500 }
    );
  }
}
