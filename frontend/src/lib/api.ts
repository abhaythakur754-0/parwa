const API_BASE = 'http://localhost:8100';
const STORAGE_KEY = 'parwa_auth';

function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (typeof window !== 'undefined') {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (parsed.jwtToken) {
          headers['Authorization'] = `Bearer ${parsed.jwtToken}`;
        }
        if (parsed.apiKey) {
          headers['X-API-Key'] = parsed.apiKey;
        }
      }
    } catch {
      // Fall through — no auth headers
    }
  }
  return headers;
}

async function apiGet(path: string, params?: Record<string, string>): Promise<any> {
  const url = new URL(`${API_BASE}${path}`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.set(key, value);
      }
    });
  }
  const res = await fetch(url.toString(), {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API Error ${res.status}: ${text || res.statusText}`);
  }
  const contentType = res.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    return res.json();
  }
  return res.text();
}

async function apiPost(path: string, body: any): Promise<any> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API Error ${res.status}: ${text || res.statusText}`);
  }
  const contentType = res.headers.get('content-type');
  if (contentType && contentType.includes('application/json')) {
    return res.json();
  }
  return res.text();
}

export const jarvisApi = {
  getStatus: (tenantId: string) =>
    apiGet('/api/jarvis/status', { tenant_id: tenantId }),

  getMetrics: (tenantId: string, days?: number) =>
    apiGet('/api/jarvis/metrics', { tenant_id: tenantId, days: String(days || 7) }),

  chat: (tenantId: string, question: string, email?: string, role?: string) =>
    apiPost('/api/jarvis/chat', {
      tenant_id: tenantId,
      question,
      user_email: email || 'admin@parwa.ai',
      user_role: role || 'admin',
    }),

  getNotifications: (tenantId: string, includeResolved?: boolean) =>
    apiGet('/api/jarvis/notifications', {
      tenant_id: tenantId,
      include_resolved: String(includeResolved || false),
    }),

  resolveNotification: (key: string) =>
    apiPost(`/api/jarvis/notifications/${key}/resolve`, {}),

  approveBatch: (tenantId: string, batchKey: string) =>
    apiPost('/api/jarvis/notifications/batch/approve', {
      tenant_id: tenantId,
      batch_key: batchKey,
    }),

  rejectBatch: (tenantId: string, batchKey: string) =>
    apiPost('/api/jarvis/notifications/batch/reject', {
      tenant_id: tenantId,
      batch_key: batchKey,
    }),

  getFlags: (tenantId: string) =>
    apiGet('/api/jarvis/flags', { tenant_id: tenantId }),

  setFlag: (data: any) =>
    apiPost('/api/jarvis/flags', data),

  getQualityScores: (tenantId: string, days?: number) =>
    apiGet('/api/quality/scores', {
      tenant_id: tenantId,
      days: String(days || 7),
    }),

  getQualityAlerts: (tenantId: string) =>
    apiGet('/api/quality/alerts', { tenant_id: tenantId }),

  getRecommendations: (tenantId: string) =>
    apiGet('/api/quality/recommendations', { tenant_id: tenantId }),

  getWeeklyReport: (tenantId: string, days?: number) =>
    apiGet('/api/quality/weekly-report', {
      tenant_id: tenantId,
      days: String(days || 7),
    }),

  getHealthScore: (tenantId: string) =>
    apiGet('/api/quality/health-score', { tenant_id: tenantId }),

  runDriftCheck: (tenantId: string) =>
    apiGet('/api/quality/drift-check', { tenant_id: tenantId }),

  getSLAStatus: (tenantId: string) =>
    apiGet('/api/sla/status', { tenant_id: tenantId }),

  getCustomerHealth: (tenantId: string) =>
    apiGet('/api/jarvis/customer-health', { tenant_id: tenantId }),

  getROI: (tenantId: string) =>
    apiGet('/api/jarvis/roi', { tenant_id: tenantId }),

  getAuditTrail: (tenantId: string, limit?: number) =>
    apiGet('/api/jarvis/audit', {
      tenant_id: tenantId,
      limit: String(limit || 50),
    }),

  getPendingApprovals: (tenantId: string) =>
    apiGet('/api/approvals/pending', { tenant_id: tenantId }),

  pauseAction: (data: any) =>
    apiPost('/api/jarvis/command/pause', data),

  resumeAction: (data: any) =>
    apiPost('/api/jarvis/command/resume', data),

  emergencyShutdown: (tenantId: string, email: string) =>
    apiPost('/api/emergency/shutdown', {
      tenant_id: tenantId,
      user_email: email,
    }),

  submitFeedback: (data: any) =>
    apiPost('/api/quality/feedback', data),

  submitTicket: (data: {
    tenant_id: string;
    query: string;
    channel_type?: string;
    variant_tier?: string;
    customer_context?: Record<string, any>;
    sender?: string;
  }) => apiPost('/api/tickets/submit', data),

  // ── Wave 8 ───────────────────────────────────────────
  listAgents: (tenantId: string) =>
    apiGet('/api/wave8/agents', { tenant_id: tenantId }),

  provisionAgent: (data: { tenant_id: string; command: string; user_email?: string }) =>
    apiPost('/api/wave8/provision', data),

  listSkills: (tenantId: string) =>
    apiGet('/api/wave8/skills', { tenant_id: tenantId }),

  teachSkill: (data: { tenant_id: string; description: string; user_email?: string }) =>
    apiPost('/api/wave8/teach', data),

  copilotDraft: (data: {
    tenant_id: string;
    ticket_id?: string;
    customer_query: string;
    channel?: string;
    user_email?: string;
  }) => apiPost('/api/wave8/copilot/draft', data),

  copilotEdit: (data: { tenant_id: string; draft_id: string; edited_text: string; user_email?: string }) =>
    apiPost('/api/wave8/copilot/edit', data),

  createProactive: (data: {
    tenant_id: string;
    type?: string;
    customer_id?: string;
    reason?: string;
    draft_content?: string;
    user_email?: string;
  }) => apiPost('/api/wave8/proactive', data),

  applyCorrection: (data: {
    tenant_id: string;
    target: string;
    code?: string;
    description?: string;
    user_email?: string;
  }) => apiPost('/api/wave8/correction', data),

  getProvisioningLogs: (tenantId: string) =>
    apiGet('/api/wave8/provisioning-logs', { tenant_id: tenantId }),

  // ── Phase 9: Onboarding ─────────────────────────────────
  getTiers: () =>
    apiGet('/api/tiers'),

  accountSetup: (data: { company_name: string; admin_email: string; password: string; industry: string; company_size: string }) =>
    apiPost('/api/onboarding/account-setup', data),

  selectTier: (data: { tenant_id: string; tier: string; billing_cycle: string }) =>
    apiPost('/api/onboarding/select-tier', data),

  connectIntegration: (data: { tenant_id: string; integration_type: string; credentials: Record<string, string> }) =>
    apiPost('/api/onboarding/connect-integration', data),

  getIntegrations: (tenantId: string) =>
    apiGet('/api/onboarding/integrations', { tenant_id: tenantId }),

  uploadKB: (data: { tenant_id: string; content: string; title: string; category: string }) =>
    apiPost('/api/onboarding/upload-kb', data),

  getKnowledgeBase: (tenantId: string) =>
    apiGet('/api/onboarding/knowledge-base', { tenant_id: tenantId }),

  setPolicy: (data: { tenant_id: string; policies: Record<string, any> }) =>
    apiPost('/api/onboarding/set-policy', data),

  getPolicies: (tenantId: string) =>
    apiGet('/api/onboarding/policies', { tenant_id: tenantId }),

  generateKey: (data: { tenant_id: string; key_type: string; name: string }) =>
    apiPost('/api/onboarding/generate-key', data),

  testTicket: (data: { tenant_id: string; query: string }) =>
    apiPost('/api/onboarding/test-ticket', data),

  getOnboardingStatus: (tenantId: string) =>
    apiGet('/api/onboarding/status', { tenant_id: tenantId }),

  // ── Auth ─────────────────────────────────────────────────
  login: (data: { email: string; password: string }) =>
    apiPost('/api/auth/login', data),

  registerKey: (data: { tenant_id: string; key_type: string; name: string }) =>
    apiPost('/api/auth/register-key', data),

  getKeys: (tenantId: string) =>
    apiGet('/api/auth/keys', { tenant_id: tenantId }),

  revokeKey: (data: { tenant_id: string; key_id: string }) =>
    apiPost('/api/auth/revoke-key', data),
};