/**
 * PARWA Demo Variant API Client
 *
 * Client-side API functions for the $1 Demo Pack variant system.
 * Uses fetch to call /api/demo/* endpoints.
 */

import type {
  DemoVariantListResponse,
  DemoSessionCreateRequest,
  DemoSessionCreateResponse,
  DemoKnowledgeBaseListResponse,
  DemoKnowledgeBaseUploadResponse,
  DemoUsageResponse,
  DemoBillingResponse,
  DemoPaymentRequest,
  DemoPaymentResponse,
  DemoBillSummary,
} from '@/types/demo-variant';

const API_BASE = '/api/demo';

async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  };

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      (errorData as { error?: { message?: string } })?.error?.message ||
      `API error: ${response.status}`,
    );
  }

  return response.json() as Promise<T>;
}

// ── Variant Endpoints ────────────────────────────────────────────

export async function listVariants(): Promise<DemoVariantListResponse> {
  return apiFetch<DemoVariantListResponse>('/variants');
}

// ── Session Endpoints ────────────────────────────────────────────

export async function createDemoSession(
  data: DemoSessionCreateRequest,
): Promise<DemoSessionCreateResponse> {
  return apiFetch<DemoSessionCreateResponse>('/session', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getDemoSession(sessionId: string): Promise<DemoSessionCreateResponse> {
  return apiFetch<DemoSessionCreateResponse>(`/session?session_id=${sessionId}`);
}

// ── Knowledge Base Endpoints ─────────────────────────────────────

export async function listKnowledgeBases(): Promise<DemoKnowledgeBaseListResponse> {
  return apiFetch<DemoKnowledgeBaseListResponse>('/knowledge-base');
}

export async function uploadKnowledgeBase(
  file: File,
  industry?: string,
): Promise<DemoKnowledgeBaseUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  if (industry) formData.append('industry', industry);

  const url = `${API_BASE}/knowledge-base`;
  const response = await fetch(url, {
    method: 'POST',
    body: formData,
    credentials: 'include',
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(
      (errorData as { error?: { message?: string } })?.error?.message ||
      `Upload failed: ${response.status}`,
    );
  }

  return response.json() as Promise<DemoKnowledgeBaseUploadResponse>;
}

// ── Usage Endpoints ──────────────────────────────────────────────

export async function getDemoUsage(sessionId: string): Promise<DemoUsageResponse> {
  return apiFetch<DemoUsageResponse>(`/usage?session_id=${sessionId}`);
}

// ── Billing Endpoints ────────────────────────────────────────────

export async function getDemoBilling(sessionId: string): Promise<DemoBillingResponse> {
  return apiFetch<DemoBillingResponse>(`/billing?session_id=${sessionId}`);
}

export async function calculateBillEstimate(
  variantId: string,
  industry: string,
  ticketVolume: number,
): Promise<DemoBillSummary> {
  return apiFetch<DemoBillSummary>('/billing/estimate', {
    method: 'POST',
    body: JSON.stringify({ variant_id: variantId, industry, ticket_volume: ticketVolume }),
  });
}

// ── Payment Endpoints ────────────────────────────────────────────

export async function createDemoPayment(
  data: DemoPaymentRequest,
): Promise<DemoPaymentResponse> {
  return apiFetch<DemoPaymentResponse>('/billing/payment', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
