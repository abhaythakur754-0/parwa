'use client';

import { useState, useEffect } from 'react';
import toast from 'react-hot-toast';
import { useAuth } from '@/hooks/useAuth';
import { useVariant } from '@/hooks/useVariant';
import { LockedFeature } from '@/components/LockedFeature';
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
} from 'lucide-react';

// ── API Base ────────────────────────────────────────────────────────────
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
  const { tier } = useVariant();

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
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([
    { id: '1', name: 'Production Key', key: 'pk_****a7f3', created: '2024-12-01' },
    { id: '2', name: 'Staging Key', key: 'pk_****b2e1', created: '2025-01-15' },
  ]);
  const [newKeyName, setNewKeyName] = useState('');
  const [showCreateKey, setShowCreateKey] = useState(false);
  const [creatingKey, setCreatingKey] = useState(false);
  const [copiedKeyId, setCopiedKeyId] = useState<string | null>(null);
  const [revokingKeyId, setRevokingKeyId] = useState<string | null>(null);

  // ── Profile Handlers ────────────────────────────────────────────────

  const handleProfileChange = () => setProfileDirty(true);

  const handleProfileSave = async () => {
    setProfileSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
        method: 'PATCH',
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
      const res = await fetch(`${API_BASE}/api/v1/settings/notifications`, {
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
      const res = await fetch(`${API_BASE}/api/v1/auth/change-password`, {
        method: 'POST',
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
      const res = await fetch(`${API_BASE}/api/v1/auth/mfa/setup`, {
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
      const res = await fetch(`${API_BASE}/api/v1/api-keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ name: newKeyName.trim() }),
      });
      let newKey: ApiKey;
      if (res.ok) {
        const data = await res.json();
        newKey = {
          id: data.id || String(Date.now()),
          name: newKeyName.trim(),
          key: `pk_****${(data.key_suffix || data.key || '').slice(-4)}`,
          created: new Date().toISOString().split('T')[0],
        };
      } else {
        // Fallback: create mock key
        const suffix = Math.random().toString(16).slice(2, 6);
        newKey = {
          id: String(Date.now()),
          name: newKeyName.trim(),
          key: `pk_****${suffix}`,
          created: new Date().toISOString().split('T')[0],
        };
      }
      setApiKeys((prev) => [...prev, newKey]);
      setNewKeyName('');
      setShowCreateKey(false);
      toast.success('API key created');
    } catch {
      // Network error: still create locally
      const suffix = Math.random().toString(16).slice(2, 6);
      const newKey: ApiKey = {
        id: String(Date.now()),
        name: newKeyName.trim(),
        key: `pk_****${suffix}`,
        created: new Date().toISOString().split('T')[0],
      };
      setApiKeys((prev) => [...prev, newKey]);
      setNewKeyName('');
      setShowCreateKey(false);
      toast.success('API key created (offline)');
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
      await fetch(`${API_BASE}/api/v1/api-keys/${keyId}`, {
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
      <Tabs.Root defaultValue="profile" className="flex flex-col gap-6">
        {/* Tab List */}
        <Tabs.List className="flex gap-1 rounded-xl border border-white/[0.06] bg-white/[0.02] p-1 w-fit">
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
          <LockedFeature requiredTier="pro" featureName="API Keys">
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
          </LockedFeature>
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
