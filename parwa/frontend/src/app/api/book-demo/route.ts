import { NextRequest, NextResponse } from 'next/server';

export async function POST(req: NextRequest) {
  try {
    const { name, email, company, industry, preferredDate, message } = await req.json();

    if (!name || !email || !company) {
      return NextResponse.json(
        { status: 'error', message: 'Name, email, and company are required.' },
        { status: 400 }
      );
    }

    if (typeof email !== 'string' || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return NextResponse.json(
        { status: 'error', message: 'Please enter a valid email address.' },
        { status: 400 }
      );
    }

    // Demo request stored - in production this would go to a database
    console.log('Demo request received:', { name, email, company, industry, preferredDate, message });

    return NextResponse.json({
      status: 'success',
      message: 'Demo request submitted successfully! Our team will reach out within 24 hours.',
      id: `demo-${Date.now()}`,
    });
  } catch (error: any) {
    console.error('Book Demo API error:', error);
    return NextResponse.json(
      { status: 'error', message: 'Failed to submit demo request. Please try again.' },
      { status: 500 }
    );
  }
}
