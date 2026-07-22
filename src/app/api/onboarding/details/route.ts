/**
 * PARWA Onboarding Details API (Step 1)
 * 
 * POST /api/onboarding/details - Save user details from Step 1
 * Saves to Supabase: full_name, company_url, work_email, legal consents
 */

import { NextRequest, NextResponse } from 'next/server';
import { saveUserDetails, saveLegalConsent, completeOnboardingStep } from '@/lib/supabase-db';

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
      work_email_verified: true, // Assume verified after OTP step
    });

    // Save legal consents if accepted
    if (accept_terms || accept_privacy || accept_ai_data) {
      // Get the created/updated user details ID
      const detailsId = userDetails?.id || userId;
      
      if (accept_terms) {
        await saveLegalConsent(detailsId, 'terms', request.ip);
      }
      if (accept_privacy) {
        await saveLegalConsent(detailsId, 'privacy', request.ip);
      }
      if (accept_ai_data) {
        await saveLegalConsent(detailsId, 'ai_data', request.ip);
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
