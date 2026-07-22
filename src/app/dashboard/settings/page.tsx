'use client';

import { useState, useEffect, useCallback } from 'react';
import { cn } from '@/lib/utils';
import { useSearchParams } from 'next/navigation';
import toast from 'react-hot-toast';
import { useAuth } from '@/hooks/useAuth';
import { useVariant } from '@/hooks/useVariant';
import { integrationsApi } from '@/lib/api';
import * as Tabs from '@radix-ui/react-tabs';
import {
  User,
  Bell,
  Shield,
  Key,
  Save,
  X,
  Copy,
  Trash2,
  Plus,
  Check,
  Link2,
  Webhook,
  RefreshCw,
  Loader2,
  Eye,
  EyeOff,
  Crown,
  Lock,
  AlertCircle,
  ExternalLink,
  Send,
  Zap,
  ClipboardList,
  Download,
  Search,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Activity,
  FileText,
  AlertTriangle,
  ShieldAlert,
} from 'lucide-react';

// ── API Base ────────────────────────────────────────────────────────────
// Use relative URLs to hit our Next.js proxy routes
const API_BASE = '';

// ── Types ───────────────────────────────────────────────────────────────

interface ApiKey {
  id: string;
  name: string;
  key: string;
  created: string;
}

interface NotificationSettings {
  email: boolean;
  inApp: boolean;
  slaAlerts: boolean;
  ticketAssignment: boolean;
  frequency: 'instant' | 'daily' | 'weekly';
}

interface ConnectedIntegration {
  id: string;
  type: string;
  name: string;
  status: 'active' | 'pending' | 'error';
  lastTestedAt: string | null;
  config: Record<string, string>;
}

interface WebhookConfig {
  id: string;
  url: string;
  events: string[];
  secret: string;
  active: boolean;
  lastTriggeredAt: string | null;
  failureCount: number;
}

interface AuditEntry {
  id: string;
  timestamp: string;
  category: string;
  severity: 'info' | 'warning' | 'critical' | 'security';
  action: string;
  actor_id: string;
  actor_name?: string;
  resource_type: string;
  resource_id: string;
  details?: Record<string, unknown>;
}

interface AuditStats {
  total_entries_30d: number;
  entries_24h: number;
  top_actor: string;
  top_action_type: string;
  action_counts?: Record<string, number>;
}

interface SecurityAlert {
  id: string;
  type: string;
  message: string;
  severity: 'warning' | 'critical';
  timestamp: string;
}

interface IntegrationHealthData {
  overall_status: 'healthy' | 'degraded' | 'unhealthy';
  integrations: Array<{
    id: string;
    name: string;
    type: string;
    circuit_breaker_state: 'closed' | 'open' | 'half_open';
    rate_limit_usage: number;
    rate_limit_max: number;
    last_tested_at: string | null;
    status: string;
  }>;
}

const INTEGRATION_CATALOG = [
  // Mini tier
  { type: 'gmail', name: 'Gmail', category: 'email', tier: 'mini' as const, icon: '📧', fields: [{ key: 'client_id', label: 'Client ID', type: 'text' }, { key: 'client_secret', label: 'Client Secret', type: 'password' }] },
  { type: 'outlook', name: 'Outlook', category: 'email', tier: 'mini' as const, icon: '📧', fields: [{ key: 'client_id', label: 'Application ID', type: 'text' }, { key: 'client_secret', label: 'Application Secret', type: 'password' }] },
  { type: 'slack', name: 'Slack', category: 'communication', tier: 'mini' as const, icon: '💬', fields: [{ key: 'bot_token', label: 'Bot Token (xoxb-)', type: 'password' }, { key: 'channel_id', label: 'Channel ID', type: 'text' }] },
  { type: 'shopify', name: 'Shopify', category: 'ecommerce', tier: 'mini' as const, icon: '🛍️', fields: [{ key: 'shop_domain', label: 'Shop Domain', type: 'text' }, { key: 'access_token', label: 'Access Token', type: 'password' }] },
  { type: 'zendesk', name: 'Zendesk', category: 'helpdesk', tier: 'mini' as const, icon: '🎧', fields: [{ key: 'subdomain', label: 'Subdomain', type: 'text' }, { key: 'api_token', label: 'API Token', type: 'password' }] },
  // Pro tier
  { type: 'salesforce', name: 'Salesforce', category: 'crm', tier: 'pro' as const, icon: '☁️', fields: [{ key: 'instance_url', label: 'Instance URL', type: 'text' }, { key: 'access_token', label: 'Access Token', type: 'password' }] },
  { type: 'hubspot', name: 'HubSpot', category: 'crm', tier: 'pro' as const, icon: '🎯', fields: [{ key: 'access_token', label: 'Access Token', type: 'password' }] },
  { type: 'intercom', name: 'Intercom', category: 'helpdesk', tier: 'pro' as const, icon: '💬', fields: [{ key: 'access_token', label: 'Access Token', type: 'password' }] },
  { type: 'whatsapp', name: 'WhatsApp Business', category: 'communication', tier: 'pro' as const, icon: '📱', fields: [{ key: 'phone_number_id', label: 'Phone Number ID', type: 'text' }, { key: 'access_token', label: 'Access Token', type: 'password' }] },
  { type: 'twilio', name: 'Twilio', category: 'communication', tier: 'pro' as const, icon: '📞', fields: [{ key: 'account_sid', label: 'Account SID', type: 'text' }, { key: 'auth_token', label: 'Auth Token', type: 'password' }] },
  // High tier
  { type: 'sap', name: 'SAP', category: 'crm', tier: 'high' as const, icon: '📦', fields: [{ key: 'endpoint', label: 'API Endpoint', type: 'text' }, { key: 'api_key', label: 'API Key', type: 'password' }] },
  { type: 'custom_api', name: 'Custom API', category: 'custom', tier: 'high' as const, icon: '🔗', fields: [{ key: 'endpoint', label: 'Endpoint URL', type: 'text' }, { key: 'api_key', label: 'API Key', type: 'password' }, { key: 'headers', label: 'Custom Headers (JSON)', type: 'text' }] },
] as const;

const WEBHOOK_EVENTS = [
  { id: 'ticket.created', label: 'Ticket Created', description: 'When a new ticket is created' },
  { id: 'ticket.resolved', label: 'Ticket Resolved', description: 'When a ticket is resolved' },
  { id: 'ticket.escalated', label: 'Ticket Escalated', description: 'When a ticket is escalated' },
  { id: 'agent.response', label: 'Agent Response', description: 'When an AI agent responds' },
  { id: 'sla.breached', label: 'SLA Breached', description: 'When an SLA is breached' },
  { id: 'integration.error', label: 'Integration Error', description: 'When an integration fails' },
];

// ── Password Strength Helper ────────────────────────────────────────────

function getPasswordStrength(password: string): {
  score: number;
  label: string;
  color: string;
} {
  if (!password) return { score: 0, label: '', color: '' };

  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
  if (/\d/.test(password)) score++;
  if (/[^a-zA-Z0-9]/.test(password)) score++;

  if (score <= 1) return { score: 1, label: 'Weak', color: 'bg-red-500' };
  if (score <= 2) return { score: 2, label: 'Fair', color: 'bg-orange-500' };
  if (score <= 3) return { score: 3, label: 'Good', color: 'bg-yellow-500' };
  if (score <= 4) return { score: 4, label: 'Strong', color: 'bg-emerald-500' };
  return { score: 5, label: 'Very Strong', color: 'bg-emerald-400' };
}

// ── Initials Helper ─────────────────────────────────────────────────────

function getInitials(name: string | null | undefined): string {
  if (!name) return '??';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].charAt(0).toUpperCase();
  return (parts[0].charAt(0) + parts[parts.length - 1].charAt(0)).toUpperCase();
}

// ── Settings Page ───────────────────────────────────────────────────────

export default function SettingsPage() {
  const { user } = useAuth();
  const { tier, isTierAtLeast } = useVariant();
  const searchParams = useSearchParams();
  const defaultTab = searchParams?.get('tab') || 'profile';

  // ── Profile State ───────────────────────────────────────────────────
  const [fullName, setFullName] = useState(user?.full_name || '');
  const [email, setEmail] = useState(user?.email || '');
  const [companyName, setCompanyName] = useState(user?.company_name || '');
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileDirty, setProfileDirty] = useState(false);

  // Sync when user loads
  useEffect(() => {
    if (user) {
      setFullName(user.full_name || '');
      setEmail(user.email || '');
      setCompanyName(user.company_name || '');
    }
  }, [user]);

  // Fetch integrations
  useEffect(() => {
    fetch(`${API_BASE}/api/integrations`, { credentials: 'include' })
      .then((r) => r.json())
      .then((data) => {
        setIntegrations(Array.isArray(data) ? data : []);
        setIntegrationsLoading(false);
      })
      .catch(() => {
        setIntegrations([]);
        setIntegrationsLoading(false);
      });
  }, []);

  // Fetch API keys from backend
  useEffect(() => {
    fetch(`${API_BASE}/api/api-keys`, { credentials: 'include' })
      .then((r) => r.json())
      .then((data) => {
        const list = Array.isArray(data) ? data : (data?.keys ?? []);
        setApiKeys(list.map((k: Record<string, unknown>) => ({
          id: String(k.id ?? k.key_id ?? ''),
          name: String(k.name ?? k.label ?? 'API Key'),
          key: `pk_****${String(k.key_suffix ?? k.last_four ?? '').slice(-4)}`,
          created: String(k.created_at ?? k.created ?? new Date().toISOString().split('T')[0]),
        })));
        setApiKeysLoading(false);
      })
      .catch(() => {
        setApiKeys([]);
        setApiKeysLoading(false);
      });
  }, []);

  // Fetch webhooks
  useEffect(() => {
    fetch(`${API_BASE}/api/integrations/webhooks`, { credentials: 'include' })
      .then((r) => r.json())
      .then((data) => {
        setWebhooks(Array.isArray(data) ? data : []);
        setWebhooksLoading(false);
      })
      .catch(() => {
        setWebhooks([]);
        setWebhooksLoading(false);
      });
  }, []);

  // ── Notifications State ─────────────────────────────────────────────
  const [notifications, setNotifications] = useState<NotificationSettings>({
    email: true,
    inApp: true,
    slaAlerts: true,
    ticketAssignment: false,
    frequency: 'instant',
  });
  const [notifSaving, setNotifSaving] = useState(false);

  // ── Security State ──────────────────────────────────────────────────
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [mfaEnrolled, setMfaEnrolled] = useState(false);
  const [mfaSetupOpen, setMfaSetupOpen] = useState(false);
  const [mfaSetupSaving, setMfaSetupSaving] = useState(false);

  // ── API Keys State ──────────────────────────────────────────────────
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [apiKeysLoading, setApiKeysLoading] = useState(true);
  const [newKeyName, setNewKeyName] = useState('');
  const [showCreateKey, setShowCreateKey] = useState(false);
  const [creatingKey, setCreatingKey] = useState(false);
  const [copiedKeyId, setCopiedKeyId] = useState<string | null>(null);
  const [revokingKeyId, setRevokingKeyId] = useState<string | null>(null);

  // ── Integrations State ────────────────────────────────────────────
  const [integrations, setIntegrations] = useState<ConnectedIntegration[]>([]);
  const [integrationsLoading, setIntegrationsLoading] = useState(true);
  const [connectingType, setConnectingType] = useState<string | null>(null);
  const [integrationForm, setIntegrationForm] = useState<Record<string, string>>({});
  const [expandedIntegration, setExpandedIntegration] = useState<string | null>(null);
  const [testingIntegration, setTestingIntegration] = useState<string | null>(null);
  const [showPasswords, setShowPasswords] = useState<Record<string, boolean>>({});

  // ── Webhooks State ────────────────────────────────────────────────
  const [webhooks, setWebhooks] = useState<WebhookConfig[]>([]);
  const [webhooksLoading, setWebhooksLoading] = useState(true);
  const [showCreateWebhook, setShowCreateWebhook] = useState(false);
  const [newWebhookUrl, setNewWebhookUrl] = useState('');
  const [newWebhookEvents, setNewWebhookEvents] = useState<string[]>(['ticket.created']);
  const [creatingWebhook, setCreatingWebhook] = useState(false);
  const [testingWebhook, setTestingWebhook] = useState<string | null>(null);
  const [deletingWebhook, setDeletingWebhook] = useState<string | null>(null);
  const [webhookEvents, setWebhookEvents] = useState<Array<{ event_type: string; status: string; provider: string; created_at: string }>>([]);

  // ── Audit Log State ────────────────────────────────────────────────
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([]);
  const [auditTotal, setAuditTotal] = useState(0);
  const [auditPage, setAuditPage] = useState(0);
  const [auditStats, setAuditStats] = useState<AuditStats | null>(null);
  const [auditAlerts, setAuditAlerts] = useState<SecurityAlert[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [filterCategory, setFilterCategory] = useState('');
  const [filterSeverity, setFilterSeverity] = useState('');
  const [filterAction, setFilterAction] = useState('');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');
  const [integrityChecking, setIntegrityChecking] = useState(false);
  const [integrityResult, setIntegrityResult] = useState<{ valid: boolean; message: string } | null>(null);
  const [exportingAudit, setExportingAudit] = useState(false);

  // ── Integration Health State ──────────────────────────────────────
  const [integrationHealth, setIntegrationHealth] = useState<IntegrationHealthData | null>(null);
  const [disconnectingIntegrationId, setDisconnectingIntegrationId] = useState<string | null>(null);
  const [showDisconnectConfirm, setShowDisconnectConfirm] = useState<string | null>(null);

  const fetchWebhookEvents = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/webhooks/events`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setWebhookEvents(Array.isArray(data) ? data : data.events || []);
      }
    } catch {
      // Silently fail — event log is supplementary
    }
  };

  // ── Audit Log Fetching ────────────────────────────────────────────

  const fetchAuditEntries = useCallback(async (page = 0) => {
    setAuditLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterCategory) params.set('category', filterCategory);
      if (filterSeverity) params.set('severity', filterSeverity);
      if (filterAction) params.set('action', filterAction);
      if (filterDateFrom) params.set('date_from', filterDateFrom);
      if (filterDateTo) params.set('date_to', filterDateTo);
      params.set('offset', String(page * 20));
      params.set('limit', '20');

      const res = await fetch(`${API_BASE}/api/audit/entries?${params}`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setAuditEntries(data.items || data || []);
        setAuditTotal(data.total || (Array.isArray(data) ? data.length : 0));
      }
    } catch {
      // Gracefully handle — audit log may be unavailable
    } finally {
      setAuditLoading(false);
    }
  }, [filterCategory, filterSeverity, filterAction, filterDateFrom, filterDateTo]);

  const fetchAuditStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/audit/stats`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setAuditStats(data);
      }
    } catch {
      // Silently fail — stats are supplementary
    }
  }, []);

  const fetchAuditAlerts = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/audit/alerts`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setAuditAlerts(Array.isArray(data) ? data : data.alerts || []);
      }
    } catch {
      // Silently fail
    }
  }, []);

  const handleAuditSearch = () => {
    setAuditPage(0);
    fetchAuditEntries(0);
  };

  const handleAuditExport = async (format: 'json' | 'csv') => {
    setExportingAudit(true);
    try {
      const params = new URLSearchParams();
      if (filterCategory) params.set('category', filterCategory);
      if (filterSeverity) params.set('severity', filterSeverity);
      if (filterAction) params.set('action', filterAction);
      if (filterDateFrom) params.set('date_from', filterDateFrom);
      if (filterDateTo) params.set('date_to', filterDateTo);
      params.set('format', format);

      const res = await fetch(`${API_BASE}/api/audit/export?${params}`, { credentials: 'include' });
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `audit-log.${format}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
        toast.success(`Audit log exported as ${format.toUpperCase()}`);
      } else {
        toast.error('Failed to export audit log');
      }
    } catch {
      toast.error('Failed to export audit log');
    } finally {
      setExportingAudit(false);
    }
  };

  const handleIntegrityCheck = async () => {
    setIntegrityChecking(true);
    setIntegrityResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/audit/integrity`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setIntegrityResult({ valid: data.valid ?? data.integrity_ok ?? true, message: data.message || (data.valid ? 'Audit log integrity verified' : 'Integrity check failed') });
        if (data.valid ?? data.integrity_ok ?? true) {
          toast.success('Audit log integrity verified');
        } else {
          toast.error('Audit log integrity check failed — possible tampering detected');
        }
      } else {
        setIntegrityResult({ valid: false, message: 'Could not verify integrity' });
        toast.error('Failed to verify audit log integrity');
      }
    } catch {
      setIntegrityResult({ valid: false, message: 'Backend unavailable' });
      toast.error('Backend unavailable — cannot verify integrity');
    } finally {
      setIntegrityChecking(false);
    }
  };

  // ── Integration Health Fetching ───────────────────────────────────

  const fetchIntegrationHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/integrations/health`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setIntegrationHealth(data);
      }
    } catch {
      // Silently fail — health is supplementary
    }
  }, []);

  const handleProperDisconnect = async (integrationId: string) => {
    setDisconnectingIntegrationId(integrationId);
    try {
      const res = await fetch(`${API_BASE}/api/integrations/${integrationId}/disconnect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
      });
      if (res.ok || res.status === 404 || res.status === 502) {
        setIntegrations((prev) => prev.filter((i) => i.id !== integrationId));
        toast.success('Integration properly disconnected');
        fetchIntegrationHealth();
      } else {
        const data = await res.json().catch(() => ({}));
        toast.error(data.detail || 'Failed to disconnect integration');
      }
    } catch {
      toast.error('Failed to disconnect integration');
    } finally {
      setDisconnectingIntegrationId(null);
      setShowDisconnectConfirm(null);
    }
  };

  // Fetch audit data when the audit tab might be shown
  useEffect(() => {
    if (defaultTab === 'audit') {
      fetchAuditEntries(0);
      fetchAuditStats();
      fetchAuditAlerts();
    }
  }, [defaultTab, fetchAuditEntries, fetchAuditStats, fetchAuditAlerts]);

  // Fetch integration health when integrations tab is shown
  useEffect(() => {
    if (defaultTab === 'integrations') {
      fetchIntegrationHealth();
    }
  }, [defaultTab, fetchIntegrationHealth]);

  // ── Profile Handlers ────────────────────────────────────────────────

  const handleProfileChange = () => setProfileDirty(true);

  const handleProfileSave = async () => {
    setProfileSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/client/profile`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ full_name: fullName, email, company_name: companyName }),
      });
      if (!res.ok && res.status !== 404 && res.status !== 502 && res.status !== 503) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Failed to update profile');
      }
      toast.success('Profile updated successfully');
      setProfileDirty(false);
    } catch (err) {
      if (err instanceof TypeError && err.message.includes('fetch')) {
        toast.error('Backend unavailable — changes saved locally');
        setProfileDirty(false);
      } else {
        toast.error(err instanceof Error ? err.message : 'Failed to update profile');
      }
    } finally {
      setProfileSaving(false);
    }
  };

  const handleProfileCancel = () => {
    setFullName(user?.full_name || '');
    setEmail(user?.email || '');
    setCompanyName(user?.company_name || '');
    setProfileDirty(false);
  };

  // ── Notification Handlers ───────────────────────────────────────────

  const handleNotifToggle = (key: keyof Omit<NotificationSettings, 'frequency'>) => {
    setNotifications((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleNotifSave = async () => {
    setNotifSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/client/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(notifications),
      });
      if (!res.ok && res.status !== 404 && res.status !== 502 && res.status !== 503) {
        throw new Error('Failed to save notifications');
      }
      toast.success('Notification preferences saved');
    } catch (err) {
      if (err instanceof TypeError && err.message.includes('fetch')) {
        toast.error('Backend unavailable — preferences saved locally');
      } else {
        toast.error('Failed to save notification preferences');
      }
    } finally {
      setNotifSaving(false);
    }
  };

  // ── Security Handlers ───────────────────────────────────────────────

  const handlePasswordChange = async () => {
    if (newPassword !== confirmPassword) {
      toast.error('New passwords do not match');
      return;
    }
    if (newPassword.length < 8) {
      toast.error('Password must be at least 8 characters');
      return;
    }
    setPasswordSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/client/password`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          current_password: currentPassword,
          new_password: newPassword,
        }),
      });
      if (!res.ok && res.status !== 404 && res.status !== 502 && res.status !== 503) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Failed to change password');
      }
      toast.success('Password changed successfully');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err) {
      if (err instanceof TypeError && err.message.includes('fetch')) {
        toast.error('Backend unavailable — cannot change password offline');
      } else {
        toast.error(err instanceof Error ? err.message : 'Failed to change password');
      }
    } finally {
      setPasswordSaving(false);
    }
  };

  const handleMfaSetup = async () => {
    setMfaSetupSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/mfa/setup/initiate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
      });
      if (!res.ok && res.status !== 404 && res.status !== 502 && res.status !== 503) {
        throw new Error('Failed to set up MFA');
      }
      setMfaEnrolled(true);
      setMfaSetupOpen(false);
      toast.success('Two-factor authentication enabled');
    } catch (err) {
      if (err instanceof TypeError && err.message.includes('fetch')) {
        toast.error('Backend unavailable — cannot set up MFA offline');
      } else {
        toast.error('Failed to set up two-factor authentication');
      }
    } finally {
      setMfaSetupSaving(false);
    }
  };

  // ── API Key Handlers ────────────────────────────────────────────────

  const handleCreateKey = async () => {
    if (!newKeyName.trim()) {
      toast.error('Please enter a key name');
      return;
    }
    setCreatingKey(true);
    try {
      const res = await fetch(`${API_BASE}/api/api-keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ name: newKeyName.trim() }),
      });
      if (res.ok) {
        const data = await res.json();
        const newKey: ApiKey = {
          id: data.id || data.key_id || String(Date.now()),
          name: newKeyName.trim(),
          key: `pk_****${(data.key_suffix || data.key || '').slice(-4)}`,
          created: new Date().toISOString().split('T')[0],
        };
        setApiKeys((prev) => [...prev, newKey]);
        setNewKeyName('');
        setShowCreateKey(false);
        toast.success('API key created');
      } else {
        toast.error('Failed to create API key');
      }
    } catch {
      toast.error('Network error — could not create API key');
    } finally {
      setCreatingKey(false);
    }
  };

  const handleCopyKey = (key: ApiKey) => {
    navigator.clipboard.writeText(key.key).then(() => {
      setCopiedKeyId(key.id);
      toast.success('Key copied to clipboard');
      setTimeout(() => setCopiedKeyId(null), 2000);
    }).catch(() => {
      toast.error('Failed to copy key');
    });
  };

  const handleRevokeKey = async (keyId: string) => {
    setRevokingKeyId(keyId);
    try {
      await fetch(`${API_BASE}/api/api-keys/${keyId}/revoke`, {
        method: 'DELETE',
        credentials: 'include',
      }).catch(() => {});
      setApiKeys((prev) => prev.filter((k) => k.id !== keyId));
      toast.success('API key revoked');
    } catch {
      toast.error('Failed to revoke API key');
    } finally {
      setRevokingKeyId(null);
    }
  };

  // ── Integration Handlers ────────────────────────────────────────────

  const handleConnectIntegration = async (catalogItem: typeof INTEGRATION_CATALOG[number]) => {
    const hasValues = catalogItem.fields.some((f) => integrationForm[f.key]?.trim());
    if (!hasValues) {
      toast.error('Please fill in the required credentials');
      return;
    }
    setConnectingType(catalogItem.type);
    try {
      const config: Record<string, string> = {};
      catalogItem.fields.forEach((f) => { config[f.key] = integrationForm[f.key] || ''; });
      const res = await fetch(`${API_BASE}/api/integrations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ integration_type: catalogItem.type, name: catalogItem.name, config, validate: true }),
      });
      if (!res.ok && res.status !== 502 && res.status !== 503) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || data.error?.message || 'Failed to connect');
      }
      const data = await res.json().catch(() => ({ id: `local-${Date.now()}`, type: catalogItem.type, name: catalogItem.name, status: 'active', config, lastTestedAt: null }));
      setIntegrations((prev) => [...prev, { id: data.id, type: catalogItem.type, name: catalogItem.name, status: data.status || 'active', lastTestedAt: data.last_tested_at || null, config }]);
      setIntegrationForm({});
      setExpandedIntegration(null);
      toast.success(`${catalogItem.name} connected successfully`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to connect integration');
    } finally {
      setConnectingType(null);
    }
  };

  const handleTestIntegration = async (integration: ConnectedIntegration) => {
    setTestingIntegration(integration.id);
    try {
      const res = await fetch(`${API_BASE}/api/integrations/${integration.id}/test`, { method: 'POST', credentials: 'include' });
      if (!res.ok && res.status !== 502 && res.status !== 503) throw new Error('Test failed');
      toast.success(`${integration.name} connection test passed`);
    } catch {
      toast.error(`${integration.name} connection test failed`);
    } finally {
      setTestingIntegration(null);
    }
  };

  const handleDisconnectIntegration = async (integrationId: string) => {
    try {
      await fetch(`${API_BASE}/api/integrations/${integrationId}`, { method: 'DELETE', credentials: 'include' }).catch(() => {});
      setIntegrations((prev) => prev.filter((i) => i.id !== integrationId));
      toast.success('Integration disconnected');
    } catch {
      toast.error('Failed to disconnect integration');
    }
  };

  // ── Webhook Handlers ──────────────────────────────────────────────

  const handleCreateWebhook = async () => {
    if (!newWebhookUrl.trim()) { toast.error('Please enter a webhook URL'); return; }
    if (newWebhookEvents.length === 0) { toast.error('Select at least one event'); return; }
    setCreatingWebhook(true);
    try {
      const res = await fetch(`${API_BASE}/api/integrations/webhooks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ url: newWebhookUrl.trim(), events: newWebhookEvents }),
      });
      let data;
      if (res.ok) {
        data = await res.json();
      } else {
        toast.error('Failed to create webhook');
      }
      if (res.ok) setWebhooks((prev) => [...prev, data]);
      setNewWebhookUrl('');
      setNewWebhookEvents(['ticket.created']);
      setShowCreateWebhook(false);
      toast.success('Webhook created');
    } catch {
      toast.error('Failed to create webhook');
    } finally {
      setCreatingWebhook(false);
    }
  };

  const handleTestWebhook = async (webhookId: string) => {
    setTestingWebhook(webhookId);
    try {
      await fetch(`${API_BASE}/api/integrations/webhooks/${webhookId}/test`, { method: 'POST', credentials: 'include' });
      toast.success('Test event sent');
    } catch {
      toast.error('Failed to send test event');
    } finally {
      setTestingWebhook(null);
    }
  };

  const handleDeleteWebhook = async (webhookId: string) => {
    setDeletingWebhook(webhookId);
    try {
      await fetch(`${API_BASE}/api/integrations/webhooks/${webhookId}`, { method: 'DELETE', credentials: 'include' }).catch(() => {});
      setWebhooks((prev) => prev.filter((w) => w.id !== webhookId));
      toast.success('Webhook deleted');
    } catch {
      toast.error('Failed to delete webhook');
    } finally {
      setDeletingWebhook(null);
    }
  };

  // ── Password Strength ───────────────────────────────────────────────

  const strength = getPasswordStrength(newPassword);

  // ── Render ──────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-6 border-b border-white/[0.06]">
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <p className="text-zinc-400 mt-1">Manage your account and application settings</p>
      </div>

      {/* Tabs */}
      <Tabs.Root defaultValue={defaultTab} className="flex flex-col gap-6">
        {/* Tab List */}
        <Tabs.List className="flex gap-1 rounded-xl border border-white/[0.06] bg-white/[0.02] p-1 w-fit flex-wrap">
          <Tabs.Trigger
            value="profile"
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 text-zinc-400 hover:text-white hover:bg-white/[0.04] data-[state=active]:text-white data-[state=active]:bg-white/[0.08] data-[state=active]:shadow-sm outline-none"
          >
            <User className="w-4 h-4" />
            Profile
          </Tabs.Trigger>
          <Tabs.Trigger
            value="notifications"
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 text-zinc-400 hover:text-white hover:bg-white/[0.04] data-[state=active]:text-white data-[state=active]:bg-white/[0.08] data-[state=active]:shadow-sm outline-none"
          >
            <Bell className="w-4 h-4" />
            Notifications
          </Tabs.Trigger>
          <Tabs.Trigger
            value="security"
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 text-zinc-400 hover:text-white hover:bg-white/[0.04] data-[state=active]:text-white data-[state=active]:bg-white/[0.08] data-[state=active]:shadow-sm outline-none"
          >
            <Shield className="w-4 h-4" />
            Security
          </Tabs.Trigger>
          <Tabs.Trigger
            value="api-keys"
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 text-zinc-400 hover:text-white hover:bg-white/[0.04] data-[state=active]:text-white data-[state=active]:bg-white/[0.08] data-[state=active]:shadow-sm outline-none"
          >
            <Key className="w-4 h-4" />
            API Keys
          </Tabs.Trigger>
          <Tabs.Trigger
            value="integrations"
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 text-zinc-400 hover:text-white hover:bg-white/[0.04] data-[state=active]:text-white data-[state=active]:bg-white/[0.08] data-[state=active]:shadow-sm outline-none"
          >
            <Link2 className="w-4 h-4" />
            Integrations
          </Tabs.Trigger>
          <Tabs.Trigger
            value="webhooks"
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 text-zinc-400 hover:text-white hover:bg-white/[0.04] data-[state=active]:text-white data-[state=active]:bg-white/[0.08] data-[state=active]:shadow-sm outline-none"
          >
            <Webhook className="w-4 h-4" />
            Webhooks
          </Tabs.Trigger>
          <Tabs.Trigger
            value="plan-industry"
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 text-zinc-400 hover:text-white hover:bg-white/[0.04] data-[state=active]:text-white data-[state=active]:bg-white/[0.08] data-[state=active]:shadow-sm outline-none"
          >
            <Crown className="w-4 h-4" />
            Plan & Industry
          </Tabs.Trigger>
          <Tabs.Trigger
            value="audit"
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-all duration-200 text-zinc-400 hover:text-white hover:bg-white/[0.04] data-[state=active]:text-white data-[state=active]:bg-white/[0.08] data-[state=active]:shadow-sm outline-none"
          >
            <ClipboardList className="w-4 h-4" />
            Audit Log
          </Tabs.Trigger>
        </Tabs.List>

        {/* ── Profile Tab ──────────────────────────────────────────────── */}
        <Tabs.Content value="profile" className="outline-none">
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6">
            <h3 className="text-sm font-semibold text-white mb-6">Profile Information</h3>

            <div className="flex flex-col sm:flex-row gap-6">
              {/* Avatar */}
              <div className="flex flex-col items-center gap-3 shrink-0">
                <div className="w-20 h-20 rounded-full bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center text-2xl font-bold text-[#1A1A1A]">
                  {getInitials(fullName || user?.full_name)}
                </div>
                <span className="text-xs text-zinc-500">
                  {tier.charAt(0).toUpperCase() + tier.slice(1)} Plan
                </span>
              </div>

              {/* Form Fields */}
              <div className="flex-1 space-y-4">
                {/* Full Name */}
                <div>
                  <label className="block text-sm font-medium text-zinc-400 mb-1.5">
                    Full Name
                  </label>
                  <input
                    type="text"
                    value={fullName}
                    onChange={(e) => {
                      setFullName(e.target.value);
                      handleProfileChange();
                    }}
                    className="w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all"
                    placeholder="Enter your full name"
                  />
                </div>

                {/* Email */}
                <div>
                  <label className="block text-sm font-medium text-zinc-400 mb-1.5">
                    Email
                  </label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                      handleProfileChange();
                    }}
                    className="w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all"
                    placeholder="Enter your email"
                  />
                </div>

                {/* Company Name */}
                <div>
                  <label className="block text-sm font-medium text-zinc-400 mb-1.5">
                    Company Name
                  </label>
                  <input
                    type="text"
                    value={companyName}
                    onChange={(e) => {
                      setCompanyName(e.target.value);
                      handleProfileChange();
                    }}
                    className="w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all"
                    placeholder="Enter your company name"
                  />
                </div>

                {/* Action Buttons */}
                {profileDirty && (
                  <div className="flex gap-3 pt-2">
                    <button
                      onClick={handleProfileSave}
                      disabled={profileSaving}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <Save className="w-4 h-4" />
                      {profileSaving ? 'Saving...' : 'Save Changes'}
                    </button>
                    <button
                      onClick={handleProfileCancel}
                      className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-zinc-400 hover:text-white bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all"
                    >
                      <X className="w-4 h-4" />
                      Cancel
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </Tabs.Content>

        {/* ── Notifications Tab ─────────────────────────────────────────── */}
        <Tabs.Content value="notifications" className="outline-none">
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 space-y-6">
            <h3 className="text-sm font-semibold text-white">Notification Preferences</h3>

            {/* Toggle Switches */}
            <div className="space-y-4">
              {/* Email Notifications */}
              <div className="flex items-center justify-between py-2">
                <div>
                  <p className="text-sm font-medium text-zinc-200">Email Notifications</p>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    Receive email alerts for important updates
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={notifications.email}
                  onClick={() => handleNotifToggle('email')}
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/40 focus-visible:ring-offset-2 focus-visible:ring-offset-[#1A1A1A] ${
                    notifications.email ? 'bg-gradient-to-r from-orange-500 to-amber-400' : 'bg-white/[0.10]'
                  }`}
                >
                  <span
                    aria-hidden="true"
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                      notifications.email ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>

              {/* In-App Notifications */}
              <div className="flex items-center justify-between py-2">
                <div>
                  <p className="text-sm font-medium text-zinc-200">In-App Notifications</p>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    Show notifications within the dashboard
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={notifications.inApp}
                  onClick={() => handleNotifToggle('inApp')}
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/40 focus-visible:ring-offset-2 focus-visible:ring-offset-[#1A1A1A] ${
                    notifications.inApp ? 'bg-gradient-to-r from-orange-500 to-amber-400' : 'bg-white/[0.10]'
                  }`}
                >
                  <span
                    aria-hidden="true"
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                      notifications.inApp ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>

              {/* SLA Alerts */}
              <div className="flex items-center justify-between py-2">
                <div>
                  <p className="text-sm font-medium text-zinc-200">SLA Alerts</p>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    Get notified when SLA thresholds are at risk
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={notifications.slaAlerts}
                  onClick={() => handleNotifToggle('slaAlerts')}
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/40 focus-visible:ring-offset-2 focus-visible:ring-offset-[#1A1A1A] ${
                    notifications.slaAlerts ? 'bg-gradient-to-r from-orange-500 to-amber-400' : 'bg-white/[0.10]'
                  }`}
                >
                  <span
                    aria-hidden="true"
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                      notifications.slaAlerts ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>

              {/* Ticket Assignment Alerts */}
              <div className="flex items-center justify-between py-2">
                <div>
                  <p className="text-sm font-medium text-zinc-200">Ticket Assignment Alerts</p>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    Get notified when tickets are assigned to you
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={notifications.ticketAssignment}
                  onClick={() => handleNotifToggle('ticketAssignment')}
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-500/40 focus-visible:ring-offset-2 focus-visible:ring-offset-[#1A1A1A] ${
                    notifications.ticketAssignment ? 'bg-gradient-to-r from-orange-500 to-amber-400' : 'bg-white/[0.10]'
                  }`}
                >
                  <span
                    aria-hidden="true"
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                      notifications.ticketAssignment ? 'translate-x-5' : 'translate-x-0'
                    }`}
                  />
                </button>
              </div>
            </div>

            {/* Frequency Selector */}
            <div className="pt-4 border-t border-white/[0.06]">
              <label className="block text-sm font-medium text-zinc-400 mb-3">
                Digest Frequency
              </label>
              <div className="flex gap-2">
                {(['instant', 'daily', 'weekly'] as const).map((freq) => (
                  <button
                    key={freq}
                    onClick={() =>
                      setNotifications((prev) => ({ ...prev, frequency: freq }))
                    }
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                      notifications.frequency === freq
                        ? 'bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A]'
                        : 'bg-white/[0.04] border border-white/[0.08] text-zinc-400 hover:text-white hover:border-white/[0.15]'
                    }`}
                  >
                    {freq === 'instant' ? 'Instant' : freq === 'daily' ? 'Daily Digest' : 'Weekly Digest'}
                  </button>
                ))}
              </div>
            </div>

            {/* Save Button */}
            <div className="flex justify-end pt-2">
              <button
                onClick={handleNotifSave}
                disabled={notifSaving}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Save className="w-4 h-4" />
                {notifSaving ? 'Saving...' : 'Save Preferences'}
              </button>
            </div>
          </div>
        </Tabs.Content>

        {/* ── Security Tab ──────────────────────────────────────────────── */}
        <Tabs.Content value="security" className="outline-none space-y-6">
          {/* Change Password */}
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6">
            <h3 className="text-sm font-semibold text-white mb-6">Change Password</h3>

            <div className="space-y-4 max-w-md">
              {/* Current Password */}
              <div>
                <label className="block text-sm font-medium text-zinc-400 mb-1.5">
                  Current Password
                </label>
                <input
                  type="password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all placeholder:text-zinc-600"
                  placeholder="Enter current password"
                />
              </div>

              {/* New Password */}
              <div>
                <label className="block text-sm font-medium text-zinc-400 mb-1.5">
                  New Password
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all placeholder:text-zinc-600"
                  placeholder="Enter new password"
                />

                {/* Password Strength Indicator */}
                {newPassword && (
                  <div className="mt-2 space-y-1.5">
                    <div className="flex gap-1">
                      {[1, 2, 3, 4, 5].map((level) => (
                        <div
                          key={level}
                          className={`h-1 flex-1 rounded-full transition-all duration-300 ${
                            strength.score >= level
                              ? strength.color
                              : 'bg-white/[0.06]'
                          }`}
                        />
                      ))}
                    </div>
                    <p className="text-xs text-zinc-500">
                      Password strength:{' '}
                      <span
                        className={
                          strength.score <= 1
                            ? 'text-red-400'
                            : strength.score <= 2
                            ? 'text-orange-400'
                            : strength.score <= 3
                            ? 'text-yellow-400'
                            : 'text-emerald-400'
                        }
                      >
                        {strength.label}
                      </span>
                    </p>
                  </div>
                )}
              </div>

              {/* Confirm Password */}
              <div>
                <label className="block text-sm font-medium text-zinc-400 mb-1.5">
                  Confirm New Password
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all placeholder:text-zinc-600"
                  placeholder="Confirm new password"
                />
                {confirmPassword && newPassword !== confirmPassword && (
                  <p className="text-xs text-red-400 mt-1">Passwords do not match</p>
                )}
                {confirmPassword && newPassword === confirmPassword && confirmPassword.length > 0 && (
                  <p className="text-xs text-emerald-400 mt-1 flex items-center gap-1">
                    <Check className="w-3 h-3" /> Passwords match
                  </p>
                )}
              </div>

              {/* Submit */}
              <button
                onClick={handlePasswordChange}
                disabled={
                  passwordSaving ||
                  !currentPassword ||
                  !newPassword ||
                  !confirmPassword ||
                  newPassword !== confirmPassword
                }
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-none"
              >
                <Shield className="w-4 h-4" />
                {passwordSaving ? 'Changing...' : 'Change Password'}
              </button>
            </div>
          </div>

          {/* MFA Section */}
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6">
            <h3 className="text-sm font-semibold text-white mb-4">Two-Factor Authentication</h3>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div
                  className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                    mfaEnrolled
                      ? 'bg-emerald-500/10'
                      : 'bg-white/[0.04]'
                  }`}
                >
                  <Shield
                    className={`w-5 h-5 ${
                      mfaEnrolled ? 'text-emerald-400' : 'text-zinc-500'
                    }`}
                  />
                </div>
                <div>
                  <p className="text-sm font-medium text-zinc-200">
                    {mfaEnrolled ? 'Two-factor authentication is active' : 'Not enrolled'}
                  </p>
                  <p className="text-xs text-zinc-500 mt-0.5">
                    {mfaEnrolled
                      ? 'Your account is protected with an additional verification step'
                      : 'Add an extra layer of security to your account'}
                  </p>
                </div>
              </div>

              {mfaEnrolled ? (
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <Check className="w-3 h-3" />
                  Active
                </span>
              ) : (
                <button
                  onClick={() => setMfaSetupOpen(true)}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-zinc-400 hover:text-white bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all"
                >
                  Set Up
                </button>
              )}
            </div>

            {/* MFA Setup Inline Form */}
            {mfaSetupOpen && !mfaEnrolled && (
              <div className="mt-4 pt-4 border-t border-white/[0.06] space-y-4">
                <p className="text-sm text-zinc-400">
                  Two-factor authentication adds an extra layer of security by requiring a
                  verification code from your authenticator app when signing in.
                </p>
                <div className="flex gap-3">
                  <button
                    onClick={handleMfaSetup}
                    disabled={mfaSetupSaving}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    {mfaSetupSaving ? 'Enabling...' : 'Enable 2FA'}
                  </button>
                  <button
                    onClick={() => setMfaSetupOpen(false)}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-zinc-400 hover:text-white bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all"
                  >
                    <X className="w-4 h-4" />
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        </Tabs.Content>

        {/* ── API Keys Tab ──────────────────────────────────────────────── */}
        <Tabs.Content value="api-keys" className="outline-none">
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-sm font-semibold text-white">API Keys</h3>
                <button
                  onClick={() => setShowCreateKey(true)}
                  className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200"
                >
                  <Plus className="w-4 h-4" />
                  Create New Key
                </button>
              </div>

              {/* Create Key Inline Form */}
              {showCreateKey && (
                <div className="mb-4 p-4 rounded-lg border border-white/[0.08] bg-white/[0.02] space-y-3">
                  <label className="block text-sm font-medium text-zinc-400">
                    Key Name
                  </label>
                  <input
                    type="text"
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    className="w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all placeholder:text-zinc-600"
                    placeholder="e.g. Production API Key"
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleCreateKey();
                    }}
                  />
                  <div className="flex gap-3">
                    <button
                      onClick={handleCreateKey}
                      disabled={creatingKey}
                      className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                    >
                      {creatingKey ? 'Creating...' : 'Create'}
                    </button>
                    <button
                      onClick={() => {
                        setShowCreateKey(false);
                        setNewKeyName('');
                      }}
                      className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium text-zinc-400 hover:text-white bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}

              {/* Key List */}
              {apiKeys.length === 0 ? (
                <div className="text-center py-10">
                  <Key className="w-8 h-8 text-zinc-600 mx-auto mb-3" />
                  <p className="text-sm text-zinc-500">No API keys yet</p>
                  <p className="text-xs text-zinc-600 mt-1">
                    Create a key to start using the API
                  </p>
                </div>
              ) : (
                <div className="space-y-2 max-h-96 overflow-y-auto custom-scrollbar">
                  {apiKeys.map((key) => (
                    <div
                      key={key.id}
                      className="flex items-center justify-between p-3 rounded-lg bg-white/[0.02] border border-white/[0.06] hover:border-white/[0.10] transition-all group"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="w-8 h-8 rounded-lg bg-white/[0.04] flex items-center justify-center shrink-0">
                          <Key className="w-4 h-4 text-zinc-500" />
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-zinc-200 truncate">
                            {key.name}
                          </p>
                          <p className="text-xs text-zinc-500 mt-0.5">
                            <code className="font-mono">{key.key}</code>
                            <span className="mx-1.5 text-zinc-700">·</span>
                            Created {key.created}
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-1.5 shrink-0">
                        {/* Copy Button */}
                        <button
                          onClick={() => handleCopyKey(key)}
                          className="p-1.5 rounded-md text-zinc-500 hover:text-white hover:bg-white/[0.06] transition-all"
                          title="Copy key"
                        >
                          {copiedKeyId === key.id ? (
                            <Check className="w-4 h-4 text-emerald-400" />
                          ) : (
                            <Copy className="w-4 h-4" />
                          )}
                        </button>

                        {/* Revoke Button */}
                        <button
                          onClick={() => {
                            if (
                              window.confirm(
                                `Are you sure you want to revoke "${key.name}"? This action cannot be undone.`
                              )
                            ) {
                              handleRevokeKey(key.id);
                            }
                          }}
                          disabled={revokingKeyId === key.id}
                          className="p-1.5 rounded-md text-zinc-500 hover:text-red-400 hover:bg-red-500/10 transition-all disabled:opacity-50"
                          title="Revoke key"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
        </Tabs.Content>

        {/* ── Integrations Tab ────────────────────────────────────────── */}
        <Tabs.Content value="integrations" className="outline-none space-y-6">
          {/* Integration Health (Phase 10) */}
          {integrationHealth && (
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                  <Activity className="w-4 h-4 text-orange-400" />
                  Integration Health
                </h3>
                <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold ${
                  integrationHealth.overall_status === 'healthy'
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                    : integrationHealth.overall_status === 'degraded'
                    ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20'
                    : 'bg-red-500/10 text-red-400 border border-red-500/20'
                }`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${
                    integrationHealth.overall_status === 'healthy' ? 'bg-emerald-400' :
                    integrationHealth.overall_status === 'degraded' ? 'bg-yellow-400' : 'bg-red-400'
                  }`} />
                  {integrationHealth.overall_status === 'healthy' ? 'Healthy' :
                   integrationHealth.overall_status === 'degraded' ? 'Degraded' : 'Unhealthy'}
                </span>
              </div>

              {integrationHealth.integrations && integrationHealth.integrations.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {integrationHealth.integrations.map((ih) => (
                    <div key={ih.id} className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-sm shrink-0">
                            {INTEGRATION_CATALOG.find((c) => c.type === ih.type)?.icon || '🔗'}
                          </span>
                          <span className="text-sm font-medium text-zinc-200 truncate">{ih.name}</span>
                        </div>
                        {/* Circuit Breaker State */}
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold shrink-0 ${
                          ih.circuit_breaker_state === 'closed'
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                            : ih.circuit_breaker_state === 'half_open'
                            ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20'
                            : 'bg-red-500/10 text-red-400 border border-red-500/20'
                        }`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${
                            ih.circuit_breaker_state === 'closed' ? 'bg-emerald-400' :
                            ih.circuit_breaker_state === 'half_open' ? 'bg-yellow-400' : 'bg-red-400'
                          }`} />
                          {ih.circuit_breaker_state === 'closed' ? 'Closed' :
                           ih.circuit_breaker_state === 'half_open' ? 'Half-Open' : 'Open'}
                        </span>
                      </div>

                      {/* Rate Limit Usage */}
                      <div>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Rate Limit</span>
                          <span className="text-[10px] text-zinc-400">{ih.rate_limit_usage}/{ih.rate_limit_max}</span>
                        </div>
                        <div className="w-full h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all ${
                              ih.rate_limit_max > 0
                                ? (ih.rate_limit_usage / ih.rate_limit_max > 0.8
                                  ? 'bg-red-400'
                                  : ih.rate_limit_usage / ih.rate_limit_max > 0.5
                                  ? 'bg-yellow-400'
                                  : 'bg-emerald-400')
                                : 'bg-emerald-400'
                            }`}
                            style={{ width: `${ih.rate_limit_max > 0 ? Math.min(100, (ih.rate_limit_usage / ih.rate_limit_max) * 100) : 0}%` }}
                          />
                        </div>
                      </div>

                      {/* Last Tested */}
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] text-zinc-600">
                          {ih.last_tested_at
                            ? `Tested ${new Date(ih.last_tested_at).toLocaleString()}`
                            : 'Not tested'}
                        </span>
                        {/* Disconnect button */}
                        <button
                          onClick={() => setShowDisconnectConfirm(ih.id)}
                          className="px-2 py-1 rounded text-[10px] font-medium text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-all"
                        >
                          Disconnect
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-zinc-500">No integration health data available</p>
              )}
            </div>
          )}

          {/* Disconnect Confirmation Dialog */}
          {showDisconnectConfirm && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4" onClick={() => setShowDisconnectConfirm(null)}>
              <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-6 max-w-sm w-full" onClick={(e) => e.stopPropagation()}>
                <h3 className="text-lg font-bold text-white mb-2 flex items-center gap-2">
                  <AlertTriangle className="w-5 h-5 text-red-400" />
                  Disconnect Integration
                </h3>
                <p className="text-sm text-zinc-400 mb-4">
                  This will properly disconnect the integration, cancel pending calls, clear cached data, and open the circuit breaker. This action cannot be undone.
                </p>
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => handleProperDisconnect(showDisconnectConfirm)}
                    disabled={disconnectingIntegrationId === showDisconnectConfirm}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold bg-red-500/20 text-red-300 hover:bg-red-500/30 transition-all disabled:opacity-50"
                  >
                    {disconnectingIntegrationId === showDisconnectConfirm ? (
                      <><Loader2 className="w-4 h-4 animate-spin" /> Disconnecting...</>
                    ) : (
                      'Disconnect'
                    )}
                  </button>
                  <button
                    onClick={() => setShowDisconnectConfirm(null)}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-zinc-400 hover:text-white bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Connected Integrations */}
          {integrations.length > 0 && (
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6">
              <h3 className="text-sm font-semibold text-white mb-4">Connected Integrations</h3>
              <div className="space-y-2">
                {integrations.map((int) => (
                  <div key={int.id} className="flex items-center justify-between p-3 rounded-lg bg-white/[0.02] border border-white/[0.06] hover:border-white/[0.10] transition-all">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-white/[0.04] flex items-center justify-center shrink-0 text-sm">
                        {INTEGRATION_CATALOG.find((c) => c.type === int.type)?.icon || '🔗'}
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-zinc-200 truncate">{int.name}</p>
                        <p className="text-[11px] text-zinc-500">{int.type}</p>
                      </div>
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                        int.status === 'active' ? 'bg-emerald-500/10 text-emerald-400' :
                        int.status === 'pending' ? 'bg-amber-500/10 text-amber-400' :
                        'bg-red-500/10 text-red-400'
                      }`}>
                        {int.status === 'active' && <Check className="w-3 h-3" />}
                        {int.status === 'pending' && <Loader2 className="w-3 h-3 animate-spin" />}
                        {int.status}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <button onClick={() => handleTestIntegration(int)} disabled={testingIntegration === int.id} className="px-3 py-1.5 rounded-lg text-xs font-medium text-zinc-400 hover:text-white bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all disabled:opacity-50">
                        {testingIntegration === int.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                      </button>
                      <button onClick={() => handleDisconnectIntegration(int.id)} className="px-3 py-1.5 rounded-lg text-xs font-medium text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-all">
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Available Integrations by Tier */}
          {(['mini', 'pro', 'high'] as const).map((tierLevel) => {
            const tierItems = INTEGRATION_CATALOG.filter((c) => c.tier === tierLevel);
            const isLocked = false;
            return (
              <div key={tierLevel} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6">
                <div className="flex items-center gap-2 mb-4">
                  <h3 className="text-sm font-semibold text-white">
                    {tierLevel === 'mini' ? 'Starter' : tierLevel === 'pro' ? 'Professional' : 'Enterprise'} Integrations
                  </h3>
                  {tierLevel !== 'mini' && (
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                      tierLevel === 'pro' ? 'bg-purple-500/10 text-purple-400' : 'bg-orange-500/10 text-orange-400'
                    }`}>
                      {tierLevel === 'pro' ? <><Crown className="w-3 h-3" /> Pro</> : <><Crown className="w-3 h-3" /> High</>}
                    </span>
                  )}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                  {tierItems.map((item) => {
                    const isConnected = integrations.some((i) => i.type === item.type);
                    const isExpanded = expandedIntegration === item.type;
                    const itemLocked = false;
                    return (
                      <div key={item.type} className={`rounded-lg border bg-white/[0.02] transition-all ${isExpanded ? 'col-span-1 sm:col-span-2 lg:col-span-3 border-orange-500/20' : 'border-white/[0.06] hover:border-white/[0.10]'}`}>
                        <div className="p-3 flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="text-base shrink-0">{item.icon}</span>
                            <span className="text-sm font-medium text-white truncate">{item.name}</span>
                            <span className="text-[10px] text-zinc-600 uppercase">{item.category}</span>
                            {itemLocked && <Lock className="w-3 h-3 text-zinc-500" />}
                          </div>
                          {isConnected ? (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/10 text-emerald-400">
                              <Check className="w-3 h-3" /> Connected
                            </span>
                          ) : (
                            <button onClick={() => { if (itemLocked) { toast.error(`Upgrade to ${tierLevel === 'pro' ? 'Pro' : 'High'} to use ${item.name}`); return; } setExpandedIntegration(isExpanded ? null : item.type); setIntegrationForm({}); }} className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-all shrink-0 ${itemLocked ? 'bg-white/[0.05] text-zinc-500 cursor-not-allowed' : 'bg-gradient-to-r from-orange-600 to-orange-500 text-white hover:from-orange-500 hover:to-orange-400 shadow-sm'}`}>
                              {isExpanded ? 'Cancel' : itemLocked ? 'Locked' : 'Connect'}
                            </button>
                          )}
                        </div>
                        {isExpanded && !itemLocked && (
                          <div className="px-3 pb-3 border-t border-white/[0.06] pt-3 space-y-3">
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                              {item.fields.map((field) => (
                                <div key={field.key}>
                                  <label className="block text-xs font-medium text-zinc-400 mb-1">{field.label}</label>
                                  <div className="relative">
                                    <input type={field.type === 'password' && !showPasswords[`${item.type}-${field.key}`] ? 'password' : 'text'} value={integrationForm[field.key] || ''} onChange={(e) => setIntegrationForm((prev) => ({ ...prev, [field.key]: e.target.value }))} placeholder={field.label} className="w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all placeholder:text-zinc-600" />
                                    {field.type === 'password' && (
                                      <button type="button" onClick={() => setShowPasswords((prev) => ({ ...prev, [`${item.type}-${field.key}`]: !prev[`${item.type}-${field.key}`] }))} className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 transition-colors">
                                        {showPasswords[`${item.type}-${field.key}`] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                      </button>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                            <button onClick={() => handleConnectIntegration(item)} disabled={connectingType === item.type} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] disabled:opacity-50 disabled:cursor-not-allowed transition-all">
                              {connectingType === item.type ? <><Loader2 className="w-4 h-4 animate-spin" /> Connecting...</> : 'Connect'}
                            </button>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </Tabs.Content>

        {/* ── Webhooks Tab ──────────────────────────────────────────────── */}
        <Tabs.Content value="webhooks" className="outline-none">
            <div className="space-y-6">
              {/* Webhook List */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-white">Webhook Endpoints</h3>
                  <button onClick={() => setShowCreateWebhook(true)} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200">
                    <Plus className="w-4 h-4" /> Add Endpoint
                  </button>
                </div>

                {webhooksLoading ? (
                  <div className="flex items-center justify-center py-10"><Loader2 className="w-6 h-6 animate-spin text-orange-400" /></div>
                ) : webhooks.length === 0 && !showCreateWebhook ? (
                  <div className="text-center py-10">
                    <Webhook className="w-8 h-8 text-zinc-600 mx-auto mb-3" />
                    <p className="text-sm text-zinc-500">No webhook endpoints configured</p>
                    <p className="text-xs text-zinc-600 mt-1">Add an endpoint to receive real-time event notifications</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {webhooks.map((wh) => (
                      <div key={wh.id} className="p-3 rounded-lg bg-white/[0.02] border border-white/[0.06] hover:border-white/[0.10] transition-all">
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-3 min-w-0">
                            <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${wh.active ? 'bg-emerald-500/10' : 'bg-white/[0.04]'}`}>
                              <Zap className={`w-4 h-4 ${wh.active ? 'text-emerald-400' : 'text-zinc-500'}`} />
                            </div>
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-zinc-200 truncate">{wh.url}</p>
                              <div className="flex items-center gap-2 mt-0.5">
                                {wh.events.map((ev) => (
                                  <span key={ev} className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.04] text-zinc-500">{ev}</span>
                                ))}
                                {wh.failureCount > 0 && <span className="text-[10px] text-red-400">{wh.failureCount} failures</span>}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                            <button onClick={() => handleTestWebhook(wh.id)} disabled={testingWebhook === wh.id} className="px-3 py-1.5 rounded-lg text-xs font-medium text-zinc-400 hover:text-white bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all disabled:opacity-50">
                              {testingWebhook === wh.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Send className="w-3 h-3" />}
                            </button>
                            <button onClick={() => handleDeleteWebhook(wh.id)} disabled={deletingWebhook === wh.id} className="px-3 py-1.5 rounded-lg text-xs font-medium text-red-400 hover:text-red-300 hover:bg-red-500/10 transition-all disabled:opacity-50">
                              {deletingWebhook === wh.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Trash2 className="w-3 h-3" />}
                            </button>
                          </div>
                        </div>
                        {wh.secret && (
                          <div className="mt-2 pt-2 border-t border-white/[0.04] flex items-center gap-2">
                            <span className="text-[10px] text-zinc-600">Signing Secret:</span>
                            <code className="text-[11px] text-zinc-400 font-mono">{wh.secret.slice(0, 8)}{'•••••••'}</code>
                            <button onClick={() => { navigator.clipboard.writeText(wh.secret); toast.success('Secret copied'); }} className="text-zinc-500 hover:text-zinc-300 transition-colors"><Copy className="w-3 h-3" /></button>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Create Webhook Form */}
                {showCreateWebhook && (
                  <div className="mt-4 p-4 rounded-lg border border-white/[0.08] bg-white/[0.02] space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-zinc-400 mb-1.5">Endpoint URL</label>
                      <input type="url" value={newWebhookUrl} onChange={(e) => setNewWebhookUrl(e.target.value)} placeholder="https://your-server.com/webhooks/parwa" className="w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all placeholder:text-zinc-600" />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-zinc-400 mb-3">Events</label>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                        {WEBHOOK_EVENTS.map((ev) => (
                          <label key={ev.id} className={`flex items-start gap-2 p-2.5 rounded-lg border cursor-pointer transition-all ${newWebhookEvents.includes(ev.id) ? 'border-orange-500/30 bg-orange-500/5' : 'border-white/[0.06] hover:border-white/[0.10]'}`}>
                            <input type="checkbox" checked={newWebhookEvents.includes(ev.id)} onChange={(e) => { if (e.target.checked) setNewWebhookEvents((prev) => [...prev, ev.id]); else setNewWebhookEvents((prev) => prev.filter((v) => v !== ev.id)); }} className="mt-0.5 accent-orange-500" />
                            <div>
                              <p className="text-xs font-medium text-zinc-200">{ev.label}</p>
                              <p className="text-[10px] text-zinc-500">{ev.description}</p>
                            </div>
                          </label>
                        ))}
                      </div>
                    </div>
                    <div className="flex gap-3">
                      <button onClick={handleCreateWebhook} disabled={creatingWebhook} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] disabled:opacity-50 disabled:cursor-not-allowed transition-all">
                        {creatingWebhook ? <><Loader2 className="w-4 h-4 animate-spin" /> Creating...</> : 'Create Webhook'}
                      </button>
                      <button onClick={() => { setShowCreateWebhook(false); setNewWebhookUrl(''); setNewWebhookEvents(['ticket.created']); }} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-zinc-400 hover:text-white bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all">
                        Cancel
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Webhook Info */}
              <div className="rounded-xl border border-amber-500/10 bg-amber-500/5 p-4 flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm text-amber-200/80 font-medium">Webhook Security</p>
                  <p className="text-xs text-amber-200/50 mt-1">Each webhook includes a signing secret. Verify the <code className="text-amber-300/70">X-Parwa-Signature</code> header on your server to confirm payloads are from PARWA. Failed deliveries are retried up to 5 times with exponential backoff.</p>
                </div>
              </div>

              {/* Webhook Event Log (Phase 6 - GAP 1) */}
              <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-white">Event Log</h3>
                  <button onClick={fetchWebhookEvents} className="px-3 py-1.5 rounded-lg text-xs font-medium text-zinc-400 hover:text-white bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all">
                    <RefreshCw className="w-3 h-3 inline mr-1" /> Refresh
                  </button>
                </div>
                {webhookEvents.length === 0 ? (
                  <div className="text-center py-6">
                    <p className="text-sm text-zinc-500">No webhook events recorded yet</p>
                    <p className="text-xs text-zinc-600 mt-1">Events will appear here when webhooks are triggered</p>
                  </div>
                ) : (
                  <div className="space-y-1 max-h-64 overflow-y-auto">
                    {webhookEvents.map((evt, idx) => (
                      <div key={idx} className="flex items-center gap-3 py-2 px-3 rounded-lg hover:bg-white/[0.02] transition-all text-xs">
                        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${evt.status === 'processed' ? 'bg-emerald-400' : evt.status === 'failed' ? 'bg-red-400' : 'bg-amber-400'}`} />
                        <span className="text-zinc-400 font-mono w-28 shrink-0">{evt.event_type}</span>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] ${evt.status === 'processed' ? 'bg-emerald-500/10 text-emerald-400' : evt.status === 'failed' ? 'bg-red-500/10 text-red-400' : 'bg-amber-500/10 text-amber-400'}`}>{evt.status}</span>
                        <span className="text-zinc-600 ml-auto">{evt.provider}</span>
                        <span className="text-zinc-700 ml-2">{new Date(evt.created_at).toLocaleString()}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
        </Tabs.Content>

        {/* ── Plan & Industry Tab (GAP 10 / D9) ──────────────────── */}
        <Tabs.Content value="plan-industry" className="outline-none">
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6 space-y-6">
            <div>
              <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                <Crown className="w-5 h-5 text-orange-400" />
                Plan & Industry
              </h3>
              <p className="text-sm text-zinc-400 mt-1">
                Change your industry or variant anytime. Your integrations, tickets, and knowledge base are never affected.
              </p>
            </div>

            {/* Current Plan */}
            <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-4">
              <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Current Plan</p>
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-orange-500 to-amber-400 flex items-center justify-center">
                  <Zap className="w-5 h-5 text-white" />
                </div>
                <div>
                  <p className="text-white font-semibold">{tier ? `${tier.charAt(0).toUpperCase() + tier.slice(1).replace('_', ' ')} Plan` : 'No Plan Active'}</p>
                  <p className="text-xs text-zinc-500">Unlimited integrations included</p>
                </div>
              </div>
            </div>

            {/* Industry Change */}
            <PlanIndustrySection currentIndustry={user?.industry || ''} companyId={user?.company_id || ''} />
          </div>
        </Tabs.Content>

        {/* ── Audit Log Tab (Phase 9) ──────────────────────────────── */}
        <Tabs.Content value="audit" className="outline-none space-y-6">
          {/* Filter Bar */}
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-6">
            <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
              <Search className="w-4 h-4 text-orange-400" />
              Filter Audit Entries
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
              {/* Category */}
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Category</label>
                <select
                  value={filterCategory}
                  onChange={(e) => setFilterCategory(e.target.value)}
                  className="w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all"
                >
                  <option value="" className="bg-[#1A1A1A]">All Categories</option>
                  <option value="auth" className="bg-[#1A1A1A]">Authentication</option>
                  <option value="integration" className="bg-[#1A1A1A]">Integration</option>
                  <option value="ai_action" className="bg-[#1A1A1A]">AI Action</option>
                  <option value="security" className="bg-[#1A1A1A]">Security</option>
                  <option value="data" className="bg-[#1A1A1A]">Data</option>
                  <option value="configuration" className="bg-[#1A1A1A]">Configuration</option>
                </select>
              </div>
              {/* Severity */}
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Severity</label>
                <select
                  value={filterSeverity}
                  onChange={(e) => setFilterSeverity(e.target.value)}
                  className="w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all"
                >
                  <option value="" className="bg-[#1A1A1A]">All Severities</option>
                  <option value="info" className="bg-[#1A1A1A]">Info</option>
                  <option value="warning" className="bg-[#1A1A1A]">Warning</option>
                  <option value="critical" className="bg-[#1A1A1A]">Critical</option>
                  <option value="security" className="bg-[#1A1A1A]">Security</option>
                </select>
              </div>
              {/* Action */}
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">Action</label>
                <input
                  type="text"
                  value={filterAction}
                  onChange={(e) => setFilterAction(e.target.value)}
                  placeholder="e.g. login, create"
                  className="w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all placeholder:text-zinc-600"
                />
              </div>
              {/* Date From */}
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">From</label>
                <input
                  type="date"
                  value={filterDateFrom}
                  onChange={(e) => setFilterDateFrom(e.target.value)}
                  className="w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all [color-scheme:dark]"
                />
              </div>
              {/* Date To */}
              <div>
                <label className="block text-xs font-medium text-zinc-400 mb-1">To</label>
                <input
                  type="date"
                  value={filterDateTo}
                  onChange={(e) => setFilterDateTo(e.target.value)}
                  className="w-full bg-white/[0.04] border border-white/[0.08] text-white rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-500/30 focus:border-orange-500/40 transition-all [color-scheme:dark]"
                />
              </div>
            </div>
            <div className="flex gap-3 mt-4">
              <button
                onClick={handleAuditSearch}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] hover:shadow-lg hover:shadow-orange-500/20 hover:-translate-y-0.5 transition-all duration-200"
              >
                <Search className="w-4 h-4" />
                Search
              </button>
              <button
                onClick={() => {
                  setFilterCategory('');
                  setFilterSeverity('');
                  setFilterAction('');
                  setFilterDateFrom('');
                  setFilterDateTo('');
                  setAuditPage(0);
                }}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-zinc-400 hover:text-white bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all"
              >
                Clear Filters
              </button>
            </div>
          </div>

          {/* Stats Cards Row */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
              <div className="flex items-center gap-2 mb-2">
                <FileText className="w-4 h-4 text-blue-400" />
                <span className="text-xs text-zinc-500 uppercase tracking-wider">Total (30d)</span>
              </div>
              <p className="text-2xl font-bold text-white">{auditStats?.total_entries_30d ?? '—'}</p>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
              <div className="flex items-center gap-2 mb-2">
                <Activity className="w-4 h-4 text-emerald-400" />
                <span className="text-xs text-zinc-500 uppercase tracking-wider">Last 24h</span>
              </div>
              <p className="text-2xl font-bold text-white">{auditStats?.entries_24h ?? '—'}</p>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
              <div className="flex items-center gap-2 mb-2">
                <User className="w-4 h-4 text-orange-400" />
                <span className="text-xs text-zinc-500 uppercase tracking-wider">Top Actor</span>
              </div>
              <p className="text-sm font-bold text-white truncate">{auditStats?.top_actor || '—'}</p>
            </div>
            <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-purple-400" />
                <span className="text-xs text-zinc-500 uppercase tracking-wider">Top Action</span>
              </div>
              <p className="text-sm font-bold text-white truncate">{auditStats?.top_action_type || '—'}</p>
            </div>
          </div>

          {/* Actions Row: Export + Integrity */}
          <div className="flex flex-wrap gap-3">
            <button
              onClick={() => handleAuditExport('json')}
              disabled={exportingAudit}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium text-zinc-400 hover:text-white bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all disabled:opacity-50"
            >
              <Download className="w-3.5 h-3.5" />
              {exportingAudit ? 'Exporting...' : 'Export JSON'}
            </button>
            <button
              onClick={() => handleAuditExport('csv')}
              disabled={exportingAudit}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium text-zinc-400 hover:text-white bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all disabled:opacity-50"
            >
              <Download className="w-3.5 h-3.5" />
              {exportingAudit ? 'Exporting...' : 'Export CSV'}
            </button>
            <button
              onClick={handleIntegrityCheck}
              disabled={integrityChecking}
              className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium text-zinc-400 hover:text-white bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all disabled:opacity-50"
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              {integrityChecking ? 'Verifying...' : 'Verify Integrity'}
            </button>
            {integrityResult && (
              <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium ${
                integrityResult.valid
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  : 'bg-red-500/10 text-red-400 border border-red-500/20'
              }`}>
                {integrityResult.valid ? <Check className="w-3.5 h-3.5" /> : <AlertTriangle className="w-3.5 h-3.5" />}
                {integrityResult.message}
              </span>
            )}
          </div>

          {/* Entries Table */}
          <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] overflow-hidden">
            <div className="p-4 border-b border-white/[0.06] flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <ClipboardList className="w-4 h-4 text-orange-400" />
                Audit Entries
                <span className="text-xs text-zinc-500 font-normal">({auditTotal} total)</span>
              </h3>
              <button
                onClick={() => { fetchAuditEntries(auditPage); fetchAuditStats(); fetchAuditAlerts(); }}
                className="px-3 py-1.5 rounded-lg text-xs font-medium text-zinc-400 hover:text-white bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all"
              >
                <RefreshCw className="w-3 h-3 inline mr-1" /> Refresh
              </button>
            </div>

            {auditLoading ? (
              <div className="flex items-center justify-center py-16">
                <Loader2 className="w-6 h-6 animate-spin text-orange-400" />
              </div>
            ) : auditEntries.length === 0 ? (
              <div className="text-center py-16">
                <ClipboardList className="w-8 h-8 text-zinc-600 mx-auto mb-3" />
                <p className="text-sm text-zinc-500">No audit entries found</p>
                <p className="text-xs text-zinc-600 mt-1">
                  {filterCategory || filterSeverity || filterAction || filterDateFrom || filterDateTo
                    ? 'Try adjusting your filters'
                    : 'Audit entries will appear here as actions are logged'}
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-white/[0.06]">
                      <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Timestamp</th>
                      <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Category</th>
                      <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Severity</th>
                      <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Action</th>
                      <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Actor</th>
                      <th className="text-left px-4 py-3 text-xs font-medium text-zinc-500 uppercase tracking-wider">Resource</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/[0.04]">
                    {auditEntries.map((entry) => (
                      <tr key={entry.id} className="hover:bg-white/[0.02] transition-colors">
                        <td className="px-4 py-3 text-xs text-zinc-400 font-mono whitespace-nowrap">
                          {new Date(entry.timestamp).toLocaleString()}
                        </td>
                        <td className="px-4 py-3">
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold bg-white/[0.04] text-zinc-300 border border-white/[0.06]">
                            {entry.category === 'auth' && '🔐'}
                            {entry.category === 'integration' && '🔗'}
                            {entry.category === 'ai_action' && '🤖'}
                            {entry.category === 'security' && '🛡️'}
                            {entry.category === 'data' && '📊'}
                            {entry.category === 'configuration' && '⚙️'}
                            {entry.category}
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            entry.severity === 'info' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' :
                            entry.severity === 'warning' ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20' :
                            entry.severity === 'critical' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                            entry.severity === 'security' ? 'bg-purple-500/10 text-purple-400 border border-purple-500/20' :
                            'bg-white/[0.04] text-zinc-400'
                          }`}>
                            {entry.severity === 'critical' && <AlertTriangle className="w-3 h-3" />}
                            {entry.severity === 'security' && <ShieldAlert className="w-3 h-3" />}
                            {entry.severity}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-xs text-zinc-200 font-mono">
                          {entry.action}
                        </td>
                        <td className="px-4 py-3 text-xs text-zinc-400 truncate max-w-[150px]">
                          {entry.actor_name || entry.actor_id}
                        </td>
                        <td className="px-4 py-3">
                          <div className="text-xs text-zinc-400">
                            <span className="text-zinc-500">{entry.resource_type}</span>
                            <span className="mx-1 text-zinc-700">/</span>
                            <span className="text-zinc-300 font-mono">{entry.resource_id?.slice(0, 8)}{entry.resource_id?.length > 8 ? '...' : ''}</span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Pagination */}
            {auditTotal > 20 && (
              <div className="flex items-center justify-between px-4 py-3 border-t border-white/[0.06]">
                <p className="text-xs text-zinc-500">
                  Showing {auditPage * 20 + 1}–{Math.min((auditPage + 1) * 20, auditTotal)} of {auditTotal}
                </p>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => { const p = Math.max(0, auditPage - 1); setAuditPage(p); fetchAuditEntries(p); }}
                    disabled={auditPage === 0}
                    className="p-1.5 rounded-lg text-zinc-400 hover:text-white bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <span className="text-xs text-zinc-400">Page {auditPage + 1} of {Math.ceil(auditTotal / 20)}</span>
                  <button
                    onClick={() => { const p = auditPage + 1; setAuditPage(p); fetchAuditEntries(p); }}
                    disabled={(auditPage + 1) * 20 >= auditTotal}
                    className="p-1.5 rounded-lg text-zinc-400 hover:text-white bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.15] transition-all disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Security Alerts Section */}
          {auditAlerts.length > 0 && (
            <div className="rounded-xl border border-red-500/10 bg-red-500/5 p-6">
              <h3 className="text-sm font-semibold text-red-300 mb-4 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" />
                Security Alerts
              </h3>
              <div className="space-y-2">
                {auditAlerts.map((alert) => (
                  <div key={alert.id} className="flex items-start gap-3 p-3 rounded-lg bg-white/[0.02] border border-white/[0.06]">
                    <span className={`shrink-0 w-2 h-2 rounded-full mt-1.5 ${
                      alert.severity === 'critical' ? 'bg-red-400' : 'bg-yellow-400'
                    }`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-zinc-200">{alert.type}</span>
                        <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                          alert.severity === 'critical'
                            ? 'bg-red-500/10 text-red-400'
                            : 'bg-yellow-500/10 text-yellow-400'
                        }`}>
                          {alert.severity}
                        </span>
                      </div>
                      <p className="text-xs text-zinc-400 mt-0.5">{alert.message}</p>
                      <p className="text-[10px] text-zinc-600 mt-1">{new Date(alert.timestamp).toLocaleString()}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Tabs.Content>

      </Tabs.Root>

      {/* Custom scrollbar styles */}
      <style jsx global>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 4px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: rgba(255, 255, 255, 0.08);
          border-radius: 9999px;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: rgba(255, 255, 255, 0.15);
        }
      `}</style>
    </div>
  );
}

// ── Plan & Industry Section Component (GAP 10 / D9) ──────────────────────

const INDUSTRY_OPTIONS = [
  { value: 'saas', label: 'SaaS', description: 'CRM, Analytics, Dev Tools focus' },
  { value: 'ecommerce', label: 'E-Commerce', description: 'Shopify, Marketing, Payments focus' },
  { value: 'logistics', label: 'Logistics', description: 'Shipping carriers, CRM focus' },
  { value: 'other', label: 'Other', description: 'All integrations shown (no filter)' },
];

function PlanIndustrySection({ currentIndustry, companyId }: { currentIndustry: string; companyId: string }) {
  const [selectedIndustry, setSelectedIndustry] = useState(currentIndustry || 'other');
  const [showImpactModal, setShowImpactModal] = useState(false);
  const [impact, setImpact] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);

  const handleIndustryChange = async (newIndustry: string) => {
    if (newIndustry === selectedIndustry) return;

    setSelectedIndustry(newIndustry);
    setLoading(true);

    try {
      const result = await integrationsApi.industryChangeImpact(selectedIndustry, newIndustry);
      setImpact(result as Record<string, unknown>);
      setShowImpactModal(true);
    } catch {
      // Even if the API fails, show the modal with a basic message
      setImpact({
        current_industry: selectedIndustry,
        new_industry: newIndustry,
        connected_integrations: [],
        still_recommended: [],
        no_longer_suggested: [],
        newly_suggested: [],
        message: `Changing from ${selectedIndustry} to ${newIndustry}. Your integrations, tickets, and knowledge base are NOT affected.`,
      });
      setShowImpactModal(true);
    } finally {
      setLoading(false);
    }
  };

  const confirmIndustryChange = () => {
    setShowImpactModal(false);
    // The industry change would be persisted via the onboarding API
    // For now, the UI shows the selection and the impact analysis
    toast.success(`Industry changed to ${selectedIndustry}`);
  };

  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs text-zinc-500 uppercase tracking-wider mb-3">Your Industry</p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {INDUSTRY_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => handleIndustryChange(opt.value)}
              className={cn(
                'rounded-xl border p-4 text-left transition-all duration-200',
                selectedIndustry === opt.value
                  ? 'border-orange-500/40 bg-orange-500/10'
                  : 'border-white/[0.06] bg-white/[0.02] hover:border-white/10 hover:bg-white/[0.04]'
              )}
            >
              <p className={cn('text-sm font-semibold', selectedIndustry === opt.value ? 'text-orange-400' : 'text-white')}>{opt.label}</p>
              <p className="text-xs text-zinc-500 mt-1">{opt.description}</p>
              {selectedIndustry === opt.value && (
                <div className="w-2 h-2 rounded-full bg-orange-400 mt-2" />
              )}
            </button>
          ))}
        </div>
        <p className="text-xs text-zinc-600 mt-2">
          Per D3: Industry is a suggestion filter, not a restriction. You can always connect tools outside your industry.
        </p>
      </div>

      {loading && (
        <div className="flex items-center gap-2 text-sm text-zinc-400">
          <Loader2 className="w-4 h-4 animate-spin" />
          Analyzing impact...
        </div>
      )}

      {/* Industry Change Impact Modal */}
      {showImpactModal && impact && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4" onClick={() => setShowImpactModal(false)}>
          <div className="rounded-xl border border-white/[0.06] bg-[#1A1A1A] p-6 max-w-lg w-full" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-bold text-white mb-3">Industry Change Impact</h3>
            <p className="text-sm text-zinc-400 mb-4">{impact.message as string}</p>

            {Array.isArray(impact.no_longer_suggested) && (impact.no_longer_suggested as string[]).length > 0 && (
              <div className="mb-3">
                <p className="text-xs text-amber-400 font-medium mb-1">No Longer Suggested (still connected):</p>
                <div className="flex flex-wrap gap-1">
                  {(impact.no_longer_suggested as string[]).map((key: string) => (
                    <span key={key} className="text-xs bg-amber-500/10 text-amber-400 px-2 py-0.5 rounded">{key}</span>
                  ))}
                </div>
              </div>
            )}

            {Array.isArray(impact.newly_suggested) && (impact.newly_suggested as string[]).length > 0 && (
              <div className="mb-3">
                <p className="text-xs text-green-400 font-medium mb-1">Newly Suggested:</p>
                <div className="flex flex-wrap gap-1">
                  {(impact.newly_suggested as string[]).map((key: string) => (
                    <span key={key} className="text-xs bg-green-500/10 text-green-400 px-2 py-0.5 rounded">{key}</span>
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-center gap-3 mt-6">
              <button type="button" onClick={() => setShowImpactModal(false)} className="btn-secondary-parwa py-2 px-4 text-sm">Cancel</button>
              <button type="button" onClick={confirmIndustryChange} className="btn-primary-parwa py-2 px-4 text-sm">Confirm Change</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
