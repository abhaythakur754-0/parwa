/**
 * PARWA Onboarding API — Next.js Catch-All Route Handler
 *
 * Proxies onboarding wizard requests to the Python backend.
 * Falls back to local JSON-file-based state when backend is unavailable.
 *
 * Endpoints:
 *   GET  /api/onboarding/state           — Get current onboarding state
 *   POST /api/onboarding/complete-step    — Complete a wizard step
 *   POST /api/onboarding/legal-consent    — Accept legal consents (Step 2)
 *   GET  /api/onboarding/prerequisites    — Check AI activation prerequisites
 *   POST /api/onboarding/activate         — Activate AI assistant (Step 5)
 *   GET  /api/onboarding/first-victory    — Get first victory status
 *   POST /api/onboarding/first-victory    — Mark first victory completed
 */

import { NextRequest, NextResponse } from 'next/server';
import * as fs from 'fs';
import * as path from 'path';

// ── Backend Proxy Configuration ─────────────────────────────────
const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL || '';

async function proxyToBackend(request: NextRequest, pathSegments: string[]): Promise<Response | null> {
  if (!BACKEND_URL) return null;

  const backendPath = `${BACKEND_URL}/api/onboarding/${pathSegments.join('/')}`;
  const url = new URL(request.url);
  const searchParams = url.searchParams.toString();
  const fullUrl = searchParams ? `${backendPath}?${searchParams}` : backendPath;

  try {
    // Use clone() so the body stream is still readable in the local fallback
    const body = ['POST', 'PATCH', 'PUT'].includes(request.method)
      ? await request.clone().arrayBuffer()
      : undefined;

    const headers = new Headers(request.headers);
    headers.delete('host');

    const response = await fetch(fullUrl, {
      method: request.method,
      headers,
      body,
      signal: AbortSignal.timeout(15000),
    });

    // Pass through backend error responses (don't fall back to local on 4xx/5xx)
    if (response.status >= 400) {
      return response;
    }
    return response;
  } catch {
    // Backend genuinely unreachable — fall back to local handling
    return null;
  }
}

// ── Local State Persistence ────────────────────────────────────

const STATE_STORE_PATH = path.join(process.cwd(), '.parwa_onboarding_state.json');

interface OnboardingState {
  current_step: number;
  completed_steps: number[];
  status: 'in_progress' | 'completed';
  first_victory_completed: boolean;
  ai_name: string;
  ai_tone: string;
  ai_response_style: string;
  ai_greeting: string | null;
  legal_consents: {
    accept_terms: boolean;
    accept_privacy: boolean;
    accept_ai_data: boolean;
    accepted_at: string | null;
  } | null;
  created_at: string;
  updated_at: string;
}

function loadState(): OnboardingState {
  try {
    if (fs.existsSync(STATE_STORE_PATH)) {
      const raw = fs.readFileSync(STATE_STORE_PATH, 'utf-8');
      return JSON.parse(raw);
    }
  } catch { /* ignore */ }

  return {
    current_step: 1,
    completed_steps: [],
    status: 'in_progress',
    first_victory_completed: false,
    ai_name: 'Jarvis',
    ai_tone: 'professional',
    ai_response_style: 'concise',
    ai_greeting: null,
    legal_consents: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
}

function saveState(state: OnboardingState): void {
  state.updated_at = new Date().toISOString();
  try {
    fs.writeFileSync(STATE_STORE_PATH, JSON.stringify(state, null, 2), 'utf-8');
  } catch { /* ignore */ }
}

// ── Route Handler ──────────────────────────────────────────────

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path: segments } = await params;
  const pathKey = segments.join('/');

  // Try backend proxy first
  const proxied = await proxyToBackend(request, segments);
  if (proxied) return proxied;

  // Local fallback
  const state = loadState();

  switch (pathKey) {
    case 'state':
      return NextResponse.json(state);

    case 'prerequisites':
      // Check what's missing based on local state
      const missing: string[] = [];
      if (!state.legal_consents) missing.push('Legal consents not accepted');
      return NextResponse.json({
        can_activate: missing.length === 0,
        missing,
      });

    case 'first-victory':
      return NextResponse.json({
        completed: state.first_victory_completed,
        ai_name: state.ai_name,
        ai_greeting: state.ai_greeting,
      });

    default:
      return NextResponse.json({ detail: 'Not found' }, { status: 404 });
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  const { path: segments } = await params;
  const pathKey = segments.join('/');

  // Try backend proxy first
  const proxied = await proxyToBackend(request, segments);
  if (proxied) return proxied;

  // Local fallback
  const state = loadState();

  switch (pathKey) {
    case 'complete-step': {
      const url = new URL(request.url);
      const step = parseInt(url.searchParams.get('step') || '1', 10);
      if (step < 1 || step > 5) {
        return NextResponse.json({ detail: 'Invalid step' }, { status: 400 });
      }
      if (!state.completed_steps.includes(step)) {
        state.completed_steps.push(step);
      }
      if (step >= state.current_step) {
        state.current_step = step + 1;
      }
      if (step === 5) {
        state.status = 'completed';
      }
      saveState(state);
      return NextResponse.json({
        message: `Step ${step} completed successfully.`,
        current_step: state.current_step,
        completed_steps: state.completed_steps,
      });
    }

    case 'legal-consent': {
      const body = await request.json().catch(() => ({}));
      if (!body.accept_terms || !body.accept_privacy || !body.accept_ai_data) {
        return NextResponse.json(
          { detail: 'All consents must be accepted.' },
          { status: 400 }
        );
      }
      state.legal_consents = {
        accept_terms: true,
        accept_privacy: true,
        accept_ai_data: true,
        accepted_at: new Date().toISOString(),
      };
      saveState(state);
      return NextResponse.json({
        message: 'Legal consents accepted successfully.',
        terms_accepted_at: state.legal_consents.accepted_at,
        privacy_accepted_at: state.legal_consents.accepted_at,
        ai_data_accepted_at: state.legal_consents.accepted_at,
      });
    }

    case 'activate': {
      const body = await request.json().catch(() => ({}));
      state.ai_name = body.ai_name || 'Jarvis';
      state.ai_tone = body.ai_tone || 'professional';
      state.ai_response_style = body.ai_response_style || 'concise';
      state.ai_greeting = body.ai_greeting || null;
      state.status = 'completed';
      saveState(state);
      return NextResponse.json({
        ai_name: state.ai_name,
        ai_tone: state.ai_tone,
        ai_response_style: state.ai_response_style,
        ai_greeting: state.ai_greeting,
      });
    }

    case 'first-victory': {
      state.first_victory_completed = true;
      saveState(state);
      return NextResponse.json({
        message: 'First victory celebration completed.',
      });
    }

    default:
      return NextResponse.json({ detail: 'Not found' }, { status: 404 });
  }
}
