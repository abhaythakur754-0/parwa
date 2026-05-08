import { NextRequest, NextResponse } from 'next/server';
import { sendEmail } from '@/lib/email';

// Auth check helper
function requireAuth(request: NextRequest): boolean {
  const authHeader = request.headers.get('authorization');
  const sessionCookie = request.cookies.get('parwa_session');
  if (!authHeader && !sessionCookie) {
    return false;
  }
  if (authHeader && !authHeader.startsWith('Bearer ')) {
    return false;
  }
  return true;
}

export async function POST(request: NextRequest) {
  if (!requireAuth(request)) {
    return NextResponse.json(
      { success: false, error: 'Authentication required' },
      { status: 401 }
    );
  }
  try {
    const body = await request.json();
    const { to, subject, htmlContent, textContent } = body;

    if (!to || !subject) {
      return NextResponse.json(
        { success: false, error: 'to and subject are required' },
        { status: 400 }
      );
    }

    const html = htmlContent || `<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;"><p>${textContent || subject}</p><hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;" /><p style="color: #888; font-size: 12px;">Powered by PARWA AI Workforce Platform</p></div>`;

    const result = await sendEmail(to, subject, html);
    return NextResponse.json(result);
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    return NextResponse.json(
      { success: false, error: message },
      { status: 500 }
    );
  }
}
