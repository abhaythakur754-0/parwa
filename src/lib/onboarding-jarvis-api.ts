/**
 * PARWA Onboarding Jarvis — API Client
 *
 * API client for the pre-purchase demo chat experience.
 * All endpoints go through /api/onboarding-jarvis/
 */

import {
  OnboardingSession,
  OnboardingMessage,
  OtpState,
} from '@/types/onboarding-jarvis';

const API_BASE = '/api/onboarding-jarvis';

async function apiCall<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.error?.message || `API error ${res.status}`);
  }

  return res.json();
}

/** Create or resume an onboarding session */
export async function createOrResumeSession(
  entrySource = 'direct',
  entryParams?: Record<string, any>,
): Promise<OnboardingSession> {
  return apiCall<OnboardingSession>('/session', {
    method: 'POST',
    body: JSON.stringify({ entry_source: entrySource, entry_params: entryParams }),
  });
}

/** Get current session */
export async function getSession(sessionId: string): Promise<OnboardingSession> {
  return apiCall<OnboardingSession>(`/session?session_id=${sessionId}`);
}

/** Get paginated chat history */
export async function getHistory(
  sessionId: string,
  limit = 50,
  offset = 0,
): Promise<{ messages: OnboardingMessage[]; total: number; has_more: boolean }> {
  return apiCall(`/history?session_id=${sessionId}&limit=${limit}&offset=${offset}`);
}

/** Send a message and get AI response */
export async function sendMessage(
  sessionId: string,
  message: string,
  channel = 'chat',
): Promise<{
  session_id: string;
  content: string;
  message_type: string;
  function_called: string | null;
  function_result: Record<string, any> | null;
  card_type: string;
  card_data: Record<string, any>;
  stage: string;
  remaining_today: number;
  metadata: Record<string, any>;
}> {
  return apiCall('/message', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, message, channel }),
  });
}

/** Update session context (partial merge) */
export async function updateContext(
  sessionId: string,
  updates: Record<string, any>,
): Promise<OnboardingSession> {
  return apiCall<OnboardingSession>(`/context?session_id=${sessionId}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
}

/** Set entry source from URL params */
export async function setEntry(
  entrySource: string,
  entryParams?: Record<string, any>,
): Promise<OnboardingSession> {
  return apiCall<OnboardingSession>('/entry', {
    method: 'POST',
    body: JSON.stringify({ entry_source: entrySource, entry_params: entryParams }),
  });
}

/** Purchase $1 demo pack */
export async function purchaseDemoPack(sessionId: string): Promise<Record<string, any>> {
  return apiCall(`/demo-pack/purchase?session_id=${sessionId}`, { method: 'POST', body: JSON.stringify({}) });
}

/** Get demo pack status */
export async function getDemoPackStatus(sessionId: string): Promise<Record<string, any>> {
  return apiCall(`/demo-pack/status?session_id=${sessionId}`);
}

/** Send OTP to business email */
export async function sendOtp(
  sessionId: string,
  email: string,
): Promise<{ message: string; status: string; attempts_remaining?: number; expires_at?: string }> {
  return apiCall(`/verify/send-otp?session_id=${sessionId}`, {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
}

/** Verify OTP code */
export async function verifyOtp(
  sessionId: string,
  email: string,
  code: string,
): Promise<{ message: string; status: string; attempts_remaining?: number }> {
  return apiCall(`/verify/verify-otp?session_id=${sessionId}`, {
    method: 'POST',
    body: JSON.stringify({ email, code }),
  });
}

/** Create Paddle checkout session */
export async function createPayment(
  sessionId: string,
  planId: string,
  variantIds: string[],
  email: string,
  billingPeriod = 'monthly',
): Promise<Record<string, any>> {
  return apiCall(`/payment/create?session_id=${sessionId}`, {
    method: 'POST',
    body: JSON.stringify({ plan_id: planId, variant_ids: variantIds, email, billing_period: billingPeriod }),
  });
}

/** Execute handoff to customer care */
export async function executeHandoff(
  sessionId: string,
): Promise<{ handoff_completed: boolean; new_session_id?: string; handoff_at?: string }> {
  return apiCall(`/handoff?session_id=${sessionId}`, { method: 'POST', body: JSON.stringify({}) });
}
