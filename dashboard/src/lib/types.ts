// ============================================================
// Parwa Variant Engine Dashboard - TypeScript Types
// ============================================================

// --- Auth Types ---
export interface User {
  id: string;
  email: string;
  name: string;
  avatar?: string;
  phone?: string;
  role: 'admin' | 'manager' | 'agent' | 'viewer';
  companyId: string;
  companyName: string;
  mfaEnabled: boolean;
  createdAt: string;
}

export interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

// --- Variant Types ---
export type VariantType = 'mini_parwa' | 'parwa' | 'parwa_high';

export interface VariantInstance {
  id: string;
  name: string;
  type: VariantType;
  status: 'active' | 'inactive' | 'maintenance' | 'error';
  channel: ChannelType;
  capacity: number;
  currentLoad: number;
  accuracyRate: number;
  avgLatency: number;
  costPerQuery: number;
  techniqueTier: 1 | 2 | 3;
  nodeCount: number;
  model: string;
  createdAt: string;
  lastActive: string;
}

export interface VariantCapability {
  featureId: string;
  featureName: string;
  category: string;
  mini_parwa: boolean;
  parwa: boolean;
  parwa_high: boolean;
}

export interface Entitlement {
  id: string;
  name: string;
  mini_parwa: string;
  parwa: string;
  parwa_high: string;
  unit?: string;
}

export interface TokenBudget {
  daily: { limit: number; used: number; remaining: number };
  monthly: { limit: number; used: number; remaining: number };
  overageCount: number;
  lastOverageDate?: string;
}

// --- Ticket Types ---
export type TicketStatus = 'open' | 'in_progress' | 'resolved' | 'closed' | 'escalated';
export type TicketPriority = 'low' | 'medium' | 'high' | 'urgent';
export type ChannelType = 'chat' | 'email' | 'sms' | 'voice';

export interface Ticket {
  id: string;
  subject: string;
  status: TicketStatus;
  priority: TicketPriority;
  channel: ChannelType;
  variant: VariantType;
  customerId: string;
  customerName: string;
  customerEmail: string;
  qualityScore: number;
  confidenceScore: number;
  techniqueUsed: string;
  resolutionTime?: number;
  createdAt: string;
  updatedAt: string;
  messages: TicketMessage[];
  tags: string[];
  escalationReason?: string;
}

export interface TicketMessage {
  id: string;
  sender: 'customer' | 'ai' | 'agent';
  content: string;
  timestamp: string;
  metadata?: {
    technique?: string;
    confidence?: number;
    latency?: number;
    model?: string;
  };
}

// --- Monitoring Types ---
export interface ProviderHealth {
  provider: string;
  status: 'healthy' | 'degraded' | 'down';
  latency: number;
  uptime: number;
  models: ModelStatus[];
  circuitBreakerState: 'closed' | 'open' | 'half_open';
  lastChecked: string;
}

export interface ModelStatus {
  name: string;
  available: boolean;
  latency: number;
  costPer1kTokens: number;
}

export interface FailoverEvent {
  id: string;
  fromProvider: string;
  toProvider: string;
  fromModel: string;
  toModel: string;
  reason: string;
  triggeredAt: string;
  recoveredAt?: string;
  duration: number;
}

export interface ColdStartStatus {
  tenantId: string;
  tenantName: string;
  warmupState: 'cold' | 'warming' | 'warm' | 'hot';
  lastAccessed: string;
  warmupProgress: number;
  estimatedTime?: number;
}

export interface QualityMetrics {
  avgConfidenceScore: number;
  guardrailPassRate: number;
  hallucinationRate: number;
  piiDetectionRate: number;
  sentimentAccuracy: number;
  intentClassificationAccuracy: number;
}

export interface PerformanceMetrics {
  latencyByVariant: { variant: VariantType; avg: number; p50: number; p95: number; p99: number }[];
  costByVariant: { variant: VariantType; costPerQuery: number; totalCost: number; queryCount: number }[];
  techniqueUsage: { technique: string; count: number; avgLatency: number; avgConfidence: number }[];
}

export interface MonitoringAlert {
  id: string;
  severity: 'critical' | 'warning' | 'info';
  title: string;
  message: string;
  source: string;
  timestamp: string;
  acknowledged: boolean;
}

// --- Channel Types ---
export interface ChannelConfig {
  type: ChannelType;
  enabled: boolean;
  provider: string;
  config: Record<string, unknown>;
  stats: ChannelStats;
}

export interface ChannelStats {
  inboundToday: number;
  outboundToday: number;
  avgResponseTime: number;
  successRate: number;
  errorRate: number;
}

export interface EmailChannelConfig extends ChannelConfig {
  type: 'email';
  brevoApiKey?: string;
  inboundAddress: string;
  oooDetectionEnabled: boolean;
  oooDetectedCount: number;
}

export interface SMSChannelConfig extends ChannelConfig {
  type: 'sms';
  twilioPhone: string;
  twilioAccountSid?: string;
}

export interface ChatWidgetConfig extends ChannelConfig {
  type: 'chat';
  widgetColor: string;
  position: 'bottom-right' | 'bottom-left';
  greeting: string;
  embedCode: string;
}

export interface VoiceChannelConfig extends ChannelConfig {
  type: 'voice';
  twilioPhone: string;
  ivrEnabled: boolean;
  ivrMenu: string;
}

// --- Billing Types ---
export interface Subscription {
  id: string;
  planId: string;
  planName: string;
  status: 'active' | 'past_due' | 'canceled' | 'trialing';
  currentPeriodStart: string;
  currentPeriodEnd: string;
  nextBillingDate: string;
  amount: number;
  currency: string;
  paddleSubscriptionId?: string;
}

export interface UsageRecord {
  date: string;
  variant: VariantType;
  tokensUsed: number;
  queryCount: number;
  cost: number;
}

export interface Invoice {
  id: string;
  number: string;
  date: string;
  amount: number;
  currency: string;
  status: 'paid' | 'pending' | 'overdue' | 'void';
  pdfUrl: string;
}

export interface PaymentMethod {
  id: string;
  type: 'card' | 'bank_transfer';
  last4: string;
  brand?: string;
  expiryMonth?: number;
  expiryYear?: number;
  isDefault: boolean;
}

// --- Knowledge Base Types ---
export interface KnowledgeDocument {
  id: string;
  name: string;
  type: 'pdf' | 'docx' | 'txt' | 'csv' | 'url';
  size: number;
  chunkCount: number;
  lastIndexed: string;
  status: 'indexed' | 'indexing' | 'error' | 'pending';
  uploadDate: string;
}

export interface SearchMetrics {
  avgRelevanceScore: number;
  retrievalLatency: number;
  hitRate: number;
  totalQueries: number;
  failedQueries: number;
}

// --- Jarvis Chat Types ---
export interface ChatSession {
  id: string;
  variant: VariantType;
  startedAt: string;
  endedAt?: string;
  messageCount: number;
  qualityScore?: number;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  variant?: VariantType;
  technique?: string;
  confidence?: number;
  isStreaming?: boolean;
}

// --- Settings Types ---
export interface APIKey {
  id: string;
  name: string;
  key: string;
  scope: string[];
  createdAt: string;
  lastUsed?: string;
  status: 'active' | 'revoked';
}

export interface Integration {
  id: string;
  name: string;
  provider: 'paddle' | 'brevo' | 'twilio' | 'shopify';
  status: 'connected' | 'disconnected' | 'error';
  connectedAt?: string;
  lastSync?: string;
  config: Record<string, unknown>;
}

export interface NotificationPreference {
  event: string;
  email: boolean;
  sms: boolean;
  push: boolean;
  inApp: boolean;
}

export interface CompanySettings {
  brandVoice: string;
  toneGuidelines: string;
  piiPatterns: string[];
  ragConfig: {
    chunkSize: number;
    overlap: number;
    topK: number;
    similarityThreshold: number;
  };
}

// --- Dashboard KPI Types ---
export interface KPICard {
  title: string;
  value: string | number;
  change: number;
  changeLabel: string;
  icon: string;
  trend: 'up' | 'down' | 'neutral';
}

export interface AutomationTrendPoint {
  date: string;
  automationRate: number;
  target: number;
}

export interface VariantDistribution {
  name: string;
  value: number;
  color: string;
}

export interface ChannelDistribution {
  channel: string;
  tickets: number;
  resolved: number;
}

// --- Navigation Types ---
export type PageId = 
  | 'auth'
  | 'dashboard'
  | 'variants'
  | 'monitoring'
  | 'tickets'
  | 'channels'
  | 'billing'
  | 'knowledge'
  | 'jarvis'
  | 'settings';

export interface NavigationItem {
  id: PageId;
  label: string;
  icon: string;
  badge?: number;
}
