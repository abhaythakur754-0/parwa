'use client';

import React, { useState, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';
import type { ChannelType } from '@/types/analytics';

interface ChannelMeta {
  type: ChannelType;
  name: string;
  description: string;
  emoji: string;
  provider: string;
}

interface ChannelStatus {
  email: {
    configured: boolean;
    provider: string | null;
    fromEmail: string | null;
    apiKeyPreview: string | null;
  };
  sms: {
    configured: boolean;
    provider: string | null;
    phoneNumber: string | null;
    accountSidPreview: string | null;
  };
}

const channelMeta: ChannelMeta[] = [
  { type: 'email', name: 'Email', description: 'Customer notifications via Brevo SMTP', emoji: '📧', provider: 'Brevo' },
  { type: 'chat', name: 'Live Chat', description: 'Real-time chat widget on your website', emoji: '💬', provider: 'Built-in' },
  { type: 'sms', name: 'SMS', description: 'Text notifications via Twilio', emoji: '📱', provider: 'Twilio' },
  { type: 'voice', name: 'Voice', description: 'AI-powered voice calls', emoji: '🎧', provider: 'Twilio' },
];

export default function ChannelsPage() {
  const [status, setStatus] = useState<ChannelStatus | null>(null);
  const [enabledChannels, setEnabledChannels] = useState<Set<ChannelType>>(new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [testLoading, setTestLoading] = useState<string | null>(null);
  const [testEmail, setTestEmail] = useState('');
  const [testPhone, setTestPhone] = useState('');

  // Fetch real channel status on mount
  useEffect(() => {
    fetchChannelStatus();
  }, []);

  const fetchChannelStatus = async () => {
    try {
      const res = await fetch('/api/channel-status');
      if (res.ok) {
        const data: ChannelStatus = await res.json();
        setStatus(data);
        // Auto-enable channels that are configured
        const enabled = new Set<ChannelType>();
        if (data.email.configured) enabled.add('email');
        if (data.sms.configured) enabled.add('sms');
        enabled.add('chat'); // Chat is always built-in
        setEnabledChannels(enabled);
      }
    } catch {
      console.error('Failed to fetch channel status');
    }
  };

  const handleToggle = useCallback(async (type: ChannelType, enabled: boolean) => {
    setIsLoading(true);
    // Simulate brief delay for UX
    await new Promise(r => setTimeout(r, 300));
    setEnabledChannels((prev) => {
      const next = new Set(prev);
      if (enabled) next.add(type);
      else next.delete(type);
      return next;
    });
    toast.success(`${channelMeta.find((c) => c.type === type)?.name} ${enabled ? 'enabled' : 'disabled'}`);
    setIsLoading(false);
  }, []);

  const handleTestEmail = async () => {
    if (!testEmail.trim()) {
      toast.error('Enter an email address to test');
      return;
    }
    setTestLoading('email');
    try {
      const res = await fetch('/api/send-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to: testEmail.trim(),
          subject: 'PARWA Channel Test - Email Integration Working!',
          textContent: 'This is a test email from PARWA AI Workforce Platform. Your email channel is configured and working correctly. Ticket notifications will be sent to this address.',
        }),
      });
      const data = await res.json();
      if (data.success) {
        toast.success('Test email sent successfully!');
      } else {
        toast.error(`Failed: ${data.error || 'Unknown error'}`);
      }
    } catch {
      toast.error('Failed to send test email');
    }
    setTestLoading(null);
  };

  const handleTestSMS = async () => {
    if (!testPhone.trim()) {
      toast.error('Enter a phone number to test');
      return;
    }
    setTestLoading('sms');
    try {
      const res = await fetch('/api/send-sms', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to: testPhone.trim(),
          body: '[PARWA] Test SMS - Your SMS channel is working! Ticket notifications will be sent here.',
        }),
      });
      const data = await res.json();
      if (data.success) {
        toast.success(`Test SMS sent! SID: ${data.sid}`);
      } else {
        toast.error(`Failed: ${data.error || 'Unknown error'}`);
      }
    } catch {
      toast.error('Failed to send test SMS');
    }
    setTestLoading(null);
  };

  const getStatusBadge = (type: ChannelType) => {
    if (!status) return null;

    if (type === 'email') {
      return status.email.configured ? (
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          <span className="text-[11px] text-emerald-400">{status.email.provider}</span>
          {status.email.fromEmail && (
            <span className="text-[10px] text-zinc-600">from: {status.email.fromEmail}</span>
          )}
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-400" />
          <span className="text-[11px] text-red-400">API key not set</span>
        </div>
      );
    }

    if (type === 'sms') {
      return status.sms.configured ? (
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          <span className="text-[11px] text-emerald-400">{status.sms.provider}</span>
          {status.sms.phoneNumber && (
            <span className="text-[10px] text-zinc-600">from: {status.sms.phoneNumber}</span>
          )}
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-red-400" />
          <span className="text-[11px] text-red-400">Not configured</span>
        </div>
      );
    }

    if (type === 'chat') {
      return (
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-emerald-400" />
          <span className="text-[11px] text-emerald-400">Built-in</span>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="pb-6 border-b border-white/[0.06]">
        <h1 className="text-xl font-bold text-white">Channels</h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          Configure and test your customer communication channels. When AI resolves tickets, notifications are sent automatically.
        </p>
      </div>

      {/* Channel Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {channelMeta.map((channel) => (
          <div
            key={channel.type}
            className={cn(
              'rounded-xl border p-5 transition-all duration-300',
              enabledChannels.has(channel.type)
                ? 'bg-[#1A1A1A] border-emerald-500/20 shadow-sm shadow-emerald-500/5'
                : 'bg-[#1A1A1A] border-white/[0.06] hover:border-white/[0.1]'
            )}
          >
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center gap-3">
                <span className="text-2xl">{channel.emoji}</span>
                <div>
                  <h3 className="text-sm font-semibold text-white">{channel.name}</h3>
                  <p className="text-xs text-zinc-500 mt-0.5 max-w-[220px]">{channel.description}</p>
                </div>
              </div>
              <button
                onClick={() => handleToggle(channel.type, !enabledChannels.has(channel.type))}
                disabled={isLoading}
                className={cn(
                  'relative w-11 h-6 rounded-full transition-colors duration-300 shrink-0',
                  enabledChannels.has(channel.type) ? 'bg-emerald-500' : 'bg-white/[0.1]'
                )}
              >
                <span
                  className={cn(
                    'absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-300',
                    enabledChannels.has(channel.type) ? 'translate-x-5' : 'translate-x-0'
                  )}
                />
              </button>
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-white/[0.04]">
              {getStatusBadge(channel.type)}
              <span className={cn(
                'text-[10px] px-2 py-0.5 rounded-full',
                enabledChannels.has(channel.type)
                  ? 'bg-emerald-500/10 text-emerald-400'
                  : 'bg-zinc-500/10 text-zinc-500'
              )}>
                {enabledChannels.has(channel.type) ? 'Active' : 'Off'}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Test Email */}
      <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-5">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-lg">📧</span>
          <div>
            <h4 className="text-sm font-semibold text-white">Test Email Channel</h4>
            <p className="text-xs text-zinc-500 mt-0.5">Send a test email to verify Brevo integration</p>
          </div>
          {status?.email.configured && (
            <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400">Connected</span>
          )}
        </div>
        <div className="flex gap-2">
          <input
            type="email"
            value={testEmail}
            onChange={(e) => setTestEmail(e.target.value)}
            placeholder="customer@example.com"
            className="flex-1 h-9 bg-[#0F0F0F] border border-white/[0.06] rounded-lg px-3 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500/40 transition-colors"
          />
          <button
            onClick={handleTestEmail}
            disabled={testLoading === 'email'}
            className="h-9 px-4 rounded-lg bg-emerald-500 text-sm text-white font-medium hover:bg-emerald-600 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {testLoading === 'email' ? (
              <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              'Send Test'
            )}
          </button>
        </div>
      </div>

      {/* Test SMS */}
      <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-5">
        <div className="flex items-center gap-3 mb-4">
          <span className="text-lg">📱</span>
          <div>
            <h4 className="text-sm font-semibold text-white">Test SMS Channel</h4>
            <p className="text-xs text-zinc-500 mt-0.5">Send a test SMS to verify Twilio integration</p>
          </div>
          {status?.sms.configured && (
            <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400">Connected</span>
          )}
        </div>
        <div className="flex gap-2">
          <input
            type="tel"
            value={testPhone}
            onChange={(e) => setTestPhone(e.target.value)}
            placeholder="+919652852014"
            className="flex-1 h-9 bg-[#0F0F0F] border border-white/[0.06] rounded-lg px-3 text-sm text-white placeholder:text-zinc-600 focus:outline-none focus:border-emerald-500/40 transition-colors"
          />
          <button
            onClick={handleTestSMS}
            disabled={testLoading === 'sms'}
            className="h-9 px-4 rounded-lg bg-emerald-500 text-sm text-white font-medium hover:bg-emerald-600 transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            {testLoading === 'sms' ? (
              <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
            ) : (
              'Send Test'
            )}
          </button>
        </div>
      </div>

      {/* How it works */}
      <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-5">
        <div className="flex items-start gap-3">
          <span className="text-lg">🔒</span>
          <div>
            <h4 className="text-sm font-semibold text-zinc-300">How Notifications Work</h4>
            <p className="text-xs text-zinc-500 mt-1 leading-relaxed">
              When a customer creates a ticket or AI responds, PARWA automatically sends:
            </p>
            <ul className="mt-2 space-y-1">
              <li className="text-xs text-zinc-500 flex items-center gap-2">
                <span className="text-emerald-400">&#10003;</span> <strong className="text-zinc-400">Email tickets</strong> → Email notification to customer
              </li>
              <li className="text-xs text-zinc-500 flex items-center gap-2">
                <span className="text-emerald-400">&#10003;</span> <strong className="text-zinc-400">SMS tickets</strong> → Text message to customer phone
              </li>
              <li className="text-xs text-zinc-500 flex items-center gap-2">
                <span className="text-emerald-400">&#10003;</span> <strong className="text-zinc-400">Chat tickets</strong> → In-app notification only
              </li>
              <li className="text-xs text-zinc-500 flex items-center gap-2">
                <span className="text-emerald-400">&#10003;</span> <strong className="text-zinc-400">Voice tickets</strong> → Email transcript
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
