/**
 * PARWA Voice API Client
 *
 * Typed API client for voice channel endpoints.
 * All requests go through the Next.js proxy route at /api/voice/*.
 */

import type {
  VoiceCall,
  VoiceConversation,
  VoiceChannelConfig,
  InitiateCallRequest,
  InitiateCallResponse,
  ListCallsParams,
  ListCallsResponse,
  TransferCallRequest,
  CallHistoryParams,
  CallHistoryResponse,
  CreateVoiceConfigRequest,
  UpdateVoiceConfigRequest,
  TestCallRequest,
  TestCallResponse,
} from '@/types/voice';

// ── Base Helper ─────────────────────────────────────────────────────

const BASE = '/api/voice';

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${BASE}${path}`;
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  };

  const res = await fetch(url, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (!res.ok) {
    let message = `Voice API error: ${res.status}`;
    try {
      const body = await res.json();
      message = body?.error?.message || body?.detail || message;
    } catch {
      // ignore parse error
    }
    throw new Error(message);
  }

  return res.json() as Promise<T>;
}

// ── Voice API ───────────────────────────────────────────────────────

export const voiceApi = {
  // ── Call Management ──────────────────────────────────────────────

  /** Initiate an outbound call */
  initiateCall: (data: InitiateCallRequest): Promise<InitiateCallResponse> =>
    request('/call', { method: 'POST', body: JSON.stringify(data) }),

  /** List voice calls with pagination */
  listCalls: (params?: ListCallsParams): Promise<ListCallsResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.page_size) searchParams.set('page_size', String(params.page_size));
    if (params?.direction) searchParams.set('direction', params.direction);
    if (params?.status) searchParams.set('status', params.status);
    const qs = searchParams.toString();
    return request(`/calls${qs ? `?${qs}` : ''}`);
  },

  /** Get a single call by ID */
  getCall: (id: string): Promise<VoiceCall> =>
    request(`/calls/${encodeURIComponent(id)}`),

  /** End an active call */
  endCall: (id: string): Promise<{ status: string; message: string }> =>
    request(`/calls/${encodeURIComponent(id)}/end`, { method: 'POST' }),

  /** Transfer an active call to another number */
  transferCall: (id: string, data: TransferCallRequest): Promise<{ status: string; message: string }> =>
    request(`/calls/${encodeURIComponent(id)}/transfer`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // ── Conversations ────────────────────────────────────────────────

  /** List voice conversations */
  listConversations: (params?: {
    page?: number;
    page_size?: number;
    is_opted_out?: boolean;
  }): Promise<{ conversations: VoiceConversation[]; total: number }> => {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.page_size) searchParams.set('page_size', String(params.page_size));
    if (params?.is_opted_out !== undefined) searchParams.set('is_opted_out', String(params.is_opted_out));
    const qs = searchParams.toString();
    return request(`/conversations${qs ? `?${qs}` : ''}`);
  },

  /** Get a single conversation */
  getConversation: (id: string): Promise<VoiceConversation> =>
    request(`/conversations/${encodeURIComponent(id)}`),

  // ── Config ───────────────────────────────────────────────────────

  /** Get voice channel config */
  getConfig: (): Promise<VoiceChannelConfig> =>
    request('/config'),

  /** Create voice channel config */
  createConfig: (data: CreateVoiceConfigRequest): Promise<VoiceChannelConfig> =>
    request('/config', { method: 'POST', body: JSON.stringify(data) }),

  /** Update voice channel config */
  updateConfig: (data: UpdateVoiceConfigRequest): Promise<VoiceChannelConfig> =>
    request('/config', { method: 'PUT', body: JSON.stringify(data) }),

  /** Delete voice channel config */
  deleteConfig: (): Promise<{ status: string }> =>
    request('/config', { method: 'DELETE' }),

  // ── History ──────────────────────────────────────────────────────

  /** Get call history */
  getHistory: (params?: CallHistoryParams): Promise<CallHistoryResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.phone_number) searchParams.set('phone_number', params.phone_number);
    if (params?.direction) searchParams.set('direction', params.direction);
    if (params?.status) searchParams.set('status', params.status);
    if (params?.page) searchParams.set('page', String(params.page));
    if (params?.page_size) searchParams.set('page_size', String(params.page_size));
    const qs = searchParams.toString();
    return request(`/history${qs ? `?${qs}` : ''}`);
  },

  // ── Test Call ────────────────────────────────────────────────────

  /** Make a test call (rate limited) */
  testCall: (data: TestCallRequest): Promise<TestCallResponse> =>
    request('/test-call', { method: 'POST', body: JSON.stringify(data) }),
};
