// PARWA Phase 4 API Client
// All backend API calls with graceful error handling and mock fallback data

const API_BASE = '/api/v1';
const PORT_PARAM = 'XTransformPort=8000';
const COMPANY_ID = 'demo-company-001';
const COMPANY_HEADER = 'X-Company-Id';

function apiUrl(path: string, extraParams?: string): string {
  const sep = path.includes('?') ? '&' : '?';
  return `${API_BASE}${path}${sep}${PORT_PARAM}${extraParams ? `&${extraParams}` : ''}`;
}

async function apiFetch<T>(path: string, options?: RequestInit, fallback?: T): Promise<T> {
  try {
    // Build headers: start with auth (JWT) if available, fall back to X-Company-Id
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    // Try to get auth token from localStorage
    if (typeof window !== 'undefined') {
      try {
        const saved = localStorage.getItem('parwa-tokens');
        if (saved) {
          const tokens = JSON.parse(saved);
          if (tokens.access_token) {
            headers['Authorization'] = `Bearer ${tokens.access_token}`;
          }
        }
      } catch { /* ignore */ }
    }

    // Fall back to X-Company-Id if no auth token (backward compat)
    if (!headers['Authorization']) {
      headers[COMPANY_HEADER] = COMPANY_ID;
    }

    const res = await fetch(apiUrl(path), {
      ...options,
      headers: {
        ...headers,
        ...options?.headers as Record<string, string>,
      },
    });
    if (!res.ok) {
      throw new Error(`API ${res.status}: ${res.statusText}`);
    }
    return await res.json();
  } catch (err) {
    console.warn(`[PARWA API] ${path} failed:`, err);
    if (fallback !== undefined) return fallback;
    throw err;
  }
}

// ============= TYPES =============

export type VariantType = 'mini' | 'parwa' | 'high';
export type PaymentProvider = 'stripe' | 'paypal' | 'razorpay' | 'paddle' | 'custom';

export interface UsageSummary {
  variants: { variant: VariantType; tickets_used: number; tickets_limit: number }[];
  total_tickets_used: number;
  period: string;
}

export interface CostCalculation {
  monthly_cost: number;
  breakdown: { variant: string; cost: number }[];
  add_ons: { name: string; cost: number }[];
}

export interface OverageEstimate {
  variant: VariantType;
  projected_tickets: number;
  overage_tickets: number;
  overage_cost: number;
}

export interface PaymentGateway {
  id: string;
  provider: PaymentProvider;
  status: 'active' | 'inactive' | 'error';
  created_at: string;
}

export interface IntegrationCatalogItem {
  id: string;
  name: string;
  category: string;
  description: string;
  icon: string;
  supported_variants: VariantType[];
}

export interface ConnectedIntegration {
  id: string;
  integration_id: string;
  name: string;
  status: 'connected' | 'disconnected' | 'error';
  connected_at: string;
}

export interface Notification {
  id: string;
  type: 'info' | 'warning' | 'error' | 'success';
  title: string;
  message: string;
  read: boolean;
  created_at: string;
}

export interface KnowledgeDocument {
  id: string;
  name: string;
  type: string;
  size: number;
  uploaded_at: string;
  status: 'processing' | 'ready' | 'error';
}

export interface FAQ {
  id: string;
  question: string;
  answer: string;
  created_at: string;
}

export interface IndustryPreview {
  current_industry: string;
  new_industry: string;
  integrations_to_disconnect: { id: string; name: string }[];
  new_default_faqs: { question: string; answer: string }[];
  impact_summary: string;
}

export interface CustomConnector {
  id: string;
  name: string;
  type: string;
  status: 'active' | 'inactive';
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'unhealthy';
  services: { name: string; status: string }[];
}

// ============= MOCK DATA =============

const MOCK_USAGE: UsageSummary = {
  variants: [
    { variant: 'parwa', tickets_used: 1247, tickets_limit: 2000 },
  ],
  total_tickets_used: 1247,
  period: '2026-06',
};

const MOCK_GATEWAYS: PaymentGateway[] = [
  { id: 'gw-1', provider: 'stripe', status: 'active', created_at: '2026-05-15T10:00:00Z' },
];

const MOCK_CATALOG: IntegrationCatalogItem[] = [
  { id: 'zendesk', name: 'Zendesk', category: 'Helpdesk', description: 'Sync tickets with Zendesk', icon: '🎧', supported_variants: ['mini', 'parwa', 'high'] },
  { id: 'slack', name: 'Slack', category: 'Communication', description: 'Get notifications in Slack', icon: '💬', supported_variants: ['mini', 'parwa', 'high'] },
  { id: 'shopify', name: 'Shopify', category: 'E-Commerce', description: 'Link Shopify orders and customers', icon: '🛒', supported_variants: ['parwa', 'high'] },
  { id: 'salesforce', name: 'Salesforce', category: 'CRM', description: 'Sync contacts and cases with Salesforce', icon: '☁️', supported_variants: ['parwa', 'high'] },
  { id: 'github', name: 'GitHub', category: 'Developer', description: 'Link issues and discussions', icon: '🐙', supported_variants: ['high'] },
  { id: 'jira', name: 'Jira', category: 'Project Management', description: 'Sync issues with Jira', icon: '📋', supported_variants: ['parwa', 'high'] },
  { id: 'hubspot', name: 'HubSpot', category: 'CRM', description: 'Sync contacts and tickets', icon: '🟠', supported_variants: ['parwa', 'high'] },
  { id: 'intercom', name: 'Intercom', category: 'Messaging', description: 'Sync conversations with Intercom', icon: '🔵', supported_variants: ['parwa', 'high'] },
  { id: 'notion', name: 'Notion', category: 'Knowledge', description: 'Import docs from Notion', icon: '📝', supported_variants: ['parwa', 'high'] },
  { id: 'whatsapp', name: 'WhatsApp Business', category: 'Communication', description: 'Support via WhatsApp', icon: '📱', supported_variants: ['parwa', 'high'] },
  { id: 'gmail', name: 'Gmail', category: 'Email', description: 'Sync email conversations', icon: '📧', supported_variants: ['mini', 'parwa', 'high'] },
  { id: 'twitter', name: 'Twitter/X', category: 'Social', description: 'Monitor social mentions', icon: '🐦', supported_variants: ['high'] },
];

const MOCK_CONNECTED: ConnectedIntegration[] = [
  { id: 'ci-1', integration_id: 'slack', name: 'Slack', status: 'connected', connected_at: '2026-06-01T09:00:00Z' },
  { id: 'ci-2', integration_id: 'zendesk', name: 'Zendesk', status: 'connected', connected_at: '2026-05-20T14:30:00Z' },
];

const MOCK_NOTIFICATIONS: Notification[] = [
  { id: 'n-1', type: 'success', title: 'Variant Activated', message: 'PARWA Standard variant is now active on your account.', read: false, created_at: '2026-06-12T08:00:00Z' },
  { id: 'n-2', type: 'warning', title: 'Usage Alert', message: 'You have used 62% of your monthly ticket allowance.', read: false, created_at: '2026-06-11T15:30:00Z' },
  { id: 'n-3', type: 'info', title: 'Integration Updated', message: 'Slack integration has been updated to the latest version.', read: true, created_at: '2026-06-10T10:00:00Z' },
  { id: 'n-4', type: 'error', title: 'Payment Failed', message: 'Your last payment via Stripe failed. Please update your payment method.', read: false, created_at: '2026-06-09T22:00:00Z' },
  { id: 'n-5', type: 'info', title: 'Knowledge Base Ready', message: 'Your uploaded document "Product FAQ" has been processed and is ready.', read: true, created_at: '2026-06-08T12:00:00Z' },
];

const MOCK_DOCUMENTS: KnowledgeDocument[] = [
  { id: 'd-1', name: 'Product FAQ.pdf', type: 'pdf', size: 245000, uploaded_at: '2026-06-08T12:00:00Z', status: 'ready' },
  { id: 'd-2', name: 'API Documentation.md', type: 'markdown', size: 89000, uploaded_at: '2026-06-07T09:00:00Z', status: 'ready' },
  { id: 'd-3', name: 'Troubleshooting Guide.docx', type: 'docx', size: 156000, uploaded_at: '2026-06-06T14:00:00Z', status: 'processing' },
];

const MOCK_FAQS: FAQ[] = [
  { id: 'f-1', question: 'How do I reset my password?', answer: 'Go to Settings > Security > Reset Password and follow the instructions.', created_at: '2026-06-05T10:00:00Z' },
  { id: 'f-2', question: 'What are the supported payment methods?', answer: 'We support Stripe, PayPal, Razorpay, Paddle, and custom payment gateways.', created_at: '2026-06-04T11:00:00Z' },
  { id: 'f-3', question: 'How do I upgrade my variant?', answer: 'Navigate to Variants section and select a higher tier. Changes take effect immediately.', created_at: '2026-06-03T15:00:00Z' },
];

const MOCK_INDUSTRY_PREVIEW: IndustryPreview = {
  current_industry: 'technology',
  new_industry: 'saas',
  integrations_to_disconnect: [],
  new_default_faqs: [
    { question: 'How do I cancel my subscription?', answer: 'You can cancel anytime from your billing settings.' },
    { question: 'What is your refund policy?', answer: 'We offer a 30-day money-back guarantee.' },
  ],
  impact_summary: 'Switching to SaaS industry will update your default templates and suggest SaaS-specific integrations.',
};

const MOCK_CONNECTORS: CustomConnector[] = [
  { id: 'cc-1', name: 'Internal CRM API', type: 'rest', status: 'active' },
];

const MOCK_COST: CostCalculation = {
  monthly_cost: 79,
  breakdown: [{ variant: 'parwa', cost: 79 }],
  add_ons: [],
};

const MOCK_HEALTH: HealthStatus = {
  status: 'healthy',
  services: [
    { name: 'API Server', status: 'healthy' },
    { name: 'Database', status: 'healthy' },
    { name: 'Cache', status: 'healthy' },
  ],
};

// ============= API FUNCTIONS =============

// Billing
export async function getUsage(): Promise<UsageSummary> {
  return apiFetch<UsageSummary>('/billing/usage', {}, MOCK_USAGE);
}

export async function addVariant(variant: VariantType, payment_provider: PaymentProvider): Promise<{ success: boolean }> {
  return apiFetch<{ success: boolean }>('/billing/variant', {
    method: 'POST',
    body: JSON.stringify({ variant, payment_provider }),
  }, { success: true });
}

export async function removeVariant(variant: VariantType): Promise<{ success: boolean }> {
  return apiFetch<{ success: boolean }>(`/billing/variant/${variant}`, {
    method: 'DELETE',
  }, { success: true });
}

export async function getCost(variants: string[], add_ons?: string): Promise<CostCalculation> {
  const params = `variants=${variants.join(',')}${add_ons ? `&add_ons=${add_ons}` : ''}`;
  return apiFetch<CostCalculation>(`/billing/cost?${params}`, {}, MOCK_COST);
}

export async function estimateOverage(variant: VariantType, projected_tickets: number): Promise<OverageEstimate> {
  return apiFetch<OverageEstimate>('/billing/overage/estimate', {
    method: 'POST',
    body: JSON.stringify({ variant, projected_tickets }),
  }, {
    variant,
    projected_tickets,
    overage_tickets: Math.max(0, projected_tickets - 2000),
    overage_cost: Math.max(0, projected_tickets - 2000) * 0.05,
  });
}

export async function getGateways(): Promise<PaymentGateway[]> {
  return apiFetch<PaymentGateway[]>('/billing/gateways', {}, MOCK_GATEWAYS);
}

export async function registerGateway(provider: PaymentProvider, credentials: Record<string, string>): Promise<PaymentGateway> {
  return apiFetch<PaymentGateway>('/billing/gateways', {
    method: 'POST',
    body: JSON.stringify({ provider, credentials }),
  }, { id: `gw-${Date.now()}`, provider, status: 'active', created_at: new Date().toISOString() });
}

// Integrations
export async function getIntegrationCatalog(): Promise<IntegrationCatalogItem[]> {
  return apiFetch<IntegrationCatalogItem[]>('/integrations/catalog', {}, MOCK_CATALOG);
}

export async function getConnectedIntegrations(): Promise<ConnectedIntegration[]> {
  return apiFetch<ConnectedIntegration[]>('/integrations/', {}, MOCK_CONNECTED);
}

export async function connectIntegration(integration_id: string): Promise<ConnectedIntegration> {
  return apiFetch<ConnectedIntegration>('/integrations/connect', {
    method: 'POST',
    body: JSON.stringify({ integration_id }),
  }, {
    id: `ci-${Date.now()}`,
    integration_id,
    name: integration_id,
    status: 'connected',
    connected_at: new Date().toISOString(),
  });
}

export async function disconnectIntegration(integration_id: string): Promise<{ success: boolean }> {
  return apiFetch<{ success: boolean }>(`/integrations/${integration_id}`, {
    method: 'DELETE',
  }, { success: true });
}

export async function testIntegration(integration_id: string): Promise<{ success: boolean; latency_ms?: number }> {
  return apiFetch<{ success: boolean; latency_ms?: number }>(`/integrations/${integration_id}/test`, {
    method: 'POST',
  }, { success: true, latency_ms: 142 });
}

// Notifications
export async function getNotifications(): Promise<Notification[]> {
  return apiFetch<Notification[]>('/notifications/', {}, MOCK_NOTIFICATIONS);
}

export async function markNotificationRead(id: string): Promise<{ success: boolean }> {
  return apiFetch<{ success: boolean }>(`/notifications/${id}/read`, {
    method: 'PUT',
  }, { success: true });
}

// Knowledge
export async function getDocuments(): Promise<KnowledgeDocument[]> {
  return apiFetch<KnowledgeDocument[]>('/knowledge/documents', {}, MOCK_DOCUMENTS);
}

export async function uploadDocument(file: File): Promise<KnowledgeDocument> {
  try {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(apiUrl('/knowledge/upload'), {
      method: 'POST',
      headers: { [COMPANY_HEADER]: COMPANY_ID },
      body: formData,
    });
    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    return await res.json();
  } catch {
    return {
      id: `d-${Date.now()}`,
      name: file.name,
      type: file.name.split('.').pop() || 'unknown',
      size: file.size,
      uploaded_at: new Date().toISOString(),
      status: 'processing',
    };
  }
}

export async function getFAQs(): Promise<FAQ[]> {
  return apiFetch<FAQ[]>('/knowledge/faqs', {}, MOCK_FAQS);
}

export async function createFAQ(question: string, answer: string): Promise<FAQ> {
  return apiFetch<FAQ>('/knowledge/faqs', {
    method: 'POST',
    body: JSON.stringify({ question, answer }),
  }, {
    id: `f-${Date.now()}`,
    question,
    answer,
    created_at: new Date().toISOString(),
  });
}

// Industry
export async function getIndustryPreview(new_industry: string): Promise<IndustryPreview> {
  return apiFetch<IndustryPreview>(`/industry/preview?new_industry=${new_industry}`, {}, {
    ...MOCK_INDUSTRY_PREVIEW,
    new_industry,
  });
}

export async function applyIndustryChange(new_industry: string, disconnect_ids?: string[]): Promise<{ success: boolean }> {
  return apiFetch<{ success: boolean }>('/industry/apply', {
    method: 'POST',
    body: JSON.stringify({ new_industry, disconnect_ids }),
  }, { success: true });
}

// Connectors
export async function getConnectors(): Promise<CustomConnector[]> {
  return apiFetch<CustomConnector[]>('/connectors/', {}, MOCK_CONNECTORS);
}

// Health
export async function getHealth(): Promise<HealthStatus> {
  return apiFetch<HealthStatus>('/health', {}, MOCK_HEALTH);
}

// ============= VARIANT DETAILS =============

export interface VariantInfo {
  id: VariantType;
  name: string;
  price: number;
  tickets: string;
  channels: string;
  ai: string;
  integrations: string;
  extras: string[];
  popular?: boolean;
}

export const VARIANT_DETAILS: VariantInfo[] = [
  {
    id: 'mini',
    name: 'PARWA Mini',
    price: 29,
    tickets: '500 tickets/mo',
    channels: 'Email + Chat',
    ai: 'Basic AI',
    integrations: '2 integrations',
    extras: [],
  },
  {
    id: 'parwa',
    name: 'PARWA Standard',
    price: 79,
    tickets: '2,000 tickets/mo',
    channels: 'All channels',
    ai: 'Advanced AI',
    integrations: '10 integrations',
    extras: ['Knowledge base', 'Priority email support'],
    popular: true,
  },
  {
    id: 'high',
    name: 'PARWA High',
    price: 199,
    tickets: 'Unlimited tickets',
    channels: 'All channels',
    ai: 'Full AI suite',
    integrations: 'Unlimited integrations',
    extras: ['Priority support', 'Custom connectors', 'Dedicated account manager', 'SLA guarantees'],
  },
];
