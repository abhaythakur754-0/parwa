/**
 * PARWA Demo Store — In-Memory Demo Session Store
 *
 * ⚠️  INTENTIONALLY IN-MEMORY: This store is designed for demo / development
 * mode only.  All session data lives in process memory (Map) and will be
 * lost on server restart.  In production, this would be replaced by
 * PostgreSQL for persistent session data and Redis for fast TTL-based
 * lookups and rate-limiting.
 *
 * Memory-safety: A MAX_SESSIONS cap (default 1000) with LRU eviction
 * prevents unbounded memory growth under load.  When the limit is
 * reached, the least-recently-accessed session is evicted before a new
 * one is created.
 *
 * Manages demo sessions, usage tracking, and billing for the $1 Demo Pack.
 * Used by API routes for server-side state management.
 */

import type {
  DemoVariant,
  DemoSession,
  DemoBillSummary,
  DemoBillItem,
  DemoKnowledgeBase,
  VariantTier,
  DemoUsageEvent,
  ShadowModeStatus,
} from '@/types/demo-variant';

// ── Variant Definitions ──────────────────────────────────────────

export const DEMO_VARIANTS: DemoVariant[] = [
  {
    id: 'starter',
    name: 'PARWA Starter',
    tier: 'starter',
    description: 'The 24/7 Trainee — your reliable workhorse that handles FAQs, data collection, and basic support around the clock.',
    price_per_month: 999,
    tickets_per_month: 1000,
    features: [
      '3 AI agents working 24/7',
      '1,000 tickets/month',
      'Email & Chat channels',
      '2 concurrent phone calls',
      'Basic FAQ handling',
      'Data collection & escalation',
      'Standard analytics dashboard',
    ],
    limitations: [
      'No autonomous decisions',
      'No SMS or social media',
      'No churn prediction',
      'Basic analytics only',
    ],
    best_for: 'Small businesses with simple support needs',
    core_capability: 'FAQ handling, data collection, basic escalation',
    smart_decisions: 'Gathers info and escalates to humans — no autonomous decisions',
    key_advantage: '85% savings vs hiring — reliable 24/7 coverage for under $1K/mo',
    tagline: 'The 24/7 Trainee',
    integrations: ['Shopify', 'WooCommerce', 'Gmail', 'Slack'],
  },
  {
    id: 'growth',
    name: 'PARWA Growth',
    tier: 'growth',
    description: 'The Junior Agent — smart, confident, proactive. Analyzes tickets, recommends actions, and detects patterns like churn and fraud.',
    price_per_month: 2499,
    tickets_per_month: 5000,
    features: [
      '8 AI agents working 24/7',
      '5,000 tickets/month',
      'Email, Chat, SMS & Voice channels',
      '3 concurrent phone calls',
      'Smart recommendations (approve/review/deny)',
      'Churn & fraud detection',
      'Advanced analytics & reporting',
      'Smart Router & Agent Lightning',
    ],
    limitations: [
      'Unusual cases flagged for human review',
      'No video support',
      'Decision cap at $25',
    ],
    best_for: 'Growing businesses that need intelligent automation',
    core_capability: 'Smart recommendations, churn detection, multi-channel support',
    smart_decisions: 'Approve/review/deny recommendations — flags unusual cases for humans',
    key_advantage: 'The sweet spot — powerful automation at an affordable price',
    tagline: 'The Junior Agent',
    integrations: ['Shopify', 'WooCommerce', 'Gmail', 'Slack', 'Twilio', 'Intercom', 'Zendesk'],
  },
  {
    id: 'high',
    name: 'PARWA High',
    tier: 'high',
    description: 'The Senior Agent — fully autonomous, strategic authority. Approves actions, predicts churn, coordinates across departments, and handles VIPs.',
    price_per_month: 3999,
    tickets_per_month: 15000,
    features: [
      '15 AI agents working 24/7',
      '15,000 tickets/month',
      'All channels: Email, Chat, SMS, Voice, Social, Video',
      '5 concurrent phone calls',
      'Full autonomous decisions (up to $50)',
      'Churn prediction & prevention',
      'VIP handling & peer review',
      'Cross-department coordination',
      'Video support',
      'Custom integrations',
    ],
    limitations: [
      'Premium pricing',
      'Requires more setup for custom integrations',
    ],
    best_for: 'Enterprise businesses that need full autonomy',
    core_capability: 'Full autonomy, strategic decisions, cross-department coordination',
    smart_decisions: 'Autonomous decisions up to $50 — you set the confidence thresholds',
    key_advantage: 'The CEO of customer support — fully autonomous with peer review',
    tagline: 'The Senior Agent',
    integrations: ['All Growth integrations + Salesforce', 'HubSpot', 'Jira', 'PagerDuty', 'Custom APIs'],
  },
];

// ── Pre-built Knowledge Bases ────────────────────────────────────

export const PREBUILT_KNOWLEDGE_BASES: DemoKnowledgeBase[] = [
  {
    id: 'kb_ecommerce',
    name: 'E-Commerce Support KB',
    description: 'Order tracking, returns & refunds, product FAQs, shipping policies, payment issues, and cart abandonment responses.',
    industry: 'ecommerce',
    document_count: 47,
    is_prebuilt: true,
    created_at: new Date().toISOString(),
  },
  {
    id: 'kb_saas',
    name: 'SaaS Technical Support KB',
    description: 'API documentation, billing FAQs, feature requests, account management, deployment guides, and troubleshooting.',
    industry: 'saas',
    document_count: 62,
    is_prebuilt: true,
    created_at: new Date().toISOString(),
  },
  {
    id: 'kb_logistics',
    name: 'Logistics & Shipping KB',
    description: 'Shipment tracking, delivery management, warehouse queries, fleet coordination, customs procedures, and hazmat handling.',
    industry: 'logistics',
    document_count: 38,
    is_prebuilt: true,
    created_at: new Date().toISOString(),
  },
  {
    id: 'kb_healthcare',
    name: 'Healthcare Support KB',
    description: 'Appointment scheduling, insurance verification, medical records, prescription management, and billing support.',
    industry: 'healthcare',
    document_count: 33,
    is_prebuilt: true,
    created_at: new Date().toISOString(),
  },
  {
    id: 'kb_realestate',
    name: 'Real Estate Support KB',
    description: 'Property inquiries, scheduling viewings, mortgage FAQs, tenant support, and maintenance ticket handling.',
    industry: 'realestate',
    document_count: 28,
    is_prebuilt: true,
    created_at: new Date().toISOString(),
  },
  {
    id: 'kb_restaurant',
    name: 'Restaurant & Hospitality KB',
    description: 'Reservation management, menu inquiries, delivery support, allergen information, and customer feedback handling.',
    industry: 'restaurant',
    document_count: 24,
    is_prebuilt: true,
    created_at: new Date().toISOString(),
  },
];

// ── In-Memory Store ──────────────────────────────────────────────

const MAX_SESSIONS = 1000;

/** Tracks insertion/access order for LRU eviction. */
const sessionAccessOrder: string[] = [];

const demoSessions = new Map<string, DemoSession>();
const demoUsageEvents = new Map<string, DemoUsageEvent[]>();
const uploadedKBs: DemoKnowledgeBase[] = [];

/** Mark a session as recently accessed (moves to end of LRU list). */
function touchSession(sessionId: string): void {
  const idx = sessionAccessOrder.indexOf(sessionId);
  if (idx !== -1) {
    sessionAccessOrder.splice(idx, 1);
  }
  sessionAccessOrder.push(sessionId);
}

/** Evict the least-recently-used session if the store exceeds MAX_SESSIONS. */
function evictIfNeeded(): void {
  while (demoSessions.size >= MAX_SESSIONS && sessionAccessOrder.length > 0) {
    const oldestId = sessionAccessOrder.shift();
    if (oldestId && demoSessions.has(oldestId)) {
      demoSessions.delete(oldestId);
      demoUsageEvents.delete(oldestId);
    }
  }
}

// ── Helper Functions ─────────────────────────────────────────────

export function generateId(prefix: string = 'demo'): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

export function getVariantById(id: string): DemoVariant | undefined {
  return DEMO_VARIANTS.find((v) => v.id === id);
}

export function getVariantsByIndustry(industry: string): DemoVariant[] {
  // All variants are available for all industries in demo mode
  return DEMO_VARIANTS;
}

// ── Session Management ───────────────────────────────────────────

export function createDemoSession(
  variantId: string,
  tier: VariantTier,
  industry: string,
  entrySource: string,
): DemoSession {
  evictIfNeeded();

  const now = new Date();
  const expiresAt = new Date(now.getTime() + 24 * 60 * 60 * 1000); // 24-hour expiry

  const session: DemoSession = {
    id: generateId('sess'),
    variant_id: variantId,
    variant_tier: tier,
    status: 'active',
    created_at: now.toISOString(),
    expires_at: expiresAt.toISOString(),
    messages_used: 0,
    messages_limit: 40, // 40 user messages (Jarvis responses don't count)
    call_seconds_used: 0,
    call_seconds_limit: 180, // 3 minutes
    shadow_mode: 'shadow', // Default to shadow mode in demo
    knowledge_base_ids: [],
    bill_summary: undefined,
  };

  demoSessions.set(session.id, session);
  demoUsageEvents.set(session.id, []);
  touchSession(session.id);

  return session;
}

export function getDemoSession(sessionId: string): DemoSession | undefined {
  const session = demoSessions.get(sessionId);
  if (session) touchSession(sessionId);
  return session;
}

export function updateDemoSession(
  sessionId: string,
  updates: Partial<DemoSession>,
): DemoSession | undefined {
  const session = demoSessions.get(sessionId);
  if (!session) return undefined;

  const updated = { ...session, ...updates };
  demoSessions.set(sessionId, updated);
  touchSession(sessionId);
  return updated;
}

// ── Usage Tracking ───────────────────────────────────────────────

export function recordUsageEvent(
  sessionId: string,
  type: DemoUsageEvent['type'],
  metadata?: Record<string, unknown>,
): void {
  const events = demoUsageEvents.get(sessionId) || [];
  events.push({
    type,
    timestamp: new Date().toISOString(),
    metadata,
  });
  demoUsageEvents.set(sessionId, events);

  // Update session counters
  const session = demoSessions.get(sessionId);
  if (!session) return;

  if (type === 'user_message') {
    session.messages_used += 1;
    if (session.messages_used >= session.messages_limit) {
      session.status = 'consumed';
    }
  } else if (type === 'call_second') {
    session.call_seconds_used += 1;
  } else if (type === 'call_initiated') {
    // Mark call as started
    session.shadow_mode = 'shadow'; // Call is real, NOT shadow mode
  }

  demoSessions.set(sessionId, session);
  touchSession(sessionId);
}

export function getUsageEvents(sessionId: string): DemoUsageEvent[] {
  return demoUsageEvents.get(sessionId) || [];
}

// ── Bill Summary ─────────────────────────────────────────────────

const PLAN_PRICES: Record<string, number> = {
  starter: 999,
  growth: 2499,
  high: 3999,
};

const HUMAN_AGENT_COST = 4500; // Average human agent cost per month
const AGENTS_PER_PLAN: Record<string, number> = {
  starter: 3,
  growth: 8,
  high: 15,
};

export function calculateBillSummary(
  tier: VariantTier,
  industry: string,
  ticketVolume: number = 1000,
): DemoBillSummary {
  const planPrice = PLAN_PRICES[tier] || 999;
  const agentsCount = AGENTS_PER_PLAN[tier] || 3;
  const humanCost = HUMAN_AGENT_COST * agentsCount;

  // Overages
  const overageTickets = Math.max(0, ticketVolume - (tier === 'starter' ? 1000 : tier === 'growth' ? 5000 : 15000));
  const overageCost = overageTickets * 0.10;

  const items: DemoBillItem[] = [
    {
      name: `PARWA ${tier.charAt(0).toUpperCase() + tier.slice(1)} Plan`,
      type: 'plan',
      unit_price: planPrice,
      quantity: 1,
      total: planPrice,
      description: `${agentsCount} AI agents, ${tier === 'starter' ? '1K' : tier === 'growth' ? '5K' : '15K'} tickets/month`,
    },
  ];

  if (overageCost > 0) {
    items.push({
      name: 'Ticket Overage',
      type: 'overage',
      unit_price: 0.10,
      quantity: overageTickets,
      total: Math.round(overageCost * 100) / 100,
      description: `${overageTickets.toLocaleString()} tickets over plan limit`,
    });
  }

  const subtotal = items.reduce((sum, i) => sum + i.total, 0);
  const tax = Math.round(subtotal * 0.08 * 100) / 100;
  const total = subtotal + tax;
  const savingsVsHuman = humanCost - total;
  const savingsPercentage = Math.round((savingsVsHuman / humanCost) * 100);
  const roiMonths = Math.round((total / savingsVsHuman) * 10) / 10;

  return {
    items,
    subtotal,
    tax,
    total,
    currency: 'USD',
    billing_cycle: 'monthly',
    savings_vs_human: savingsVsHuman,
    savings_percentage: savingsPercentage,
    roi_months: roiMonths,
    monthly_estimate: total,
    annual_estimate: Math.round(total * 12 * 0.85 * 100) / 100, // 15% annual discount
  };
}

// ── Knowledge Base Management ────────────────────────────────────

export function addUploadedKB(kb: DemoKnowledgeBase): void {
  uploadedKBs.push(kb);
}

export function getUploadedKBs(): DemoKnowledgeBase[] {
  return uploadedKBs;
}

export function getAllKnowledgeBases(): {
  prebuilt: DemoKnowledgeBase[];
  uploaded: DemoKnowledgeBase[];
} {
  return {
    prebuilt: PREBUILT_KNOWLEDGE_BASES,
    uploaded: uploadedKBs,
  };
}

export function getKnowledgeBasesByIndustry(industry: string): DemoKnowledgeBase[] {
  const prebuilt = PREBUILT_KNOWLEDGE_BASES.filter((kb) => kb.industry === industry);
  const uploaded = uploadedKBs.filter((kb) => kb.industry === industry || !kb.industry);
  return [...prebuilt, ...uploaded];
}

// ── Demo Output Filter (Shadow Mode) ────────────────────────────
// Strips internal AI details from responses before showing to demo users

export function filterDemoOutput(response: string): string {
  // Remove model names
  let filtered = response.replace(/\b(GPT-4|GPT-3\.5|Claude|Gemini|Llama|Mixtral|Cerebras|Groq)\b/gi, '[AI Model]');

  // Remove confidence scores
  filtered = filtered.replace(/confidence[:\s]*\d+\.?\d*%?/gi, '[Confidence Score]');

  // Remove pipeline step references
  filtered = filtered.replace(/pipeline[_ ]step[:\s]*\d+/gi, '[Pipeline Step]');

  // Remove internal routing info
  filtered = filtered.replace(/route[d]?\s*(via|through|to)\s*\w+_pipeline/gi, '[Routed]');

  return filtered;
}

// ── Industries List ──────────────────────────────────────────────

export const DEMO_INDUSTRIES = [
  { id: 'ecommerce', name: 'E-Commerce', icon: '🛒' },
  { id: 'saas', name: 'SaaS / Tech', icon: '💻' },
  { id: 'logistics', name: 'Logistics', icon: '🚛' },
  { id: 'healthcare', name: 'Healthcare', icon: '🏥' },
  { id: 'realestate', name: 'Real Estate', icon: '🏠' },
  { id: 'restaurant', name: 'Restaurant', icon: '🍽️' },
  { id: 'finance', name: 'Finance', icon: '💰' },
  { id: 'education', name: 'Education', icon: '📚' },
  { id: 'travel', name: 'Travel', icon: '✈️' },
  { id: 'salon', name: 'Salon & Beauty', icon: '💇' },
];
