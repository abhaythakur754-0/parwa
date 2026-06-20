'use client';

import { create } from 'zustand';
import { toast } from 'sonner';

// ── Types ────────────────────────────────────────────────────────────

export type TicketType =
  | 'billing'
  | 'technical'
  | 'account'
  | 'general'
  | 'refund'
  | 'feature_request'
  | 'complaint';

export type Complexity = 'simple' | 'moderate' | 'complex' | 'critical';
export type HumanStatus = 'pending' | 'guidance_provided' | 'resolved';
export type ReprocessStatus = 'pending' | 'processing' | 'done' | 'failed';
export type CrmProvider = 'zendesk' | 'hubspot' | 'generic' | '';
export type CrmStatus = 'pending' | 'updated' | 'failed' | '';

export interface Escalation {
  escalation_id: string;
  tenant_id: string;
  original_ticket_id: string;
  notification_key: string;
  original_query: string;
  ticket_type: TicketType;
  complexity: Complexity;
  required_action: string;
  knowledge_context: Array<{ title: string; snippet: string; score: number }>;
  customer_context: Record<string, unknown> | null;
  previous_attempts: string[];
  failure_analysis: string;
  quality_score: number;
  technique_log: Array<{ step: string; detail: string; duration_ms: number }>;
  human_guidance: string;
  human_status: HumanStatus;
  guidance_timestamp: string | null;
  guidance_source: string | null;
  reprocess_status: ReprocessStatus;
  reprocess_result: string;
  reprocess_quality_score: number | null;
  reprocess_technique_log: Array<{ step: string; detail: string; duration_ms: number }>;
  crm_ticket_id: string;
  crm_provider: CrmProvider;
  crm_status: CrmStatus;
  created_at: string;
  updated_at: string;
}

export interface EscalationStats {
  awaiting_human: number;
  guidance_provided: number;
  resolved: number;
  failed: number;
  total: number;
}

export interface EscalationFilters {
  humanStatus: HumanStatus | 'all';
  reprocessStatus: ReprocessStatus | 'all';
  search: string;
}

// ── Display Helpers ─────────────────────────────────────────────────

export const TICKET_TYPE_LABELS: Record<TicketType, string> = {
  billing: 'Billing',
  technical: 'Technical',
  account: 'Account',
  general: 'General',
  refund: 'Refund',
  feature_request: 'Feature Request',
  complaint: 'Complaint',
};

export const COMPLEXITY_LABELS: Record<Complexity, string> = {
  simple: 'Simple',
  moderate: 'Moderate',
  complex: 'Complex',
  critical: 'Critical',
};

export const HUMAN_STATUS_LABELS: Record<HumanStatus, string> = {
  pending: 'Awaiting Human',
  guidance_provided: 'Guidance Provided',
  resolved: 'Resolved',
};

export const REPROCESS_STATUS_LABELS: Record<ReprocessStatus, string> = {
  pending: 'Pending',
  processing: 'Processing',
  done: 'Done',
  failed: 'Failed',
};

export const CRM_PROVIDER_LABELS: Record<string, string> = {
  zendesk: 'Zendesk',
  hubspot: 'HubSpot',
  generic: 'Generic',
};

export const ALL_HUMAN_STATUSES: HumanStatus[] = ['pending', 'guidance_provided', 'resolved'];
export const ALL_REPROCESS_STATUSES: ReprocessStatus[] = ['pending', 'processing', 'done', 'failed'];

// ── Mock Data ────────────────────────────────────────────────────────

const MOCK_ESCALATIONS: Escalation[] = [
  {
    escalation_id: 'esc_001',
    tenant_id: 'tenant_001',
    original_ticket_id: 'TKT-20240315-001',
    notification_key: 'notif_billing_7a3f',
    original_query:
      'I was charged $149.99 on March 12th but my subscription is only $49.99/month. I already canceled my account last week and you still charged me. I want a full refund immediately and confirmation that my account is permanently deleted.',
    ticket_type: 'billing',
    complexity: 'complex',
    required_action: 'Investigate duplicate/erroneous charge, verify cancellation, process refund, confirm account deletion',
    knowledge_context: [
      { title: 'Refund Policy - Enterprise Tier', snippet: 'Enterprise customers may receive up to 30-day full refund if cancellation was submitted before billing cycle.', score: 0.89 },
      { title: 'Billing Dispute Resolution', snippet: 'Disputes must be resolved within 48 hours. Refund processing takes 5-7 business days.', score: 0.72 },
    ],
    customer_context: { plan: 'Enterprise', tenure_months: 14, lifetime_value: 2098.86, cancellation_date: '2024-03-08' },
    previous_attempts: ['Initial auto-response: Generic refund policy', 'Second attempt: Standard cancellation confirmation'],
    failure_analysis:
      'The AI could not verify whether the cancellation was properly processed before the billing cycle ran. The billing system API returned a timeout. Additionally, the refund amount calculation required cross-referencing with proration rules that are not in the knowledge base.',
    quality_score: 0.32,
    technique_log: [
      { step: 'classify_ticket', detail: 'Classified as billing with 0.94 confidence', duration_ms: 120 },
      { step: 'retrieve_knowledge', detail: 'Found 2 relevant documents', duration_ms: 340 },
      { step: 'check_billing_system', detail: 'API timeout after 5000ms', duration_ms: 5023 },
      { step: 'generate_response', detail: 'Quality check failed: 0.32 < 0.60 threshold', duration_ms: 890 },
    ],
    human_guidance: '',
    human_status: 'pending',
    guidance_timestamp: null,
    guidance_source: null,
    reprocess_status: 'pending',
    reprocess_result: '',
    reprocess_quality_score: null,
    reprocess_technique_log: [],
    crm_ticket_id: 'ZD-48291',
    crm_provider: 'zendesk',
    crm_status: 'updated',
    created_at: '2024-03-15T09:23:00Z',
    updated_at: '2024-03-15T09:23:00Z',
  },
  {
    escalation_id: 'esc_002',
    tenant_id: 'tenant_001',
    original_ticket_id: 'TKT-20240315-002',
    notification_key: 'notif_tech_2b8e',
    original_query:
      'Your integration with Salesforce keeps breaking. Every time I try to sync contacts, it shows "OAuth token expired" and I have to re-authenticate manually. This has been happening 3 times this week. My team of 15 sales reps are blocked from doing their work.',
    ticket_type: 'technical',
    complexity: 'critical',
    required_action: 'Diagnose OAuth token refresh issue, check token expiry configuration, provide permanent fix',
    knowledge_context: [
      { title: 'Salesforce Integration Guide', snippet: 'OAuth tokens should auto-refresh using the refresh token. Default expiry is 1 hour.', score: 0.91 },
      { title: 'Known Issues - March 2024', snippet: 'Salesforce changed their OAuth flow on March 1st. Updated integration required.', score: 0.85 },
    ],
    customer_context: { integration: 'salesforce', team_size: 15, impact: 'critical', first_reported: '2024-03-11' },
    previous_attempts: [
      'Auto-response: Standard OAuth reconnection steps',
      'Second attempt: Suggested clearing browser cache and re-authenticating',
    ],
    failure_analysis:
      'The knowledge base article about the Salesforce OAuth change was dated March 1st but the AI did not prioritize it. The response suggested basic troubleshooting instead of acknowledging the known platform change and providing the updated integration steps.',
    quality_score: 0.28,
    technique_log: [
      { step: 'classify_ticket', detail: 'Classified as technical with 0.97 confidence', duration_ms: 95 },
      { step: 'retrieve_knowledge', detail: 'Found 3 relevant documents', duration_ms: 280 },
      { step: 'analyze_context', detail: 'Identified recurring issue pattern', duration_ms: 150 },
      { step: 'generate_response', detail: 'Quality check failed: 0.28 < 0.60 threshold', duration_ms: 1020 },
    ],
    human_guidance: 'This is a known issue caused by Salesforce changing their OAuth flow. The customer needs to update to integration v3.2+ which handles the new token refresh mechanism. Ask them to check their current integration version in Settings > Integrations > Salesforce.',
    human_status: 'guidance_provided',
    guidance_timestamp: '2024-03-15T10:15:00Z',
    guidance_source: 'agent',
    reprocess_status: 'done',
    reprocess_result:
      'Based on agent guidance, identified the Salesforce OAuth flow change from March 1st. Provided customer with step-by-step instructions to update to integration v3.2. Included the new OAuth configuration settings and a direct link to the migration guide.',
    reprocess_quality_score: 0.87,
    reprocess_technique_log: [
      { step: 'incorporate_guidance', detail: 'Added Salesforce OAuth change context from agent guidance', duration_ms: 45 },
      { step: 'retrieve_knowledge', detail: 'Fetched integration v3.2 migration guide', duration_ms: 220 },
      { step: 'generate_response', detail: 'Quality check passed: 0.87 >= 0.60 threshold', duration_ms: 780 },
      { step: 'push_to_crm', detail: 'Successfully updated Zendesk ticket ZD-48302', duration_ms: 340 },
    ],
    crm_ticket_id: 'ZD-48302',
    crm_provider: 'zendesk',
    crm_status: 'updated',
    created_at: '2024-03-15T08:45:00Z',
    updated_at: '2024-03-15T10:18:00Z',
  },
  {
    escalation_id: 'esc_003',
    tenant_id: 'tenant_001',
    original_ticket_id: 'TKT-20240314-018',
    notification_key: 'notif_account_9c4d',
    original_query:
      'I need to transfer ownership of our company account from my email (john@oldcompany.com) to our new operations director at sarah@newcompany.com. The company was acquired and we need this done urgently as my access will be cut off by end of day Friday.',
    ticket_type: 'account',
    complexity: 'moderate',
    required_action: 'Process account ownership transfer with proper verification',
    knowledge_context: [
      { title: 'Account Transfer Policy', snippet: 'Account ownership transfers require email verification from both old and new owners, plus admin confirmation.', score: 0.88 },
    ],
    customer_context: { current_plan: 'Business', seats: 25, company_status: 'acquired' },
    previous_attempts: ['Initial response: Generic account settings link'],
    failure_analysis:
      'The AI provided a generic link to account settings instead of recognizing this as an ownership transfer request requiring special handling. It also did not address the urgency or the acquisition context.',
    quality_score: 0.35,
    technique_log: [
      { step: 'classify_ticket', detail: 'Classified as account with 0.82 confidence', duration_ms: 110 },
      { step: 'retrieve_knowledge', detail: 'Found 1 relevant document', duration_ms: 190 },
      { step: 'generate_response', detail: 'Quality check failed: 0.35 < 0.60 threshold', duration_ms: 650 },
    ],
    human_guidance: '',
    human_status: 'pending',
    guidance_timestamp: null,
    guidance_source: null,
    reprocess_status: 'pending',
    reprocess_result: '',
    reprocess_quality_score: null,
    reprocess_technique_log: [],
    crm_ticket_id: '',
    crm_provider: '',
    crm_status: 'pending',
    created_at: '2024-03-14T16:30:00Z',
    updated_at: '2024-03-14T16:30:00Z',
  },
  {
    escalation_id: 'esc_004',
    tenant_id: 'tenant_001',
    original_ticket_id: 'TKT-20240314-022',
    notification_key: 'notif_complaint_5f1a',
    original_query:
      'This is absolutely unacceptable. I have been waiting 6 days for a response to my refund request. Your AI bot keeps giving me the same generic response about "processing times" but no one has actually looked at my case. I want to speak to a real manager immediately. I am a paying customer and this is the worst customer service I have ever experienced.',
    ticket_type: 'complaint',
    complexity: 'critical',
    required_action: 'Escalate to management, provide personal response, resolve refund request',
    knowledge_context: [
      { title: 'Complaint Handling Procedure', snippet: 'Complaints mentioning "manager" or "unacceptable" must be escalated to Tier 2 within 2 hours.', score: 0.93 },
      { title: 'VIP Customer Protocol', snippet: 'Customers on Business+ plans with >12 months tenure receive priority complaint handling.', score: 0.76 },
    ],
    customer_context: { plan: 'Business', tenure_months: 18, previous_complaints: 1, sentiment: 'very_negative' },
    previous_attempts: ['Auto-response: Refund processing times (generic)', 'Auto-response: Same generic response repeated'],
    failure_analysis:
      'The AI failed to recognize the escalating anger and repeated-contact pattern. It sent the same generic response twice, which further aggravated the customer. A complaint with strong negative sentiment keywords and a demand for a manager should have been flagged for immediate human handoff.',
    quality_score: 0.15,
    technique_log: [
      { step: 'classify_ticket', detail: 'Classified as complaint with 0.91 confidence', duration_ms: 88 },
      { step: 'sentiment_analysis', detail: 'Detected very_negative sentiment (0.12 score)', duration_ms: 200 },
      { step: 'retrieve_knowledge', detail: 'Found 2 relevant documents', duration_ms: 260 },
      { step: 'generate_response', detail: 'Quality check failed: 0.15 < 0.60 threshold. Repeated response detected.', duration_ms: 540 },
    ],
    human_guidance: 'This customer needs an immediate personal apology from a senior agent. Process the pending refund (Ticket TKT-20240308-044) as priority. Offer a 1-month free extension as goodwill. The customer has been a loyal subscriber for 18 months.',
    human_status: 'guidance_provided',
    guidance_timestamp: '2024-03-14T17:00:00Z',
    guidance_source: 'agent',
    reprocess_status: 'done',
    reprocess_result:
      'Drafted a personalized apology acknowledging the delay and frustration. Confirmed the refund from TKT-20240308-044 has been prioritized. Included the 1-month goodwill extension offer. Response is empathetic and addresses all customer concerns.',
    reprocess_quality_score: 0.91,
    reprocess_technique_log: [
      { step: 'incorporate_guidance', detail: 'Added refund reference and goodwill offer from agent', duration_ms: 35 },
      { step: 'sentiment_adjustment', detail: 'Applied empathetic tone framework for very_negative sentiment', duration_ms: 180 },
      { step: 'generate_response', detail: 'Quality check passed: 0.91 >= 0.60 threshold', duration_ms: 620 },
      { step: 'push_to_crm', detail: 'Failed to update HubSpot ticket: CRM API returned 403', duration_ms: 1200 },
    ],
    crm_ticket_id: 'HS-78432',
    crm_provider: 'hubspot',
    crm_status: 'failed',
    created_at: '2024-03-14T14:20:00Z',
    updated_at: '2024-03-14T17:05:00Z',
  },
  {
    escalation_id: 'esc_005',
    tenant_id: 'tenant_001',
    original_ticket_id: 'TKT-20240315-005',
    notification_key: 'notif_refund_3e7c',
    original_query:
      'I upgraded from Basic to Pro plan mid-cycle on Feb 28th and was told I would get a prorated credit for the remaining Basic days. It has been 2 weeks and I still see no credit on my billing page.',
    ticket_type: 'refund',
    complexity: 'moderate',
    required_action: 'Verify proration calculation, apply credit, explain billing timeline',
    knowledge_context: [
      { title: 'Plan Upgrade Proration', snippet: 'When upgrading mid-cycle, customers receive a prorated credit applied to the next billing cycle. Processing takes up to 10 business days.', score: 0.92 },
    ],
    customer_context: { previous_plan: 'Basic', new_plan: 'Pro', upgrade_date: '2024-02-28', billing_cycle_start: '2024-02-15' },
    previous_attempts: ['Auto-response: Standard proration explanation without checking actual credit status'],
    failure_analysis:
      'The AI explained the proration policy but did not check whether the credit was actually processed. The customer specifically stated they see no credit on their billing page, which suggests a processing issue rather than a timing issue.',
    quality_score: 0.41,
    technique_log: [
      { step: 'classify_ticket', detail: 'Classified as refund with 0.88 confidence', duration_ms: 105 },
      { step: 'retrieve_knowledge', detail: 'Found 1 relevant document', duration_ms: 175 },
      { step: 'generate_response', detail: 'Quality check failed: 0.41 < 0.60 threshold. Did not address actual credit status.', duration_ms: 710 },
    ],
    human_guidance: '',
    human_status: 'pending',
    guidance_timestamp: null,
    guidance_source: null,
    reprocess_status: 'pending',
    reprocess_result: '',
    reprocess_quality_score: null,
    reprocess_technique_log: [],
    crm_ticket_id: '',
    crm_provider: '',
    crm_status: '',
    created_at: '2024-03-15T11:10:00Z',
    updated_at: '2024-03-15T11:10:00Z',
  },
  {
    escalation_id: 'esc_006',
    tenant_id: 'tenant_001',
    original_ticket_id: 'TKT-20240313-009',
    notification_key: 'notif_feature_8b2d',
    original_query:
      'We need the ability to create custom ticket fields for our workflow. Right now we can only use the default fields but our compliance team requires specific data points for audit trails. Is this on your roadmap?',
    ticket_type: 'feature_request',
    complexity: 'simple',
    required_action: 'Check if custom fields feature exists or is planned, provide alternative if not available',
    knowledge_context: [
      { title: 'Custom Fields Feature', snippet: 'Custom fields are available on Business and Enterprise plans. Go to Settings > Ticket Fields > Custom.', score: 0.95 },
    ],
    customer_context: { plan: 'Pro', seats: 10, industry: 'Healthcare' },
    previous_attempts: ['Auto-response: Thanked for suggestion, said it was added to roadmap (incorrect)'],
    failure_analysis:
      'The AI incorrectly stated the feature was on the roadmap when it actually already exists. The customer is on the Pro plan which supports custom fields. The response should have directed them to Settings > Ticket Fields > Custom instead of treating it as a feature request.',
    quality_score: 0.22,
    technique_log: [
      { step: 'classify_ticket', detail: 'Misclassified as feature_request (0.72) instead of how-to question (0.68)', duration_ms: 115 },
      { step: 'retrieve_knowledge', detail: 'Found 1 highly relevant document about custom fields', duration_ms: 195 },
      { step: 'generate_response', detail: 'Quality check failed: 0.22 < 0.60 threshold. Misinformation risk.', duration_ms: 480 },
    ],
    human_guidance: 'Custom fields are already available on their Pro plan. Direct them to Settings > Ticket Fields > Custom. Mention that for compliance audit trails, they can also enable the Audit Log add-on.',
    human_status: 'resolved',
    guidance_timestamp: '2024-03-13T15:30:00Z',
    guidance_source: 'agent',
    reprocess_status: 'done',
    reprocess_result:
      'Corrected the misinformation by explaining that custom fields are already available on the Pro plan. Provided step-by-step instructions to access Settings > Ticket Fields > Custom. Also mentioned the Audit Log add-on for compliance needs.',
    reprocess_quality_score: 0.94,
    reprocess_technique_log: [
      { step: 'incorporate_guidance', detail: 'Corrected feature classification based on agent guidance', duration_ms: 30 },
      { step: 'retrieve_knowledge', detail: 'Fetched custom fields setup guide and audit log docs', duration_ms: 210 },
      { step: 'generate_response', detail: 'Quality check passed: 0.94 >= 0.60 threshold', duration_ms: 550 },
      { step: 'push_to_crm', detail: 'Updated Zendesk ticket ZD-48011 with corrected response', duration_ms: 280 },
    ],
    crm_ticket_id: 'ZD-48011',
    crm_provider: 'zendesk',
    crm_status: 'updated',
    created_at: '2024-03-13T14:50:00Z',
    updated_at: '2024-03-13T15:35:00Z',
  },
  {
    escalation_id: 'esc_007',
    tenant_id: 'tenant_001',
    original_ticket_id: 'TKT-20240315-008',
    notification_key: 'notif_general_1a4f',
    original_query:
      'How do I set up automated ticket routing based on the skill level of my agents? I want technical tickets to go to senior engineers and billing questions to go to the billing team automatically.',
    ticket_type: 'general',
    complexity: 'moderate',
    required_action: 'Explain routing rules setup, provide configuration steps for skill-based routing',
    knowledge_context: [
      { title: 'Routing Rules Configuration', snippet: 'Go to Settings > Routing > Rules. Create rules based on ticket category, keywords, or custom fields.', score: 0.78 },
    ],
    customer_context: { plan: 'Business', agents: 8, teams: ['engineering', 'billing', 'general'] },
    previous_attempts: ['Auto-response: Basic routing overview without specific skill-based routing instructions'],
    failure_analysis:
      'The AI provided a generic overview of routing but did not explain how to set up skill-based routing specifically. The customer asked about routing based on agent skill level, which requires a different configuration approach than category-based routing.',
    quality_score: 0.38,
    technique_log: [
      { step: 'classify_ticket', detail: 'Classified as general with 0.79 confidence', duration_ms: 130 },
      { step: 'retrieve_knowledge', detail: 'Found 1 relevant document', duration_ms: 210 },
      { step: 'generate_response', detail: 'Quality check failed: 0.38 < 0.60 threshold. Too generic.', duration_ms: 590 },
    ],
    human_guidance: '',
    human_status: 'pending',
    guidance_timestamp: null,
    guidance_source: null,
    reprocess_status: 'pending',
    reprocess_result: '',
    reprocess_quality_score: null,
    reprocess_technique_log: [],
    crm_ticket_id: '',
    crm_provider: '',
    crm_status: '',
    created_at: '2024-03-15T07:50:00Z',
    updated_at: '2024-03-15T07:50:00Z',
  },
  {
    escalation_id: 'esc_008',
    tenant_id: 'tenant_001',
    original_ticket_id: 'TKT-20240312-031',
    notification_key: 'notif_billing_6c9e',
    original_query:
      'Your pricing page shows $79/month for the Business plan but I am being charged $89/month. I have screenshots from when I signed up showing the $79 price. This feels like a bait-and-switch.',
    ticket_type: 'billing',
    complexity: 'complex',
    required_action: 'Investigate pricing discrepancy, check legacy pricing, resolve billing amount',
    knowledge_context: [
      { title: 'Pricing History', snippet: 'Business plan was $79/month until Jan 15, 2024 when it was updated to $89/month. Legacy customers on annual billing retain $79 rate.', score: 0.87 },
    ],
    customer_context: { plan: 'Business', billing: 'monthly', signup_date: '2023-11-20' },
    previous_attempts: ['Auto-response: Current pricing information only', 'Second attempt: Suggested contacting billing support'],
    failure_analysis:
      'The AI did not check the pricing history or the customer\'s signup date to determine if they should be on the legacy rate. The customer signed up in November 2023 at $79/month and should have been grandfathered at that rate.',
    quality_score: 0.29,
    technique_log: [
      { step: 'classify_ticket', detail: 'Classified as billing with 0.96 confidence', duration_ms: 98 },
      { step: 'retrieve_knowledge', detail: 'Found 1 document but missed pricing history', duration_ms: 240 },
      { step: 'generate_response', detail: 'Quality check failed: 0.29 < 0.60 threshold', duration_ms: 670 },
    ],
    human_guidance: 'Check the customer\'s original signup terms. Business plan was $79/month until Jan 15, 2024. Customers who signed up before the price change on monthly billing should have been grandfathered. Verify their contract and adjust the rate if applicable. If they want the legacy rate permanently, suggest switching to annual billing.',
    human_status: 'guidance_provided',
    guidance_timestamp: '2024-03-12T16:45:00Z',
    guidance_source: 'agent',
    reprocess_status: 'failed',
    reprocess_result: '',
    reprocess_quality_score: null,
    reprocess_technique_log: [
      { step: 'incorporate_guidance', detail: 'Added pricing history and grandfathering context', duration_ms: 40 },
      { step: 'retrieve_knowledge', detail: 'Fetched full pricing history and legacy terms', duration_ms: 310 },
      { step: 'generate_response', detail: 'Quality check passed: 0.82 >= 0.60 threshold', duration_ms: 720 },
      { step: 'push_to_crm', detail: 'Failed: CRM system returned 500 Internal Server Error', duration_ms: 3000 },
    ],
    crm_ticket_id: 'HS-78199',
    crm_provider: 'hubspot',
    crm_status: 'failed',
    created_at: '2024-03-12T15:20:00Z',
    updated_at: '2024-03-12T16:50:00Z',
  },
];

// ── Store Interface ──────────────────────────────────────────────────

interface EscalationStore {
  escalations: Escalation[];
  stats: EscalationStats;
  loading: boolean;
  providingGuidance: boolean;
  selectedEscalation: Escalation | null;
  isModalOpen: boolean;
  modalMode: 'guidance' | 'result';
  filters: EscalationFilters;
  autoResumeResult: { success: number; failed: number; message: string } | null;

  // Actions
  fetchEscalations: (tenantId: string, filters?: Partial<EscalationFilters>) => Promise<void>;
  fetchStats: (tenantId: string) => Promise<void>;
  setFilters: (filters: Partial<EscalationFilters>) => void;
  openModal: (escalation: Escalation, mode: 'guidance' | 'result') => void;
  closeModal: () => void;
  provideGuidance: (escalationId: string, guidance: string, source?: string) => Promise<boolean>;
  provideGuidanceByNotification: (notificationKey: string, guidance: string) => Promise<boolean>;
  resumeEscalation: (escalationId: string) => Promise<boolean>;
  autoResumeAll: (tenantId: string) => Promise<void>;
}

// ── Store ────────────────────────────────────────────────────────────

export const useEscalationStore = create<EscalationStore>((set, get) => ({
  escalations: [],
  stats: { awaiting_human: 0, guidance_provided: 0, resolved: 0, failed: 0, total: 0 },
  loading: false,
  providingGuidance: false,
  selectedEscalation: null,
  isModalOpen: false,
  modalMode: 'guidance',
  filters: { humanStatus: 'all', reprocessStatus: 'all', search: '' },
  autoResumeResult: null,

  fetchEscalations: async (tenantId: string, filters?: Partial<EscalationFilters>) => {
    set({ loading: true, autoResumeResult: null });
    const mergedFilters = { ...get().filters, ...filters };

    try {
      const params = new URLSearchParams();
      params.set('tenant_id', tenantId);
      if (mergedFilters.humanStatus !== 'all') params.set('human_status', mergedFilters.humanStatus);
      if (mergedFilters.reprocessStatus !== 'all') params.set('reprocess_status', mergedFilters.reprocessStatus);
      if (mergedFilters.search) params.set('search', mergedFilters.search);

      const res = await fetch(`/api/escalations?${params.toString()}`);
      if (res.ok) {
        const data = await res.json();
        set({ escalations: data.escalations || data, loading: false });
        return;
      }
    } catch {
      // Backend unavailable — fall through to mock data
    }

    // Mock data fallback
    await new Promise((r) => setTimeout(r, 400));
    let filtered = [...MOCK_ESCALATIONS].filter((e) => e.tenant_id === tenantId);
    if (mergedFilters.humanStatus !== 'all') {
      filtered = filtered.filter((e) => e.human_status === mergedFilters.humanStatus);
    }
    if (mergedFilters.reprocessStatus !== 'all') {
      filtered = filtered.filter((e) => e.reprocess_status === mergedFilters.reprocessStatus);
    }
    if (mergedFilters.search) {
      const s = mergedFilters.search.toLowerCase();
      filtered = filtered.filter(
        (e) =>
          e.original_ticket_id.toLowerCase().includes(s) ||
          e.notification_key.toLowerCase().includes(s),
      );
    }
    set({ escalations: filtered, loading: false });
  },

  fetchStats: async (tenantId: string) => {
    try {
      const res = await fetch(`/api/escalations?action=stats&tenant_id=${tenantId}`);
      if (res.ok) {
        const data = await res.json();
        set({ stats: data });
        return;
      }
    } catch {
      // Backend unavailable — fall through to mock
    }

    // Mock data fallback
    const all = MOCK_ESCALATIONS.filter((e) => e.tenant_id === tenantId);
    set({
      stats: {
        awaiting_human: all.filter((e) => e.human_status === 'pending').length,
        guidance_provided: all.filter((e) => e.human_status === 'guidance_provided').length,
        resolved: all.filter((e) => e.human_status === 'resolved').length,
        failed: all.filter((e) => e.reprocess_status === 'failed' && e.human_status !== 'resolved').length,
        total: all.length,
      },
    });
  },

  setFilters: (filters: Partial<EscalationFilters>) => {
    set({ filters: { ...get().filters, ...filters } });
  },

  openModal: (escalation: Escalation, mode: 'guidance' | 'result') => {
    set({ selectedEscalation: escalation, isModalOpen: true, modalMode: mode });
  },

  closeModal: () => {
    set({ selectedEscalation: null, isModalOpen: false, modalMode: 'guidance' });
  },

  provideGuidance: async (escalationId: string, guidance: string, source: string = 'agent') => {
    set({ providingGuidance: true });
    try {
      const res = await fetch(`/api/escalations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'guidance', escalation_id: escalationId, guidance, source }),
      });
      if (res.ok) {
        const data = await res.json();
        // Update local state
        set((state) => ({
          escalations: state.escalations.map((e) =>
            e.escalation_id === escalationId
              ? {
                  ...e,
                  human_guidance: guidance,
                  human_status: 'guidance_provided' as HumanStatus,
                  guidance_timestamp: new Date().toISOString(),
                  guidance_source: source,
                }
              : e,
          ),
          providingGuidance: false,
        }));
        return true;
      }
    } catch {
      // Backend unavailable — update locally
    }

    // Mock fallback
    await new Promise((r) => setTimeout(r, 500));
    set((state) => ({
      escalations: state.escalations.map((e) =>
        e.escalation_id === escalationId
          ? {
              ...e,
              human_guidance: guidance,
              human_status: 'guidance_provided' as HumanStatus,
              guidance_timestamp: new Date().toISOString(),
              guidance_source: source,
            }
          : e,
      ),
      providingGuidance: false,
    }));
    return true;
  },

  provideGuidanceByNotification: async (notificationKey: string, guidance: string) => {
    set({ providingGuidance: true });
    try {
      const res = await fetch(`/api/escalations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'guidance-by-notification', notification_key: notificationKey, guidance }),
      });
      if (res.ok) {
        const data = await res.json();
        // Update local state
        set((state) => ({
          escalations: state.escalations.map((e) =>
            e.notification_key === notificationKey
              ? {
                  ...e,
                  human_guidance: guidance,
                  human_status: 'guidance_provided' as HumanStatus,
                  guidance_timestamp: new Date().toISOString(),
                  guidance_source: 'notification',
                }
              : e,
          ),
          providingGuidance: false,
        }));
        toast.success('Guidance saved. Ticket is now eligible for resume.');
        return true;
      }
    } catch {
      // Backend unavailable — update locally
    }

    // Mock fallback
    await new Promise((r) => setTimeout(r, 500));
    set((state) => ({
      escalations: state.escalations.map((e) =>
        e.notification_key === notificationKey
          ? {
              ...e,
              human_guidance: guidance,
              human_status: 'guidance_provided' as HumanStatus,
              guidance_timestamp: new Date().toISOString(),
              guidance_source: 'notification',
            }
          : e,
      ),
      providingGuidance: false,
    }));
    toast.success('Guidance saved. Ticket is now eligible for resume.');
    return true;
  },

  resumeEscalation: async (escalationId: string) => {
    try {
      const res = await fetch(`/api/escalations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'resume', escalation_id: escalationId }),
      });
      if (res.ok) {
        set((state) => ({
          escalations: state.escalations.map((e) =>
            e.escalation_id === escalationId
              ? { ...e, reprocess_status: 'processing' as ReprocessStatus, updated_at: new Date().toISOString() }
              : e,
          ),
        }));
        toast.success('Escalation queued for reprocessing.');
        return true;
      }
    } catch {
      // Backend unavailable — update locally
    }

    // Mock fallback
    await new Promise((r) => setTimeout(r, 300));
    set((state) => ({
      escalations: state.escalations.map((e) =>
        e.escalation_id === escalationId
          ? { ...e, reprocess_status: 'processing' as ReprocessStatus, updated_at: new Date().toISOString() }
          : e,
      ),
    }));
    toast.success('Escalation queued for reprocessing.');
    return true;
  },

  autoResumeAll: async (tenantId: string) => {
    set({ autoResumeResult: null, loading: true });
    try {
      const res = await fetch(`/api/escalations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'auto-resume', tenant_id: tenantId }),
      });
      if (res.ok) {
        const data = await res.json();
        set({
          autoResumeResult: data,
          loading: false,
        });
        toast.success(`Auto-resume complete: ${data.success} succeeded, ${data.failed} failed.`);
        // Refresh data
        get().fetchEscalations(tenantId);
        get().fetchStats(tenantId);
        return;
      }
    } catch {
      // Backend unavailable
    }

    // Mock fallback
    await new Promise((r) => setTimeout(r, 1200));
    const eligible = get().escalations.filter(
      (e) => e.human_status === 'guidance_provided' && e.reprocess_status === 'pending',
    );
    const result = { success: eligible.length, failed: 0, message: `${eligible.length} escalations queued for reprocessing.` };
    set((state) => ({
      escalations: state.escalations.map((e) =>
        e.human_status === 'guidance_provided' && e.reprocess_status === 'pending'
          ? { ...e, reprocess_status: 'processing' as ReprocessStatus, updated_at: new Date().toISOString() }
          : e,
      ),
      autoResumeResult: result,
      loading: false,
    }));
    toast.success(result.message);
  },
}));