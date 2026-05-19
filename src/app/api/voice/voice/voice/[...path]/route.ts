/**
 * PARWA Voice API — Next.js Catch-All Proxy Route
 *
 * Proxies all /api/voice/* requests to the backend FastAPI server
 * at /api/v1/voice/*.
 *
 * Endpoints proxied:
 *   POST /api/voice/call                     → Backend /api/v1/voice/call
 *   GET  /api/voice/calls                    → Backend /api/v1/voice/calls
 *   GET  /api/voice/calls/:id                → Backend /api/v1/voice/calls/:id
 *   POST /api/voice/calls/:id/end            → Backend /api/v1/voice/calls/:id/end
 *   POST /api/voice/calls/:id/transfer       → Backend /api/v1/voice/calls/:id/transfer
 *   GET  /api/voice/conversations            → Backend /api/v1/voice/conversations
 *   GET  /api/voice/conversations/:id        → Backend /api/v1/voice/conversations/:id
 *   GET  /api/voice/config                   → Backend /api/v1/voice/config
 *   POST /api/voice/config                   → Backend /api/v1/voice/config
 *   PUT  /api/voice/config                   → Backend /api/v1/voice/config
 *   DELETE /api/voice/config                 → Backend /api/v1/voice/config
 *   GET  /api/voice/history                  → Backend /api/v1/voice/history
 *   POST /api/voice/test-call                → Backend /api/v1/voice/test-call
 */

import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || '';

async function proxyToBackend(request: NextRequest, pathSegments: string[]): Promise<Response> {
  const backendPath = `${BACKEND_URL}/api/v1/voice/${pathSegments.join('/')}`;
  const url = new URL(request.url);
  const searchParams = url.searchParams.toString();
  const fullUrl = searchParams ? `${backendPath}?${searchParams}` : backendPath;

  // If no backend URL, return mock responses for development
  if (!BACKEND_URL) {
    return mockResponse(pathSegments, request);
  }

  try {
    const body = ['POST', 'PATCH', 'PUT'].includes(request.method)
      ? await request.arrayBuffer()
      : undefined;

    const headers = new Headers(request.headers);
    headers.delete('host');

    const response = await fetch(fullUrl, {
      method: request.method,
      headers,
      body,
      signal: AbortSignal.timeout(20000),
    });

    const data = await response.text();
    return new NextResponse(data, {
      status: response.status,
      headers: {
        'Content-Type': response.headers.get('Content-Type') || 'application/json',
      },
    });
  } catch (err) {
    console.warn('[Voice] Backend proxy failed, using mock:', (err instanceof Error ? err.message : String(err))?.slice(0, 150));
    return mockResponse(pathSegments, request);
  }
}

// ── Mock Responses (for development without backend) ────────────────

function mockResponse(pathSegments: string[], request: NextRequest): NextResponse {
  const method = request.method;
  const path = pathSegments.join('/');

  // POST /call — Initiate outbound call
  if (method === 'POST' && path === 'call') {
    return NextResponse.json({
      id: `call_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      twilio_call_sid: `CA${Math.random().toString(36).slice(2, 34)}`,
      status: 'queued',
      direction: 'outbound',
      to_number: '+919652852014',
      from_number: '+17752583673',
      created_at: new Date().toISOString(),
    });
  }

  // GET /calls — List calls
  if (method === 'GET' && path === 'calls') {
    const now = Date.now();
    const calls = [
      {
        id: `call_mock_1`,
        company_id: 'comp_1',
        twilio_call_sid: 'CAmock1',
        direction: 'outbound',
        from_number: '+17752583673',
        to_number: '+919652852014',
        status: 'in-progress',
        variant_tier: 'parwa',
        intent_detected: 'Refund Inquiry',
        resolution: 'Processing',
        duration_seconds: 154,
        started_at: new Date(now - 154000).toISOString(),
        topics_discussed: ['refund', 'order status', 'shipping delay'],
        satisfaction_score: 4,
        created_at: new Date(now - 154000).toISOString(),
      },
      {
        id: `call_mock_2`,
        company_id: 'comp_1',
        twilio_call_sid: 'CAmock2',
        direction: 'inbound',
        from_number: '+919876543210',
        to_number: '+17752583673',
        status: 'ringing',
        variant_tier: 'parwa_pro',
        duration_seconds: 0,
        started_at: new Date(now - 8000).toISOString(),
        created_at: new Date(now - 8000).toISOString(),
      },
      ...generateMockHistoryCalls(now),
    ];

    return NextResponse.json({
      calls,
      total: calls.length,
      page: 1,
      page_size: 50,
      total_pages: 1,
    });
  }

  // GET /calls/:id — Get single call
  if (method === 'GET' && path.startsWith('calls/') && !path.includes('/end') && !path.includes('/transfer')) {
    return NextResponse.json({
      id: pathSegments[1],
      company_id: 'comp_1',
      twilio_call_sid: 'CAmock1',
      direction: 'outbound',
      from_number: '+17752583673',
      to_number: '+919652852014',
      status: 'completed',
      variant_tier: 'parwa',
      intent_detected: 'Billing Inquiry',
      resolution: 'Resolved — Payment method updated',
      duration_seconds: 204,
      started_at: new Date(Date.now() - 300000).toISOString(),
      ended_at: new Date(Date.now() - 96000).toISOString(),
      recording_url: 'https://api.twilio.com/recordings/REmock',
      transcript_summary: 'Customer inquired about recent billing charge. Agent explained the charge was for the monthly subscription renewal. Customer requested to update payment method which was completed successfully.',
      topics_discussed: ['billing', 'payment method', 'subscription renewal'],
      satisfaction_score: 4,
      created_at: new Date(Date.now() - 300000).toISOString(),
    });
  }

  // POST /calls/:id/end — End call
  if (method === 'POST' && path.includes('/end')) {
    return NextResponse.json({ status: 'ok', message: 'Call ended successfully' });
  }

  // POST /calls/:id/transfer — Transfer call
  if (method === 'POST' && path.includes('/transfer')) {
    return NextResponse.json({ status: 'ok', message: 'Call transferred successfully' });
  }

  // GET /conversations — List conversations
  if (method === 'GET' && path === 'conversations') {
    return NextResponse.json({
      conversations: [
        {
          id: 'conv_mock_1',
          company_id: 'comp_1',
          customer_number: '+919652852014',
          twilio_number: '+17752583673',
          call_count: 3,
          total_duration_seconds: 542,
          last_call_at: new Date().toISOString(),
          is_opted_out: false,
          created_at: new Date(Date.now() - 86400000).toISOString(),
        },
      ],
      total: 1,
    });
  }

  // GET /conversations/:id
  if (method === 'GET' && path.startsWith('conversations/')) {
    return NextResponse.json({
      id: pathSegments[1],
      company_id: 'comp_1',
      customer_number: '+919652852014',
      twilio_number: '+17752583673',
      call_count: 3,
      total_duration_seconds: 542,
      last_call_at: new Date().toISOString(),
      is_opted_out: false,
      created_at: new Date(Date.now() - 86400000).toISOString(),
    });
  }

  // GET /config — Get config
  if (method === 'GET' && path === 'config') {
    return NextResponse.json({
      id: 'vcfg_mock_1',
      company_id: 'comp_1',
      twilio_phone_number: '+17752583673',
      is_enabled: true,
      default_variant: 'parwa',
      max_call_duration_minutes: 30,
      enable_recording: true,
      speech_language: 'en',
      tts_voice: 'Polly.Matthew',
      transfer_number: '+919652852014',
      created_at: new Date(Date.now() - 604800000).toISOString(),
    });
  }

  // POST /config — Create config
  if (method === 'POST' && path === 'config') {
    return NextResponse.json({
      id: 'vcfg_mock_new',
      company_id: 'comp_1',
      twilio_phone_number: '+17752583673',
      is_enabled: true,
      default_variant: 'parwa',
      max_call_duration_minutes: 30,
      enable_recording: true,
      speech_language: 'en',
      tts_voice: 'Polly.Matthew',
      created_at: new Date().toISOString(),
    });
  }

  // PUT /config — Update config
  if (method === 'PUT' && path === 'config') {
    return NextResponse.json({
      id: 'vcfg_mock_1',
      company_id: 'comp_1',
      twilio_phone_number: '+17752583673',
      is_enabled: true,
      default_variant: 'parwa',
      max_call_duration_minutes: 30,
      enable_recording: true,
      speech_language: 'en',
      tts_voice: 'Polly.Matthew',
      created_at: new Date(Date.now() - 604800000).toISOString(),
    });
  }

  // DELETE /config
  if (method === 'DELETE' && path === 'config') {
    return NextResponse.json({ status: 'ok' });
  }

  // GET /history — Call history
  if (method === 'GET' && path === 'history') {
    const now = Date.now();
    const calls = generateMockHistoryCalls(now);
    return NextResponse.json({
      calls,
      total: calls.length,
      page: 1,
      page_size: 20,
      total_pages: 1,
    });
  }

  // POST /test-call — Test call
  if (method === 'POST' && path === 'test-call') {
    return NextResponse.json({
      id: `call_test_${Date.now()}`,
      twilio_call_sid: `CAtest${Math.random().toString(36).slice(2, 10)}`,
      status: 'queued',
      message: 'Test call initiated successfully',
    });
  }

  return NextResponse.json({ error: { code: 'NOT_FOUND', message: 'Voice endpoint not found' } }, { status: 404 });
}

// ── Generate mock history calls ─────────────────────────────────────

function generateMockHistoryCalls(now: number) {
  const statuses = ['completed', 'failed', 'busy', 'no-answer', 'completed', 'completed', 'completed'];
  const directions: Array<'inbound' | 'outbound'> = ['inbound', 'outbound', 'inbound', 'outbound'];
  const intents = ['Refund Inquiry', 'Shipping Status', 'Billing Question', 'Account Issue', 'Technical Support', 'Order Update', 'Return Request'];
  const variants = ['parwa', 'parwa_pro', 'parwa_high', 'parwa', 'parwa_pro'];
  const numbers = ['+919652852014', '+919876543210', '+918765432109', '+919123456789'];

  return Array.from({ length: 7 }, (_, i) => {
    const status = statuses[i];
    const duration = status === 'completed' ? Math.floor(Math.random() * 300) + 30 : 0;
    const startedAt = new Date(now - (i + 1) * 600000 - Math.random() * 300000);
    const endedAt = status === 'completed' ? new Date(startedAt.getTime() + duration * 1000) : undefined;

    return {
      id: `call_hist_${i + 1}`,
      company_id: 'comp_1',
      twilio_call_sid: `CAhist${i}${Math.random().toString(36).slice(2, 8)}`,
      direction: directions[i % 2],
      from_number: directions[i % 2] === 'outbound' ? '+17752583673' : numbers[i % numbers.length],
      to_number: directions[i % 2] === 'outbound' ? numbers[i % numbers.length] : '+17752583673',
      status,
      variant_tier: variants[i % variants.length],
      intent_detected: status === 'completed' ? intents[i % intents.length] : undefined,
      resolution: status === 'completed' ? 'Resolved' : undefined,
      duration_seconds: duration,
      started_at: startedAt.toISOString(),
      ended_at: endedAt?.toISOString(),
      topics_discussed: status === 'completed' ? [intents[i % intents.length]?.toLowerCase().replace(' inquiry', '').replace(' question', '')] : undefined,
      satisfaction_score: status === 'completed' ? Math.floor(Math.random() * 2) + 3 : undefined,
      created_at: startedAt.toISOString(),
    };
  });
}

// ── Route Handlers ──────────────────────────────────────────────────

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxyToBackend(request, path);
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxyToBackend(request, path);
}

export async function PUT(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxyToBackend(request, path);
}

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  return proxyToBackend(request, path);
}
