// ============================================================
// Parwa Variant Engine Dashboard - Comprehensive Mock Data
// ============================================================

import type {
  User, VariantInstance, VariantCapability, Entitlement, TokenBudget,
  Ticket, ProviderHealth, FailoverEvent, ColdStartStatus, QualityMetrics,
  PerformanceMetrics, MonitoringAlert, ChannelStats, EmailChannelConfig,
  SMSChannelConfig, ChatWidgetConfig, VoiceChannelConfig,
  Subscription, UsageRecord, Invoice, PaymentMethod,
  KnowledgeDocument, SearchMetrics, ChatSession, ChatMessage,
  APIKey, Integration, NotificationPreference, CompanySettings,
  KPICard, AutomationTrendPoint, VariantDistribution, ChannelDistribution,
} from './types';

// --- User ---
export const mockUser: User = {
  id: 'usr_001',
  email: 'admin@parwa.ai',
  name: 'Sarah Chen',
  avatar: undefined,
  phone: '+1-555-0142',
  role: 'admin',
  companyId: 'comp_001',
  companyName: 'Parwa Corp',
  mfaEnabled: true,
  createdAt: '2024-01-15T10:00:00Z',
};

// --- KPI Cards ---
export const mockKPICards: KPICard[] = [
  { title: 'Total Tickets', value: '2,847', change: 12.3, changeLabel: 'vs last week', icon: 'TicketCheck', trend: 'up' },
  { title: 'Active Variants', value: '6', change: 0, changeLabel: 'no change', icon: 'Cpu', trend: 'neutral' },
  { title: 'Avg Quality Score', value: '94.2%', change: 2.1, changeLabel: 'vs last week', icon: 'Award', trend: 'up' },
  { title: 'Avg Resolution Time', value: '4.2m', change: -8.5, changeLabel: 'vs last week', icon: 'Clock', trend: 'down' },
  { title: 'Automation Rate', value: '87.3%', change: 3.2, changeLabel: 'vs last month', icon: 'Bot', trend: 'up' },
  { title: 'Token Usage Today', value: '1.2M', change: 15.4, changeLabel: 'vs yesterday', icon: 'Zap', trend: 'up' },
];

// --- Automation Trend ---
export const mockAutomationTrend: AutomationTrendPoint[] = Array.from({ length: 30 }, (_, i) => {
  const date = new Date();
  date.setDate(date.getDate() - (29 - i));
  const base = 84.3 + (i * 0.18) + (Math.random() * 1.5 - 0.75);
  return {
    date: date.toISOString().split('T')[0],
    automationRate: Math.min(89.5, Math.round(base * 10) / 10),
    target: 89.5,
  };
});

// --- Variant Distribution ---
export const mockVariantDistribution: VariantDistribution[] = [
  { name: 'mini_parwa (Starter)', value: 892, color: '#10b981' },
  { name: 'parwa (Growth)', value: 1245, color: '#f59e0b' },
  { name: 'parwa_high (High)', value: 710, color: '#ef4444' },
];

// --- Channel Distribution ---
export const mockChannelDistribution: ChannelDistribution[] = [
  { channel: 'Chat', tickets: 1420, resolved: 1298 },
  { channel: 'Email', tickets: 856, resolved: 724 },
  { channel: 'SMS', tickets: 312, resolved: 287 },
  { channel: 'Voice', tickets: 259, resolved: 221 },
];

// --- Variant Instances ---
export const mockVariantInstances: VariantInstance[] = [
  {
    id: 'vi_001', name: 'Starter Chat', type: 'mini_parwa', status: 'active', channel: 'chat',
    capacity: 500, currentLoad: 342, accuracyRate: 91.2, avgLatency: 2.1, costPerQuery: 0.003,
    techniqueTier: 1, nodeCount: 10, model: 'gpt-4o-mini', createdAt: '2024-01-20T10:00:00Z',
    lastActive: '2025-05-06T19:30:00Z',
  },
  {
    id: 'vi_002', name: 'Growth Chat', type: 'parwa', status: 'active', channel: 'chat',
    capacity: 800, currentLoad: 612, accuracyRate: 94.5, avgLatency: 5.2, costPerQuery: 0.008,
    techniqueTier: 2, nodeCount: 22, model: 'gpt-4o', createdAt: '2024-02-10T10:00:00Z',
    lastActive: '2025-05-06T19:32:00Z',
  },
  {
    id: 'vi_003', name: 'High Chat', type: 'parwa_high', status: 'active', channel: 'chat',
    capacity: 400, currentLoad: 298, accuracyRate: 97.1, avgLatency: 10.5, costPerQuery: 0.015,
    techniqueTier: 3, nodeCount: 27, model: 'gpt-4o', createdAt: '2024-03-01T10:00:00Z',
    lastActive: '2025-05-06T19:31:00Z',
  },
  {
    id: 'vi_004', name: 'Starter Email', type: 'mini_parwa', status: 'active', channel: 'email',
    capacity: 300, currentLoad: 189, accuracyRate: 89.7, avgLatency: 2.4, costPerQuery: 0.003,
    techniqueTier: 1, nodeCount: 10, model: 'gpt-4o-mini', createdAt: '2024-02-15T10:00:00Z',
    lastActive: '2025-05-06T19:28:00Z',
  },
  {
    id: 'vi_005', name: 'Growth Email', type: 'parwa', status: 'maintenance', channel: 'email',
    capacity: 600, currentLoad: 0, accuracyRate: 93.8, avgLatency: 6.1, costPerQuery: 0.008,
    techniqueTier: 2, nodeCount: 22, model: 'gpt-4o', createdAt: '2024-03-10T10:00:00Z',
    lastActive: '2025-05-06T18:00:00Z',
  },
  {
    id: 'vi_006', name: 'High Voice', type: 'parwa_high', status: 'active', channel: 'voice',
    capacity: 200, currentLoad: 145, accuracyRate: 96.3, avgLatency: 12.1, costPerQuery: 0.015,
    techniqueTier: 3, nodeCount: 27, model: 'gpt-4o', createdAt: '2024-04-01T10:00:00Z',
    lastActive: '2025-05-06T19:25:00Z',
  },
];

// --- Variant Capabilities ---
export const mockVariantCapabilities: VariantCapability[] = [
  { featureId: 'f01', featureName: 'PII Redaction', category: 'Security', mini_parwa: true, parwa: true, parwa_high: true },
  { featureId: 'f02', featureName: 'Empathy Engine', category: 'Security', mini_parwa: true, parwa: true, parwa_high: true },
  { featureId: 'f03', featureName: 'Smart Router', category: 'Core', mini_parwa: true, parwa: true, parwa_high: true },
  { featureId: 'f04', featureName: 'CLARA Quality Gate', category: 'Core', mini_parwa: true, parwa: true, parwa_high: true },
  { featureId: 'f05', featureName: 'CRP (Contextual Response Protocol)', category: 'Core', mini_parwa: true, parwa: true, parwa_high: true },
  { featureId: 'f06', featureName: 'GSD (Get Stuff Done)', category: 'Core', mini_parwa: true, parwa: true, parwa_high: true },
  { featureId: 'f07', featureName: 'Channel Delivery', category: 'Core', mini_parwa: true, parwa: true, parwa_high: true },
  { featureId: 'f08', featureName: 'Chain of Thought', category: 'Tier 2', mini_parwa: false, parwa: true, parwa_high: true },
  { featureId: 'f09', featureName: 'ReAct', category: 'Tier 2', mini_parwa: false, parwa: true, parwa_high: true },
  { featureId: 'f10', featureName: 'Tree of Thoughts', category: 'Tier 2', mini_parwa: false, parwa: true, parwa_high: true },
  { featureId: 'f11', featureName: 'Step-Back Prompting', category: 'Tier 2', mini_parwa: false, parwa: true, parwa_high: true },
  { featureId: 'f12', featureName: 'Complaint Handler', category: 'Tier 2', mini_parwa: false, parwa: true, parwa_high: true },
  { featureId: 'f13', featureName: 'Retention Handler', category: 'Tier 2', mini_parwa: false, parwa: true, parwa_high: true },
  { featureId: 'f14', featureName: 'Billing Handler', category: 'Tier 2', mini_parwa: false, parwa: true, parwa_high: true },
  { featureId: 'f15', featureName: 'Tech Handler', category: 'Tier 2', mini_parwa: false, parwa: true, parwa_high: true },
  { featureId: 'f16', featureName: 'Shipping Handler', category: 'Tier 2', mini_parwa: false, parwa: true, parwa_high: true },
  { featureId: 'f17', featureName: 'GST (Guided Strategic Thinking)', category: 'Tier 3', mini_parwa: false, parwa: false, parwa_high: true },
  { featureId: 'f18', featureName: 'Universe of Thoughts', category: 'Tier 3', mini_parwa: false, parwa: false, parwa_high: true },
  { featureId: 'f19', featureName: 'Self-Consistency', category: 'Tier 3', mini_parwa: false, parwa: false, parwa_high: true },
  { featureId: 'f20', featureName: 'Reflexion', category: 'Tier 3', mini_parwa: false, parwa: false, parwa_high: true },
  { featureId: 'f21', featureName: 'Least-to-Most', category: 'Tier 3', mini_parwa: false, parwa: false, parwa_high: true },
  { featureId: 'f22', featureName: 'Context Compression', category: 'Tier 3', mini_parwa: false, parwa: false, parwa_high: true },
  { featureId: 'f23', featureName: 'Peer Review', category: 'Tier 3', mini_parwa: false, parwa: false, parwa_high: true },
  { featureId: 'f24', featureName: 'Strategic Decision', category: 'Tier 3', mini_parwa: false, parwa: false, parwa_high: true },
];

// --- Entitlements ---
export const mockEntitlements: Entitlement[] = [
  { id: 'e01', name: 'Max Instances', mini_parwa: '2', parwa: '5', parwa_high: '10', unit: 'instances' },
  { id: 'e02', name: 'Daily Token Budget', mini_parwa: '500K', parwa: '2M', parwa_high: '5M', unit: 'tokens' },
  { id: 'e03', name: 'Monthly Token Budget', mini_parwa: '10M', parwa: '50M', parwa_high: '150M', unit: 'tokens' },
  { id: 'e04', name: 'Channels', mini_parwa: 'Chat', parwa: 'Chat, Email', parwa_high: 'All' },
  { id: 'e05', name: 'Enhancement Engines', mini_parwa: 'None', parwa: '2', parwa_high: '5', unit: 'engines' },
  { id: 'e06', name: 'Knowledge Base Docs', mini_parwa: '10', parwa: '50', parwa_high: 'Unlimited', unit: 'docs' },
  { id: 'e07', name: 'API Rate Limit', mini_parwa: '100', parwa: '500', parwa_high: '2000', unit: 'req/min' },
  { id: 'e08', name: 'Team Members', mini_parwa: '3', parwa: '10', parwa_high: 'Unlimited' },
  { id: 'e09', name: 'Support', mini_parwa: 'Email', parwa: 'Priority', parwa_high: 'Dedicated' },
];

// --- Token Budget ---
export const mockTokenBudget: TokenBudget = {
  daily: { limit: 2000000, used: 1200000, remaining: 800000 },
  monthly: { limit: 50000000, used: 32400000, remaining: 17600000 },
  overageCount: 2,
  lastOverageDate: '2025-04-28T14:30:00Z',
};

// --- Tickets ---
export const mockTickets: Ticket[] = [
  {
    id: 'TKT-2847', subject: 'Order not received after 2 weeks', status: 'open', priority: 'high',
    channel: 'chat', variant: 'parwa_high', customerId: 'cust_101', customerName: 'James Wilson',
    customerEmail: 'james@example.com', qualityScore: 96.4, confidenceScore: 0.94,
    techniqueUsed: 'GST + Shipping Intelligence', createdAt: '2025-05-06T18:45:00Z',
    updatedAt: '2025-05-06T19:00:00Z', tags: ['shipping', 'delay', 'order'],
    messages: [
      { id: 'm1', sender: 'customer', content: 'I ordered a laptop 2 weeks ago and it still hasn\'t arrived. Order #ORD-9923.', timestamp: '2025-05-06T18:45:00Z' },
      { id: 'm2', sender: 'ai', content: 'I\'m sorry to hear about the delay with your order #ORD-9923. Let me look into the shipping status for you right away.', timestamp: '2025-05-06T18:45:12Z', metadata: { technique: 'GST', confidence: 0.94, latency: 8.2, model: 'gpt-4o' } },
    ],
  },
  {
    id: 'TKT-2846', subject: 'Billing charge discrepancy', status: 'in_progress', priority: 'urgent',
    channel: 'email', variant: 'parwa', customerId: 'cust_102', customerName: 'Maria Garcia',
    customerEmail: 'maria@example.com', qualityScore: 93.7, confidenceScore: 0.91,
    techniqueUsed: 'Chain of Thought + Billing Intelligence', createdAt: '2025-05-06T17:30:00Z',
    updatedAt: '2025-05-06T18:15:00Z', tags: ['billing', 'refund', 'discrepancy'],
    messages: [
      { id: 'm3', sender: 'customer', content: 'I was charged $149.99 but my plan is only $49.99. This is the third time this has happened!', timestamp: '2025-05-06T17:30:00Z' },
      { id: 'm4', sender: 'ai', content: 'I understand your frustration about the billing discrepancy. I can see you\'ve experienced this issue before, which makes it even more concerning. Let me review your billing history and initiate a correction immediately.', timestamp: '2025-05-06T17:30:25Z', metadata: { technique: 'Chain of Thought + Billing Intelligence', confidence: 0.91, latency: 5.8, model: 'gpt-4o' } },
    ],
  },
  {
    id: 'TKT-2845', subject: 'How to reset my password?', status: 'resolved', priority: 'low',
    channel: 'chat', variant: 'mini_parwa', customerId: 'cust_103', customerName: 'Tom Baker',
    customerEmail: 'tom@example.com', qualityScore: 98.1, confidenceScore: 0.97,
    techniqueUsed: 'FAQ + CLARA', resolutionTime: 45, createdAt: '2025-05-06T16:20:00Z',
    updatedAt: '2025-05-06T16:21:00Z', tags: ['password', 'account', 'faq'],
    messages: [
      { id: 'm5', sender: 'customer', content: 'How do I reset my password?', timestamp: '2025-05-06T16:20:00Z' },
      { id: 'm6', sender: 'ai', content: 'To reset your password:\n1. Go to Settings > Security\n2. Click "Change Password"\n3. Enter your current password and new password\n4. Click "Save Changes"\n\nWould you like me to send you a direct link?', timestamp: '2025-05-06T16:20:08Z', metadata: { technique: 'FAQ + CLARA', confidence: 0.97, latency: 1.8, model: 'gpt-4o-mini' } },
    ],
  },
  {
    id: 'TKT-2844', subject: 'Feature request: dark mode', status: 'closed', priority: 'low',
    channel: 'email', variant: 'mini_parwa', customerId: 'cust_104', customerName: 'Lisa Park',
    customerEmail: 'lisa@example.com', qualityScore: 95.0, confidenceScore: 0.93,
    techniqueUsed: 'CLARA', resolutionTime: 120, createdAt: '2025-05-06T14:10:00Z',
    updatedAt: '2025-05-06T14:12:00Z', tags: ['feature-request', 'ui'],
    messages: [
      { id: 'm7', sender: 'customer', content: 'Would love to see a dark mode option in the dashboard!', timestamp: '2025-05-06T14:10:00Z' },
      { id: 'm8', sender: 'ai', content: 'Thank you for the suggestion! Dark mode is actually already available — you can toggle it using the theme switcher in the top-right corner of the dashboard. Would you like me to walk you through it?', timestamp: '2025-05-06T14:10:15Z', metadata: { technique: 'CLARA', confidence: 0.93, latency: 2.0, model: 'gpt-4o-mini' } },
    ],
  },
  {
    id: 'TKT-2843', subject: 'Service outage affecting API calls', status: 'escalated', priority: 'urgent',
    channel: 'voice', variant: 'parwa_high', customerId: 'cust_105', customerName: 'David Chen',
    customerEmail: 'david@example.com', qualityScore: 88.2, confidenceScore: 0.85,
    techniqueUsed: 'ReAct + Tech Diagnostics', escalationReason: 'Infrastructure issue requiring human intervention',
    createdAt: '2025-05-06T12:00:00Z', updatedAt: '2025-05-06T12:15:00Z',
    tags: ['outage', 'api', 'critical'],
    messages: [
      { id: 'm9', sender: 'customer', content: 'Our API calls are returning 503 errors. This is affecting our production system!', timestamp: '2025-05-06T12:00:00Z' },
      { id: 'm10', sender: 'ai', content: 'I understand this is a critical issue affecting your production. Let me check the API status and run diagnostics immediately.', timestamp: '2025-05-06T12:00:18Z', metadata: { technique: 'ReAct + Tech Diagnostics', confidence: 0.85, latency: 12.3, model: 'gpt-4o' } },
      { id: 'm11', sender: 'ai', content: 'I\'ve detected an active infrastructure issue on our end. I\'m escalating this to our engineering team with priority status. Your ticket has been assigned to an on-call engineer.', timestamp: '2025-05-06T12:01:30Z', metadata: { technique: 'Escalation Protocol', confidence: 0.88, latency: 8.1, model: 'gpt-4o' } },
    ],
  },
  {
    id: 'TKT-2842', subject: 'Subscription downgrade request', status: 'open', priority: 'medium',
    channel: 'sms', variant: 'parwa', customerId: 'cust_106', customerName: 'Amy Torres',
    customerEmail: 'amy@example.com', qualityScore: 91.5, confidenceScore: 0.89,
    techniqueUsed: 'Retention + Step-Back', createdAt: '2025-05-06T10:30:00Z',
    updatedAt: '2025-05-06T10:30:00Z', tags: ['subscription', 'downgrade', 'retention'],
    messages: [
      { id: 'm12', sender: 'customer', content: 'I want to downgrade my subscription to the basic plan.', timestamp: '2025-05-06T10:30:00Z' },
      { id: 'm13', sender: 'ai', content: 'I understand you\'d like to explore a more basic plan. Before I process that, may I ask what\'s prompting the change? I want to make sure you\'re getting the best value for your needs.', timestamp: '2025-05-06T10:30:22Z', metadata: { technique: 'Retention + Step-Back', confidence: 0.89, latency: 6.4, model: 'gpt-4o' } },
    ],
  },
  {
    id: 'TKT-2841', subject: 'Invoice not matching usage', status: 'in_progress', priority: 'medium',
    channel: 'chat', variant: 'parwa', customerId: 'cust_107', customerName: 'Robert Kim',
    customerEmail: 'robert@example.com', qualityScore: 92.8, confidenceScore: 0.90,
    techniqueUsed: 'Billing Intelligence + CoT', createdAt: '2025-05-05T22:00:00Z',
    updatedAt: '2025-05-06T08:00:00Z', tags: ['billing', 'invoice'],
    messages: [],
  },
  {
    id: 'TKT-2840', subject: 'Can\'t access knowledge base', status: 'resolved', priority: 'medium',
    channel: 'email', variant: 'mini_parwa', customerId: 'cust_108', customerName: 'Nina Patel',
    customerEmail: 'nina@example.com', qualityScore: 94.6, confidenceScore: 0.92,
    techniqueUsed: 'GSD', resolutionTime: 180, createdAt: '2025-05-05T16:00:00Z',
    updatedAt: '2025-05-05T16:03:00Z', tags: ['knowledge-base', 'access'],
    messages: [],
  },
  {
    id: 'TKT-2839', subject: 'Chat widget not loading on mobile', status: 'open', priority: 'high',
    channel: 'chat', variant: 'parwa', customerId: 'cust_109', customerName: 'Chris Lee',
    customerEmail: 'chris@example.com', qualityScore: 90.3, confidenceScore: 0.87,
    techniqueUsed: 'Tech Diagnostics + ReAct', createdAt: '2025-05-05T14:00:00Z',
    updatedAt: '2025-05-05T14:00:00Z', tags: ['chat-widget', 'mobile', 'bug'],
    messages: [],
  },
  {
    id: 'TKT-2838', subject: 'Request for custom integration', status: 'open', priority: 'low',
    channel: 'email', variant: 'parwa_high', customerId: 'cust_110', customerName: 'Emma Davis',
    customerEmail: 'emma@example.com', qualityScore: 97.0, confidenceScore: 0.95,
    techniqueUsed: 'Strategic Decision', createdAt: '2025-05-05T10:00:00Z',
    updatedAt: '2025-05-05T10:00:00Z', tags: ['integration', 'custom'],
    messages: [],
  },
];

// --- Provider Health ---
export const mockProviderHealth: ProviderHealth[] = [
  {
    provider: 'OpenAI', status: 'healthy', latency: 320, uptime: 99.97,
    models: [
      { name: 'gpt-4o', available: true, latency: 580, costPer1kTokens: 0.005 },
      { name: 'gpt-4o-mini', available: true, latency: 210, costPer1kTokens: 0.00015 },
    ],
    circuitBreakerState: 'closed', lastChecked: '2025-05-06T19:30:00Z',
  },
  {
    provider: 'Anthropic', status: 'healthy', latency: 410, uptime: 99.92,
    models: [
      { name: 'claude-3.5-sonnet', available: true, latency: 650, costPer1kTokens: 0.003 },
    ],
    circuitBreakerState: 'closed', lastChecked: '2025-05-06T19:30:00Z',
  },
  {
    provider: 'Google AI', status: 'degraded', latency: 890, uptime: 98.5,
    models: [
      { name: 'gemini-1.5-pro', available: true, latency: 1200, costPer1kTokens: 0.0025 },
    ],
    circuitBreakerState: 'half_open', lastChecked: '2025-05-06T19:30:00Z',
  },
];

// --- Failover Events ---
export const mockFailoverEvents: FailoverEvent[] = [
  {
    id: 'fo_001', fromProvider: 'OpenAI', toProvider: 'Anthropic', fromModel: 'gpt-4o',
    toModel: 'claude-3.5-sonnet', reason: 'Latency spike (>2s)', triggeredAt: '2025-05-06T14:22:00Z',
    recoveredAt: '2025-05-06T14:35:00Z', duration: 780,
  },
  {
    id: 'fo_002', fromProvider: 'Google AI', toProvider: 'OpenAI', fromModel: 'gemini-1.5-pro',
    toModel: 'gpt-4o', reason: 'Provider unavailable', triggeredAt: '2025-05-06T10:15:00Z',
    recoveredAt: '2025-05-06T10:45:00Z', duration: 1800,
  },
  {
    id: 'fo_003', fromProvider: 'OpenAI', toProvider: 'Anthropic', fromModel: 'gpt-4o-mini',
    toModel: 'claude-3.5-sonnet', reason: 'Rate limit exceeded', triggeredAt: '2025-05-05T22:10:00Z',
    recoveredAt: '2025-05-05T22:18:00Z', duration: 480,
  },
];

// --- Cold Start Status ---
export const mockColdStartStatus: ColdStartStatus[] = [
  { tenantId: 't_001', tenantName: 'Parwa Corp', warmupState: 'hot', lastAccessed: '2025-05-06T19:30:00Z', warmupProgress: 100 },
  { tenantId: 't_002', tenantName: 'Acme Inc', warmupState: 'warm', lastAccessed: '2025-05-06T17:45:00Z', warmupProgress: 85 },
  { tenantId: 't_003', tenantName: 'TechStart LLC', warmupState: 'warming', lastAccessed: '2025-05-06T15:00:00Z', warmupProgress: 45, estimatedTime: 120 },
  { tenantId: 't_004', tenantName: 'GlobalRetail', warmupState: 'cold', lastAccessed: '2025-05-05T08:00:00Z', warmupProgress: 0 },
];

// --- Quality Metrics ---
export const mockQualityMetrics: QualityMetrics = {
  avgConfidenceScore: 0.924,
  guardrailPassRate: 97.8,
  hallucinationRate: 1.2,
  piiDetectionRate: 99.5,
  sentimentAccuracy: 94.7,
  intentClassificationAccuracy: 92.3,
};

// --- Performance Metrics ---
export const mockPerformanceMetrics: PerformanceMetrics = {
  latencyByVariant: [
    { variant: 'mini_parwa', avg: 2.1, p50: 1.8, p95: 3.5, p99: 5.2 },
    { variant: 'parwa', avg: 5.2, p50: 4.5, p95: 8.1, p99: 12.3 },
    { variant: 'parwa_high', avg: 10.5, p50: 9.2, p95: 14.8, p99: 18.9 },
  ],
  costByVariant: [
    { variant: 'mini_parwa', costPerQuery: 0.003, totalCost: 26.76, queryCount: 8920 },
    { variant: 'parwa', costPerQuery: 0.008, totalCost: 99.60, queryCount: 12450 },
    { variant: 'parwa_high', costPerQuery: 0.015, totalCost: 106.50, queryCount: 7100 },
  ],
  techniqueUsage: [
    { technique: 'CLARA', count: 4520, avgLatency: 1.5, avgConfidence: 0.95 },
    { technique: 'CRP', count: 3890, avgLatency: 2.0, avgConfidence: 0.93 },
    { technique: 'GSD', count: 3200, avgLatency: 2.2, avgConfidence: 0.91 },
    { technique: 'Chain of Thought', count: 2840, avgLatency: 5.5, avgConfidence: 0.92 },
    { technique: 'ReAct', count: 2150, avgLatency: 6.8, avgConfidence: 0.89 },
    { technique: 'Tree of Thoughts', count: 1680, avgLatency: 7.2, avgConfidence: 0.90 },
    { technique: 'Step-Back', count: 1420, avgLatency: 5.0, avgConfidence: 0.91 },
    { technique: 'GST', count: 980, avgLatency: 11.5, avgConfidence: 0.94 },
    { technique: 'Self-Consistency', count: 850, avgLatency: 13.2, avgConfidence: 0.96 },
    { technique: 'Reflexion', count: 720, avgLatency: 12.8, avgConfidence: 0.95 },
  ],
};

// --- Monitoring Alerts ---
export const mockMonitoringAlerts: MonitoringAlert[] = [
  { id: 'ma_001', severity: 'critical', title: 'Circuit Breaker Open', message: 'Google AI provider circuit breaker is in half-open state due to high latency', source: 'Smart Router', timestamp: '2025-05-06T19:25:00Z', acknowledged: false },
  { id: 'ma_002', severity: 'warning', title: 'Token Budget 60% Used', message: 'Daily token budget has reached 60% utilization with 8 hours remaining', source: 'Budget Manager', timestamp: '2025-05-06T18:00:00Z', acknowledged: false },
  { id: 'ma_003', severity: 'warning', title: 'Growth Email Maintenance', message: 'Growth Email variant instance is in maintenance mode', source: 'Variant Manager', timestamp: '2025-05-06T17:30:00Z', acknowledged: true },
  { id: 'ma_004', severity: 'info', title: 'Cold Start Detected', message: 'GlobalRetail tenant detected in cold state - consider triggering warmup', source: 'Cold Start Service', timestamp: '2025-05-06T16:00:00Z', acknowledged: true },
  { id: 'ma_005', severity: 'critical', title: 'Escalation Rate Spike', message: 'Escalation rate increased 15% in the last hour', source: 'Quality Monitor', timestamp: '2025-05-06T19:15:00Z', acknowledged: false },
];

// --- Channel Configs ---
export const mockEmailChannel: EmailChannelConfig = {
  type: 'email', enabled: true, provider: 'Brevo',
  config: { apiKey: '••••••••••••', inboundAddress: 'support@parwa.ai' },
  stats: { inboundToday: 342, outboundToday: 287, avgResponseTime: 45, successRate: 98.2, errorRate: 1.8 },
  brevoApiKey: '••••••••••••', inboundAddress: 'support@parwa.ai', oooDetectionEnabled: true, oooDetectedCount: 23,
};

export const mockSMSChannel: SMSChannelConfig = {
  type: 'sms', enabled: true, provider: 'Twilio',
  config: { phone: '+1-555-0199', accountSid: 'AC••••••••' },
  stats: { inboundToday: 128, outboundToday: 95, avgResponseTime: 12, successRate: 99.1, errorRate: 0.9 },
  twilioPhone: '+1-555-0199', twilioAccountSid: 'AC••••••••',
};

export const mockChatWidget: ChatWidgetConfig = {
  type: 'chat', enabled: true, provider: 'Parwa',
  config: { color: '#10b981', position: 'bottom-right' },
  stats: { inboundToday: 567, outboundToday: 543, avgResponseTime: 3, successRate: 99.5, errorRate: 0.5 },
  widgetColor: '#10b981', position: 'bottom-right', greeting: 'Hi! How can I help you today?',
  embedCode: '<script src="https://cdn.parwa.ai/widget.js" data-id="pw_001"></script>',
};

export const mockVoiceChannel: VoiceChannelConfig = {
  type: 'voice', enabled: true, provider: 'Twilio',
  config: { phone: '+1-555-0188', ivrEnabled: true },
  stats: { inboundToday: 89, outboundToday: 34, avgResponseTime: 8, successRate: 95.4, errorRate: 4.6 },
  twilioPhone: '+1-555-0188', ivrEnabled: true, ivrMenu: 'Press 1 for Sales, 2 for Support, 3 for Billing',
};

// --- Subscription ---
export const mockSubscription: Subscription = {
  id: 'sub_001', planId: 'plan_growth', planName: 'Growth Plan', status: 'active',
  currentPeriodStart: '2025-04-01T00:00:00Z', currentPeriodEnd: '2025-05-01T00:00:00Z',
  nextBillingDate: '2025-06-01T00:00:00Z', amount: 499, currency: 'USD',
  paddleSubscriptionId: 'padd_sub_abc123',
};

// --- Usage Records ---
export const mockUsageRecords: UsageRecord[] = Array.from({ length: 14 }, (_, i) => {
  const date = new Date();
  date.setDate(date.getDate() - (13 - i));
  return [
    { date: date.toISOString().split('T')[0], variant: 'mini_parwa' as const, tokensUsed: Math.floor(180000 + Math.random() * 80000), queryCount: Math.floor(600 + Math.random() * 200), cost: 0 },
    { date: date.toISOString().split('T')[0], variant: 'parwa' as const, tokensUsed: Math.floor(450000 + Math.random() * 200000), queryCount: Math.floor(800 + Math.random() * 300), cost: 0 },
    { date: date.toISOString().split('T')[0], variant: 'parwa_high' as const, tokensUsed: Math.floor(280000 + Math.random() * 120000), queryCount: Math.floor(400 + Math.random() * 150), cost: 0 },
  ];
}).flat().map(r => ({ ...r, cost: r.variant === 'mini_parwa' ? r.queryCount * 0.003 : r.variant === 'parwa' ? r.queryCount * 0.008 : r.queryCount * 0.015 }));

// --- Invoices ---
export const mockInvoices: Invoice[] = [
  { id: 'inv_001', number: 'INV-2025-004', date: '2025-05-01', amount: 499.00, currency: 'USD', status: 'paid', pdfUrl: '#' },
  { id: 'inv_002', number: 'INV-2025-003', date: '2025-04-01', amount: 499.00, currency: 'USD', status: 'paid', pdfUrl: '#' },
  { id: 'inv_003', number: 'INV-2025-002', date: '2025-03-01', amount: 499.00, currency: 'USD', status: 'paid', pdfUrl: '#' },
  { id: 'inv_004', number: 'INV-2025-001', date: '2025-02-01', amount: 249.00, currency: 'USD', status: 'paid', pdfUrl: '#' },
  { id: 'inv_005', number: 'INV-2024-012', date: '2025-01-01', amount: 249.00, currency: 'USD', status: 'paid', pdfUrl: '#' },
];

// --- Payment Methods ---
export const mockPaymentMethods: PaymentMethod[] = [
  { id: 'pm_001', type: 'card', last4: '4242', brand: 'Visa', expiryMonth: 12, expiryYear: 2026, isDefault: true },
  { id: 'pm_002', type: 'card', last4: '8888', brand: 'Mastercard', expiryMonth: 6, expiryYear: 2027, isDefault: false },
];

// --- Knowledge Documents ---
export const mockKnowledgeDocuments: KnowledgeDocument[] = [
  { id: 'kd_001', name: 'Product FAQ.pdf', type: 'pdf', size: 2450000, chunkCount: 142, lastIndexed: '2025-05-06T10:00:00Z', status: 'indexed', uploadDate: '2025-04-15' },
  { id: 'kd_002', name: 'Shipping Policy.docx', type: 'docx', size: 890000, chunkCount: 56, lastIndexed: '2025-05-05T14:00:00Z', status: 'indexed', uploadDate: '2025-04-20' },
  { id: 'kd_003', name: 'Return Policy.txt', type: 'txt', size: 45000, chunkCount: 28, lastIndexed: '2025-05-04T09:00:00Z', status: 'indexed', uploadDate: '2025-04-10' },
  { id: 'kd_004', name: 'Pricing Table.csv', type: 'csv', size: 120000, chunkCount: 15, lastIndexed: '2025-05-03T16:00:00Z', status: 'indexed', uploadDate: '2025-03-25' },
  { id: 'kd_005', name: 'API Documentation.pdf', type: 'pdf', size: 5600000, chunkCount: 312, lastIndexed: '2025-05-06T08:00:00Z', status: 'indexed', uploadDate: '2025-05-01' },
  { id: 'kd_006', name: 'Integration Guide.pdf', type: 'pdf', size: 3200000, chunkCount: 189, lastIndexed: '2025-05-06T12:00:00Z', status: 'indexing', uploadDate: '2025-05-06' },
];

// --- Search Metrics ---
export const mockSearchMetrics: SearchMetrics = {
  avgRelevanceScore: 0.87,
  retrievalLatency: 145,
  hitRate: 94.2,
  totalQueries: 15842,
  failedQueries: 23,
};

// --- Chat Sessions ---
export const mockChatSessions: ChatSession[] = [
  { id: 'cs_001', variant: 'parwa_high', startedAt: '2025-05-06T19:00:00Z', messageCount: 8, qualityScore: 96.4 },
  { id: 'cs_002', variant: 'parwa', startedAt: '2025-05-06T18:30:00Z', endedAt: '2025-05-06T18:45:00Z', messageCount: 4, qualityScore: 93.7 },
  { id: 'cs_003', variant: 'mini_parwa', startedAt: '2025-05-06T17:00:00Z', endedAt: '2025-05-06T17:05:00Z', messageCount: 2, qualityScore: 98.1 },
];

// --- Chat Messages ---
export const mockChatMessages: ChatMessage[] = [
  { id: 'cm_001', role: 'system', content: 'Connected to parwa_high variant. How can I assist you today?', timestamp: '2025-05-06T19:00:00Z', variant: 'parwa_high' },
  { id: 'cm_002', role: 'user', content: 'I need help with my order #ORD-9923. It hasn\'t arrived yet.', timestamp: '2025-05-06T19:00:30Z' },
  { id: 'cm_003', role: 'assistant', content: 'I\'m sorry to hear about the delay with your order #ORD-9923. Let me look into the shipping status for you right away using our shipping intelligence system.', timestamp: '2025-05-06T19:00:38Z', variant: 'parwa_high', technique: 'GST + Shipping Intelligence', confidence: 0.94 },
  { id: 'cm_004', role: 'user', content: 'It\'s been 2 weeks! This is really frustrating.', timestamp: '2025-05-06T19:01:00Z' },
  { id: 'cm_005', role: 'assistant', content: 'I completely understand your frustration. A 2-week delay is absolutely unacceptable, and I want to make this right for you. Here\'s what I\'ve found:\n\n📦 **Order #ORD-9923 Status**: The package appears to be stuck at a regional distribution center since May 1st.\n\n**Here\'s what I\'m doing right now:**\n1. Filing a trace request with the carrier\n2. Initiating a replacement shipment with expedited shipping (free of charge)\n3. Applying a 20% credit to your account for the inconvenience\n\nWould you like me to proceed with the replacement, or would you prefer a full refund?', timestamp: '2025-05-06T19:01:28Z', variant: 'parwa_high', technique: 'Reflexion + Shipping Intelligence', confidence: 0.96, isStreaming: false },
];

// --- API Keys ---
export const mockAPIKeys: APIKey[] = [
  { id: 'ak_001', name: 'Production API Key', key: 'pk_live_••••••••••••••••••••••••a7f3', scope: ['tickets:read', 'tickets:write', 'variants:read'], createdAt: '2025-01-15T10:00:00Z', lastUsed: '2025-05-06T19:00:00Z', status: 'active' },
  { id: 'ak_002', name: 'Development Key', key: 'pk_test_••••••••••••••••••••••••b2e1', scope: ['tickets:read', 'variants:read', 'monitoring:read'], createdAt: '2025-02-20T10:00:00Z', lastUsed: '2025-05-05T14:00:00Z', status: 'active' },
  { id: 'ak_003', name: 'Legacy Key (Revoked)', key: 'pk_old_••••••••••••••••••••••••c8d4', scope: ['tickets:read'], createdAt: '2024-06-10T10:00:00Z', status: 'revoked' },
];

// --- Integrations ---
export const mockIntegrations: Integration[] = [
  { id: 'int_001', name: 'Paddle Billing', provider: 'paddle', status: 'connected', connectedAt: '2025-01-15T10:00:00Z', lastSync: '2025-05-06T18:00:00Z', config: { vendorId: 'vnd_12345' } },
  { id: 'int_002', name: 'Brevo Email', provider: 'brevo', status: 'connected', connectedAt: '2025-01-20T10:00:00Z', lastSync: '2025-05-06T19:00:00Z', config: { apiKey: '••••••••' } },
  { id: 'int_003', name: 'Twilio Voice/SMS', provider: 'twilio', status: 'connected', connectedAt: '2025-02-01T10:00:00Z', lastSync: '2025-05-06T19:00:00Z', config: { accountSid: 'AC••••••••' } },
  { id: 'int_004', name: 'Shopify E-commerce', provider: 'shopify', status: 'disconnected', config: {} },
];

// --- Notification Preferences ---
export const mockNotificationPreferences: NotificationPreference[] = [
  { event: 'Ticket Escalated', email: true, sms: true, push: true, inApp: true },
  { event: 'Circuit Breaker Open', email: true, sms: true, push: true, inApp: true },
  { event: 'Budget Alert', email: true, sms: false, push: true, inApp: true },
  { event: 'Quality Score Drop', email: true, sms: false, push: false, inApp: true },
  { event: 'New Ticket Assigned', email: false, sms: false, push: true, inApp: true },
  { event: 'Monthly Report Ready', email: true, sms: false, push: false, inApp: true },
  { event: 'Integration Error', email: true, sms: true, push: true, inApp: true },
  { event: 'Cold Start Detected', email: false, sms: false, push: false, inApp: true },
];

// --- Company Settings ---
export const mockCompanySettings: CompanySettings = {
  brandVoice: 'Professional yet approachable. Use clear, concise language. Always empathetic when handling complaints.',
  toneGuidelines: 'Maintain a helpful and positive tone. Avoid jargon. Use active voice. Address customers by name when possible.',
  piiPatterns: ['SSN', 'Credit Card', 'Email', 'Phone', 'Date of Birth', 'Address'],
  ragConfig: {
    chunkSize: 512,
    overlap: 50,
    topK: 5,
    similarityThreshold: 0.75,
  },
};
