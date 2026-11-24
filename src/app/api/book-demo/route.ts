import { NextRequest, NextResponse } from 'next/server';
import { PrismaClient } from '@prisma/client';

const prisma = new PrismaClient();
const MAX_BODY_BYTES = 16 * 1024;
const MAX_REQUESTS_PER_EMAIL_PER_HOUR = 3;

export async function POST(req: NextRequest) {
  try {
    const contentLength = Number(req.headers.get('content-length') || 0);
    if (contentLength > MAX_BODY_BYTES) {
      return NextResponse.json(
        { status: 'error', message: 'Request is too large.' },
        { status: 413, headers: { 'Cache-Control': 'no-store' } }
      );
    }

    const body = await req.json();
    const name = typeof body?.name === 'string' ? body.name.trim() : '';
    const email = typeof body?.email === 'string' ? body.email.trim().toLowerCase() : '';
    const company = typeof body?.company === 'string' ? body.company.trim() : '';
    const industry = typeof body?.industry === 'string' ? body.industry.trim() : '';
    const preferredDate = typeof body?.preferredDate === 'string' ? body.preferredDate.trim() : '';
    const message = typeof body?.message === 'string' ? body.message.trim() : '';

    if (!name || !email || !company) {
      return NextResponse.json(
        { status: 'error', message: 'Name, email, and company are required.' },
        { status: 400 }
      );
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return NextResponse.json(
        { status: 'error', message: 'Please enter a valid email address.' },
        { status: 400 }
      );
    }

    if (
      name.length > 120 ||
      email.length > 254 ||
      company.length > 120 ||
      industry.length > 120 ||
      preferredDate.length > 80 ||
      message.length > 2000
    ) {
      return NextResponse.json(
        { status: 'error', message: 'One or more fields exceed the allowed length.' },
        { status: 400 }
      );
    }

    // A small per-email limit prevents simple automated form flooding while
    // keeping the form public. The database count works across app instances.
    const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);
    const recentRequests = await prisma.post.count({
      where: {
        title: { startsWith: 'Demo Request:' },
        content: { contains: email },
        createdAt: { gte: oneHourAgo },
      },
    });
    if (recentRequests >= MAX_REQUESTS_PER_EMAIL_PER_HOUR) {
      return NextResponse.json(
        { status: 'error', message: 'Too many demo requests. Please try again later.' },
        {
          status: 429,
          headers: { 'Retry-After': '3600', 'Cache-Control': 'no-store' },
        }
      );
    }

    // Keep using the existing support-request storage, but do not invent a
    // foreign-key user ID for this anonymous public request.
    const demoRequest = await prisma.post.create({
      data: {
        title: `Demo Request: ${name} - ${company}`,
        content: JSON.stringify({
          name,
          email,
          company,
          industry: industry || 'Not specified',
          preferredDate: preferredDate || 'Not specified',
          message,
          requestedAt: new Date().toISOString(),
        }),
        published: false,
        authorId: null,
      },
    });

    return NextResponse.json(
      {
        status: 'success',
        message: 'Demo request submitted successfully! Our team will reach out within 24 hours.',
        id: demoRequest.id,
      },
      { headers: { 'Cache-Control': 'no-store' } }
    );
  } catch (error: unknown) {
    console.error('Book Demo API error:', error instanceof Error ? error.message : 'Unknown error');
    return NextResponse.json(
      { status: 'error', message: 'Failed to submit demo request. Please try again.' },
      { status: 500, headers: { 'Cache-Control': 'no-store' } }
    );
  }
}
