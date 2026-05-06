// ============================================================
// Parwa Variant Engine Dashboard - API Client (Mock)
// ============================================================

import {
  mockUser, mockKPICards, mockAutomationTrend, mockVariantDistribution,
  mockChannelDistribution, mockVariantInstances, mockVariantCapabilities,
  mockEntitlements, mockTokenBudget, mockTickets, mockProviderHealth,
  mockFailoverEvents, mockColdStartStatus, mockQualityMetrics,
  mockPerformanceMetrics, mockMonitoringAlerts, mockEmailChannel,
  mockSMSChannel, mockChatWidget, mockVoiceChannel, mockSubscription,
  mockUsageRecords, mockInvoices, mockPaymentMethods, mockKnowledgeDocuments,
  mockSearchMetrics, mockChatMessages, mockAPIKeys, mockIntegrations,
  mockNotificationPreferences, mockCompanySettings, mockChatSessions,
} from './mock-data';
import type {
  User, KPICard, AutomationTrendPoint, VariantDistribution, ChannelDistribution,
  VariantInstance, VariantCapability, Entitlement, TokenBudget, Ticket,
  ProviderHealth, FailoverEvent, ColdStartStatus, QualityMetrics,
  PerformanceMetrics, MonitoringAlert, EmailChannelConfig, SMSChannelConfig,
  ChatWidgetConfig, VoiceChannelConfig, Subscription, UsageRecord, Invoice,
  PaymentMethod, KnowledgeDocument, SearchMetrics, ChatMessage, ChatSession,
  APIKey, Integration, NotificationPreference, CompanySettings, VariantType,
  TicketStatus, ChannelType,
} from './types';

// Simulate API delay
const delay = (ms: number = 300) => new Promise(resolve => setTimeout(resolve, ms));

// --- Dashboard API ---
export async function fetchKPIs(): Promise<KPICard[]> {
  await delay(400);
  return mockKPICards;
}

export async function fetchAutomationTrend(): Promise<AutomationTrendPoint[]> {
  await delay(500);
  return mockAutomationTrend;
}

export async function fetchVariantDistribution(): Promise<VariantDistribution[]> {
  await delay(300);
  return mockVariantDistribution;
}

export async function fetchChannelDistribution(): Promise<ChannelDistribution[]> {
  await delay(300);
  return mockChannelDistribution;
}

// --- Variants API ---
export async function fetchVariantInstances(): Promise<VariantInstance[]> {
  await delay(400);
  return mockVariantInstances;
}

export async function fetchVariantCapabilities(): Promise<VariantCapability[]> {
  await delay(300);
  return mockVariantCapabilities;
}

export async function fetchEntitlements(): Promise<Entitlement[]> {
  await delay(200);
  return mockEntitlements;
}

export async function fetchTokenBudget(): Promise<TokenBudget> {
  await delay(200);
  return mockTokenBudget;
}

export async function createVariantInstance(data: Partial<VariantInstance>): Promise<VariantInstance> {
  await delay(600);
  return {
    id: `vi_${Date.now()}`,
    name: data.name || 'New Instance',
    type: data.type || 'mini_parwa',
    status: 'active',
    channel: data.channel || 'chat',
    capacity: data.capacity || 500,
    currentLoad: 0,
    accuracyRate: 0,
    avgLatency: 0,
    costPerQuery: data.type === 'mini_parwa' ? 0.003 : data.type === 'parwa' ? 0.008 : 0.015,
    techniqueTier: data.type === 'mini_parwa' ? 1 : data.type === 'parwa' ? 2 : 3,
    nodeCount: data.type === 'mini_parwa' ? 10 : data.type === 'parwa' ? 22 : 27,
    model: data.type === 'mini_parwa' ? 'gpt-4o-mini' : 'gpt-4o',
    createdAt: new Date().toISOString(),
    lastActive: new Date().toISOString(),
  };
}

// --- Tickets API ---
export async function fetchTickets(filters?: {
  status?: TicketStatus | 'all';
  variant?: VariantType | 'all';
  channel?: ChannelType | 'all';
  priority?: string | 'all';
  search?: string;
}): Promise<Ticket[]> {
  await delay(400);
  let filtered = [...mockTickets];
  if (filters) {
    if (filters.status && filters.status !== 'all') {
      filtered = filtered.filter(t => t.status === filters.status);
    }
    if (filters.variant && filters.variant !== 'all') {
      filtered = filtered.filter(t => t.variant === filters.variant);
    }
    if (filters.channel && filters.channel !== 'all') {
      filtered = filtered.filter(t => t.channel === filters.channel);
    }
    if (filters.priority && filters.priority !== 'all') {
      filtered = filtered.filter(t => t.priority === filters.priority);
    }
    if (filters.search) {
      const q = filters.search.toLowerCase();
      filtered = filtered.filter(t =>
        t.subject.toLowerCase().includes(q) ||
        t.customerName.toLowerCase().includes(q) ||
        t.id.toLowerCase().includes(q)
      );
    }
  }
  return filtered;
}

export async function fetchTicketById(id: string): Promise<Ticket | undefined> {
  await delay(200);
  return mockTickets.find(t => t.id === id);
}

// --- Monitoring API ---
export async function fetchProviderHealth(): Promise<ProviderHealth[]> {
  await delay(300);
  return mockProviderHealth;
}

export async function fetchFailoverEvents(): Promise<FailoverEvent[]> {
  await delay(300);
  return mockFailoverEvents;
}

export async function fetchColdStartStatus(): Promise<ColdStartStatus[]> {
  await delay(200);
  return mockColdStartStatus;
}

export async function fetchQualityMetrics(): Promise<QualityMetrics> {
  await delay(200);
  return mockQualityMetrics;
}

export async function fetchPerformanceMetrics(): Promise<PerformanceMetrics> {
  await delay(300);
  return mockPerformanceMetrics;
}

export async function fetchMonitoringAlerts(): Promise<MonitoringAlert[]> {
  await delay(200);
  return mockMonitoringAlerts;
}

export async function acknowledgeAlert(alertId: string): Promise<void> {
  await delay(200);
  const alert = mockMonitoringAlerts.find(a => a.id === alertId);
  if (alert) alert.acknowledged = true;
}

export async function triggerWarmup(tenantId: string): Promise<void> {
  await delay(500);
  const tenant = mockColdStartStatus.find(t => t.tenantId === tenantId);
  if (tenant) {
    tenant.warmupState = 'warming';
    tenant.warmupProgress = 10;
  }
}

// --- Channels API ---
export async function fetchEmailChannel(): Promise<EmailChannelConfig> {
  await delay(200);
  return mockEmailChannel;
}

export async function fetchSMSChannel(): Promise<SMSChannelConfig> {
  await delay(200);
  return mockSMSChannel;
}

export async function fetchChatWidgetConfig(): Promise<ChatWidgetConfig> {
  await delay(200);
  return mockChatWidget;
}

export async function fetchVoiceChannel(): Promise<VoiceChannelConfig> {
  await delay(200);
  return mockVoiceChannel;
}

// --- Billing API ---
export async function fetchSubscription(): Promise<Subscription> {
  await delay(200);
  return mockSubscription;
}

export async function fetchUsageRecords(): Promise<UsageRecord[]> {
  await delay(300);
  return mockUsageRecords;
}

export async function fetchInvoices(): Promise<Invoice[]> {
  await delay(200);
  return mockInvoices;
}

export async function fetchPaymentMethods(): Promise<PaymentMethod[]> {
  await delay(200);
  return mockPaymentMethods;
}

// --- Knowledge Base API ---
export async function fetchKnowledgeDocuments(): Promise<KnowledgeDocument[]> {
  await delay(300);
  return mockKnowledgeDocuments;
}

export async function fetchSearchMetrics(): Promise<SearchMetrics> {
  await delay(200);
  return mockSearchMetrics;
}

export async function uploadDocument(file: File): Promise<KnowledgeDocument> {
  await delay(1000);
  return {
    id: `kd_${Date.now()}`,
    name: file.name,
    type: file.name.split('.').pop() as KnowledgeDocument['type'],
    size: file.size,
    chunkCount: 0,
    lastIndexed: new Date().toISOString(),
    status: 'indexing',
    uploadDate: new Date().toISOString().split('T')[0],
  };
}

export async function reindexDocument(docId: string): Promise<void> {
  await delay(800);
  const doc = mockKnowledgeDocuments.find(d => d.id === docId);
  if (doc) {
    doc.status = 'indexing';
    setTimeout(() => { doc.status = 'indexed'; doc.lastIndexed = new Date().toISOString(); }, 2000);
  }
}

// --- Jarvis Chat API ---
export async function fetchChatMessages(sessionId: string): Promise<ChatMessage[]> {
  await delay(200);
  if (sessionId === 'cs_001' || !sessionId) return mockChatMessages;
  return [];
}

export async function sendChatMessage(content: string, _variant: VariantType): Promise<ChatMessage> {
  await delay(1500);
  const responses = [
    "I understand your concern. Let me look into this for you right away.",
    "Thank you for reaching out. I've found the information you need.",
    "I can definitely help with that. Here's what I recommend...",
    "Let me check our system for the latest updates on your request.",
    "I appreciate your patience. I've processed your request successfully.",
  ];
  return {
    id: `cm_${Date.now()}`,
    role: 'assistant',
    content: responses[Math.floor(Math.random() * responses.length)],
    timestamp: new Date().toISOString(),
    variant: _variant,
    technique: _variant === 'parwa_high' ? 'GST' : _variant === 'parwa' ? 'Chain of Thought' : 'CLARA',
    confidence: 0.85 + Math.random() * 0.12,
  };
}

export async function fetchChatSessions(): Promise<ChatSession[]> {
  await delay(200);
  return mockChatSessions;
}

// --- Settings API ---
export async function fetchAPIKeys(): Promise<APIKey[]> {
  await delay(200);
  return mockAPIKeys;
}

export async function createAPIKey(name: string, scope: string[]): Promise<APIKey> {
  await delay(400);
  return {
    id: `ak_${Date.now()}`,
    name,
    key: `pk_live_${Math.random().toString(36).substr(2, 24)}`,
    scope,
    createdAt: new Date().toISOString(),
    status: 'active',
  };
}

export async function revokeAPIKey(keyId: string): Promise<void> {
  await delay(200);
  const key = mockAPIKeys.find(k => k.id === keyId);
  if (key) key.status = 'revoked';
}

export async function fetchIntegrations(): Promise<Integration[]> {
  await delay(200);
  return mockIntegrations;
}

export async function fetchNotificationPreferences(): Promise<NotificationPreference[]> {
  await delay(200);
  return mockNotificationPreferences;
}

export async function updateNotificationPreferences(_prefs: NotificationPreference[]): Promise<void> {
  await delay(300);
}

export async function fetchCompanySettings(): Promise<CompanySettings> {
  await delay(200);
  return mockCompanySettings;
}

export async function updateCompanySettings(_settings: Partial<CompanySettings>): Promise<void> {
  await delay(400);
}

export async function fetchUserProfile(): Promise<User> {
  await delay(200);
  return mockUser;
}

export async function updateUserProfile(_data: Partial<User>): Promise<User> {
  await delay(400);
  return { ...mockUser, ..._data };
}

export async function changePassword(_currentPassword: string, _newPassword: string): Promise<void> {
  await delay(500);
}

export async function enableMFA(): Promise<{ secret: string; qrCode: string }> {
  await delay(500);
  return { secret: 'JBSWY3DPEHPK3PXP', qrCode: 'otpauth://totp/Parwa:admin@parwa.ai?secret=JBSWY3DPEHPK3PXP' };
}
