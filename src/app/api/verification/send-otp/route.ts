/**
 * PARWA Send OTP Email API
 * 
 * POST /api/verification/send-otp
 * Sends a 6-digit OTP to the user's email via Brevo
 */

import { NextRequest, NextResponse } from 'next/server';
import { sendOtpEmail } from '@/lib/email-brevo';

// Simple in-memory store for OTPs (in production, use Redis or DB)
const otpStore = new Map<string, { code: string; expiresAt: Date; attempts: number }>();

function generateOTP(): string {
  // Generate 6-digit numeric OTP
  return Math.floor(100000 + Math.random() * 900000).toString();
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { email } = body;

    if (!email || !email.includes('@')) {
      return NextResponse.json(
        { error: 'validation_error', message: 'Valid email address is required' },
        { status: 400 }
      );
    }

    const normalizedEmail = email.toLowerCase().trim();

    // Check rate limiting (max 3 OTPs per 5 minutes)
    const existing = otpStore.get(normalizedEmail);
    if (existing && existing.expiresAt > new Date()) {
      const timeRemaining = Math.ceil((existing.expiresAt.getTime() - Date.now()) / 1000 / 60);
      
      if (existing.attempts >= 3) {
        return NextResponse.json(
          { error: 'rate_limited', message: `Too many requests. Try again in ${timeRemaining} minutes.` },
          { status: 429 }
        );
      }
    }

    // Generate and store new OTP
    const otpCode = generateOTP();
    const expiresAt = new Date(Date.now() + 10 * 60 * 1000); // 10 minutes

    otpStore.set(normalizedEmail, {
      code: otpCode,
      expiresAt,
      attempts: (existing?.attempts || 0) + 1,
    });

    console.log(`[OTP] Generated for ${normalizedEmail}: ${otpCode} (expires ${expiresAt.toISOString()})`);

    // Send email via Brevo
    const result = await sendOtpEmail({
      to: normalizedEmail,
      otpCode,
      expiryMinutes: 10,
    });

    if (!result.success) {
      return NextResponse.json(
        { error: 'send_failed', message: result.error || 'Failed to send OTP email' },
        { status: 500 }
      );
    }

    return NextResponse.json({
      success: true,
      message: 'OTP sent successfully',
      // Don't return the actual OTP in production!
      // For debugging only:
      ...(process.env.NODE_ENV === 'development' ? { debug_otp: otpCode } : {}),
      expires_in: 600, // 10 minutes in seconds
    });
  } catch (error) {
    console.error('[OTP Send Error]:', error);
    return NextResponse.json(
      { error: 'internal_error', message: 'Failed to send OTP' },
      { status: 500 }
    );
  }
}
