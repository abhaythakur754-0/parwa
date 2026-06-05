/**
 * PARWA Demo Usage API — GET /api/demo/usage
 *
 * Returns usage stats for a demo session.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getDemoSession, getUsageEvents } from '@/lib/demo-store';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const sessionId = searchParams.get('session_id');

    if (!sessionId) {
      return NextResponse.json(
        { error: { code: 'MISSING_SESSION_ID', message: 'session_id is required' } },
        { status: 400 },
      );
    }

    const session = getDemoSession(sessionId);
    if (!session) {
      return NextResponse.json(
        { error: { code: 'SESSION_NOT_FOUND', message: 'Demo session not found' } },
        { status: 404 },
      );
    }

    const events = getUsageEvents(sessionId);
    const userMessages = events.filter((e) => e.type === 'user_message').length;
    const jarvisMessages = events.filter((e) => e.type === 'jarvis_message').length;
    const callSeconds = events.filter((e) => e.type === 'call_second').length;

    const usage = {
      session_id: sessionId,
      user_messages_sent: session.messages_used,
      user_messages_limit: session.messages_limit,
      jarvis_messages_sent: jarvisMessages,
      call_seconds_used: session.call_seconds_used,
      call_seconds_limit: session.call_seconds_limit,
      is_call_available: session.call_seconds_used < session.call_seconds_limit,
      is_messages_remaining: session.messages_used < session.messages_limit,
      percentage_used: Math.round((session.messages_used / session.messages_limit) * 100),
    };

    return NextResponse.json({
      usage,
      events: events.slice(-20), // Last 20 events
    });
  } catch (error) {
    return NextResponse.json(
      { error: { code: 'USAGE_GET_ERROR', message: 'Failed to get usage stats' } },
      { status: 500 },
    );
  }
}
