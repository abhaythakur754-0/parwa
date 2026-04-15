import { NextRequest, NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();

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

    // Store demo request in the database via the Post model (repurposed as DemoRequest)
    // Since there's no dedicated DemoRequest model, we'll use a simple approach
    const demoRequest = await prisma.post.create({
      data: {
        title: `Demo Request: ${name} - ${company}`,
        content: JSON.stringify({
          name,
          email,
          company,
          industry: industry || 'Not specified',
          preferredDate: preferredDate || 'Not specified',
          message: message || '',
          requestedAt: new Date().toISOString(),
        }),
        published: false,
        authorId: 'demo-request',
      },
    });

    return NextResponse.json({
      status: 'success',
      message: 'Demo request submitted successfully! Our team will reach out within 24 hours.',
      id: demoRequest.id,
    });
  } catch (error: unknown) {
    const message = error instanceof Error ? error.message : 'An unexpected error occurred';
    console.error('Book Demo API error:', message);
    return NextResponse.json(
      { status: 'error', message: 'Failed to submit demo request. Please try again.' },
      { status: 500 }
    );
  }
}
