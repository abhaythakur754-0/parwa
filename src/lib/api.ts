import type { AuthType } from "./integration-catalog";

// ==========================================
// BFF API Client - All calls go through Next.js API routes
// Never calls FastAPI (port 8000) directly
// ==========================================

interface ApiResponse<T = unknown> {
  data?: T;
  error?: string;
  status: number;
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  try {
    const res = await fetch(path, {
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      ...options,
    });

    const data = await res.json();
    return { data, status: res.status };
  } catch {
    return { error: "Network error. Please try again.", status: 503 };
  }
}

// ==========================================
// Auth API
// ==========================================
export const auth = {
  register: (email: string, name: string, password: string) =>
    request("/api/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, name, password }),
    }),

  login: (email: string, password: string) =>
    request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () => request("/api/auth/me"),

  refresh: (refreshToken: string) =>
    request("/api/auth/refresh", {
      method: "POST",
      body: JSON.stringify({ refresh_token: refreshToken }),
    }),

  logout: () =>
    request("/api/auth/logout", { method: "POST" }),
};

// ==========================================
// Onboarding API
// ==========================================
export const onboarding = {
  getState: () => request("/api/onboarding"),

  setIndustryVariant: (industry: string, variant: string) =>
    request("/api/onboarding/industry-variant", {
      method: "POST",
      body: JSON.stringify({ industry, variant }),
    }),

  acceptLegal: (accepted: boolean) =>
    request("/api/onboarding/legal-consent", {
      method: "POST",
      body: JSON.stringify({ accepted }),
    }),

  completeStep: (step: number) =>
    request("/api/onboarding/complete-step", {
      method: "POST",
      body: JSON.stringify({ step }),
    }),

  activate: () =>
    request("/api/onboarding/activate", { method: "POST" }),

  getFirstVictory: () => request("/api/onboarding/first-victory"),

  getPrerequisites: () => request("/api/onboarding/prerequisites"),
};

// ==========================================
// Integrations API
// ==========================================
export const integrations = {
  getCatalog: (industry?: string) =>
    request(`/api/integrations/catalog${industry ? `?industry=${industry}` : ""}`),

  connect: (integrationId: string, authType: AuthType, credentials: Record<string, string>) =>
    request("/api/integrations/connect", {
      method: "POST",
      body: JSON.stringify({ integration_id: integrationId, auth_type: authType, credentials }),
    }),

  disconnect: (integrationId: string) =>
    request("/api/integrations/disconnect", {
      method: "POST",
      body: JSON.stringify({ integration_id: integrationId }),
    }),

  test: (integrationId: string) =>
    request("/api/integrations/test", {
      method: "POST",
      body: JSON.stringify({ integration_id: integrationId }),
    }),

  getHealth: () => request("/api/integrations/health"),

  list: () => request("/api/integrations/list"),
};

// ==========================================
// API Keys API (PHASE 13)
// ==========================================
export const apiKeys = {
  store: (integrationId: string, authType: AuthType, credentials: Record<string, string>) =>
    request("/api/api-keys/store", {
      method: "POST",
      body: JSON.stringify({ integration_id: integrationId, auth_type: authType, credentials }),
    }),

  rotate: (integrationId: string, newCredentials: Record<string, string>) =>
    request("/api/api-keys/rotate", {
      method: "POST",
      body: JSON.stringify({ integration_id: integrationId, new_credentials: newCredentials }),
    }),

  revoke: (integrationId: string) =>
    request("/api/api-keys/revoke", {
      method: "DELETE",
      body: JSON.stringify({ integration_id: integrationId }),
    }),

  test: (integrationId: string) =>
    request("/api/api-keys/test", {
      method: "POST",
      body: JSON.stringify({ integration_id: integrationId }),
    }),

  list: () => request("/api/api-keys/list"),
};

// ==========================================
// Audit API (Phase 9)
// ==========================================
export const audit = {
  getEntries: (params?: { category?: string; severity?: string; date_from?: string; date_to?: string; limit?: number; offset?: number }) => {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) searchParams.set(key, String(value));
      });
    }
    return request(`/api/audit/entries?${searchParams.toString()}`);
  },

  getStats: () => request("/api/audit/stats"),

  exportLogs: (format: "json" | "csv" = "json") =>
    request(`/api/audit/export?format=${format}`),

  getAlerts: () => request("/api/audit/alerts"),

  log: (action: string, actor?: string, resourceType?: string, resourceId?: string, details?: Record<string, unknown>, severity: string = "info") =>
    request("/api/audit/log", {
      method: "POST",
      body: JSON.stringify({ action, actor, resource_type: resourceType, resource_id: resourceId, details, severity }),
    }),
};

// ==========================================
// Variants API (PHASE 14)
// ==========================================
export const variants = {
  list: () => request("/api/variants/list"),

  add: (variantType: string) =>
    request("/api/variants/add", {
      method: "POST",
      body: JSON.stringify({ variant_type: variantType }),
    }),

  remove: (variantId: string) =>
    request("/api/variants/remove", {
      method: "DELETE",
      body: JSON.stringify({ variant_id: variantId }),
    }),

  getUsage: () => request("/api/variants/usage"),

  routeTicket: (intent: string, complexityScore: number) =>
    request("/api/variants/route-ticket", {
      method: "POST",
      body: JSON.stringify({ intent, complexity_score: complexityScore }),
    }),
};

// ==========================================
// AI Tools API (PHASE 14)
// ==========================================
export const aiTools = {
  getAvailable: () => request("/api/ai-tools/available"),

  selectTool: (ticketIntent: string) =>
    request("/api/ai-tools/select", {
      method: "POST",
      body: JSON.stringify({ ticket_intent: ticketIntent }),
    }),

  getPrompt: () => request("/api/ai-tools/prompt"),
};

export const api = {
  auth,
  onboarding,
  integrations,
  apiKeys,
  audit,
  variants,
  aiTools,
};
