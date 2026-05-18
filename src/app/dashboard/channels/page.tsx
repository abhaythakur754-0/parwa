'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';
import { getErrorMessage } from '@/lib/api';
import { voiceApi } from '@/lib/voice-api';
import { Phone, Settings, Loader2 } from 'lucide-react';
import type { ChannelInfo, ChannelConfig, ChannelType } from '@/types/analytics';
import type { VoiceChannelConfig } from '@/types/voice';

// ── Channel Metadata ──────────────────────────────────────────────────

interface ChannelMeta {
  type: ChannelType;
  name: string;
  description: string;
  emoji: string;
}

const channelMeta: ChannelMeta[] = [
  { type: 'email', name: 'Email', description: 'Inbound/outbound email support via Brevo', emoji: '\u2709\uFE0F' },
  { type: 'chat', name: 'Live Chat', description: 'Real-time chat widget on your website', emoji: '\uD83D\uDCAC' },
  { type: 'sms', name: 'SMS', description: 'Text messaging via Twilio', emoji: '\uD83D\uDCF1' },
  { type: 'voice', name: 'Voice', description: 'AI-powered voice calls via Twilio', emoji: '\uD83C\uDF99\uFE0F' },
];

// ── Channel Card Component ────────────────────────────────────────────

function ChannelCard({
  channel,
  isEnabled,
  isLoading,
  onToggle,
  onTest,
  extra,
}: {
  channel: ChannelMeta;
  isEnabled: boolean;
  isLoading: boolean;
  onToggle: (type: ChannelType, enabled: boolean) => void;
  onTest: (type: ChannelType) => void;
  extra?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        'rounded-xl border p-5 transition-all duration-300 group',
        isEnabled
          ? 'bg-[#1A1A1A] border-emerald-500/20 shadow-sm shadow-emerald-500/5'
          : 'bg-[#1A1A1A] border-white/[0.06] hover:border-white/[0.1]'
      )}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{channel.emoji}</span>
          <div>
            <h3 className="text-sm font-semibold text-white">{channel.name}</h3>
            <p className="text-xs text-zinc-500 mt-0.5 max-w-[240px]">{channel.description}</p>
          </div>
        </div>
        {/* Toggle */}
        <button
          onClick={() => onToggle(channel.type, !isEnabled)}
          disabled={isLoading}
          className={cn(
            'relative w-11 h-6 rounded-full transition-colors duration-300 shrink-0',
            isEnabled ? 'bg-emerald-500' : 'bg-white/[0.1]'
          )}
        >
          <span
            className={cn(
              'absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-300',
              isEnabled ? 'translate-x-5' : 'translate-x-0'
            )}
          />
        </button>
      </div>

      {/* Status + Test */}
      <div className="flex items-center justify-between pt-3 border-t border-white/[0.04]">
        <div className="flex items-center gap-1.5">
          <span className={cn(
            'w-2 h-2 rounded-full',
            isEnabled ? 'bg-emerald-400 pulse-live' : 'bg-zinc-600'
          )} />
          <span className={cn(
            'text-xs font-medium',
            isEnabled ? 'text-emerald-400' : 'text-zinc-500'
          )}>
            {isEnabled ? 'Active' : 'Disabled'}
          </span>
        </div>
        {isEnabled && (
          <button
            onClick={() => onTest(channel.type)}
            disabled={isLoading}
            className="text-xs font-medium text-orange-400 hover:text-orange-300 transition-colors disabled:opacity-50"
          >
            Test Connection
          </button>
        )}
      </div>

      {/* Extra content (Voice-specific) */}
      {extra}
    </div>
  );
}

// ── Channels Page ─────────────────────────────────────────────────────

export default function ChannelsPage() {
  const [enabledChannels, setEnabledChannels] = useState<Set<ChannelType>>(new Set());
  const [isLoading, setIsLoading] = useState(false);
  const [voiceConfig, setVoiceConfig] = useState<VoiceChannelConfig | null>(null);
  const [recentCallCount, setRecentCallCount] = useState(0);
  const [testCallLoading, setTestCallLoading] = useState(false);

  // ── Load channel config ────────────────────────────────────────────

  useEffect(() => {
    loadChannelConfig();
    loadVoiceData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadChannelConfig() {
    try {
      setIsLoading(true);
      const response = await fetch('/api/v1/channels/config', {
        credentials: 'include',
      });
      if (response.ok) {
        const data = await response.json();
        const enabled = new Set<ChannelType>();
        if (Array.isArray(data)) {
          data.forEach((ch: { channel_type: string; is_enabled: boolean }) => {
            if (ch.is_enabled) enabled.add(ch.channel_type as ChannelType);
          });
        }
        setEnabledChannels(enabled);
      }
    } catch (error) {
      console.error('Failed to load channels:', error);
    } finally {
      setIsLoading(false);
    }
  }

  async function loadVoiceData() {
    try {
      const config = await voiceApi.getConfig();
      setVoiceConfig(config);

      // Get recent calls count
      const history = await voiceApi.getHistory({ page: 1, page_size: 1 });
      setRecentCallCount(history.total);

      // If voice is enabled in config, add to enabled set
      if (config.is_enabled) {
        setEnabledChannels((prev) => new Set(prev).add('voice'));
      }
    } catch {
      // Voice config may not exist yet
    }
  }

  // ── Toggle Channel ─────────────────────────────────────────────────

  const handleToggle = useCallback(async (type: ChannelType, enabled: boolean) => {
    try {
      const response = await fetch(`/api/v1/channels/config/${type}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ is_enabled: enabled }),
      });

      if (response.ok) {
        setEnabledChannels((prev) => {
          const next = new Set(prev);
          if (enabled) next.add(type);
          else next.delete(type);
          return next;
        });
        toast.success(`${channelMeta.find((c) => c.type === type)?.name} ${enabled ? 'enabled' : 'disabled'}`);
      } else {
        const error = await response.json().catch(() => ({}));
        toast.error(error.detail || 'Failed to update channel');
      }
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }, []);

  // ── Test Connection ────────────────────────────────────────────────

  const handleTest = useCallback(async (type: ChannelType) => {
    try {
      toast.loading(`Testing ${channelMeta.find((c) => c.type === type)?.name}...`, { id: 'test-channel' });
      const response = await fetch(`/api/v1/channels/config/${type}/test`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
      });

      if (response.ok) {
        toast.success(`${channelMeta.find((c) => c.type === type)?.name} connection successful`, { id: 'test-channel' });
      } else {
        toast.error('Connection failed', { id: 'test-channel' });
      }
    } catch (error) {
      toast.error(getErrorMessage(error), { id: 'test-channel' });
    }
  }, []);

  // ── Test Voice Call ────────────────────────────────────────────────

  const handleTestCall = useCallback(async () => {
    setTestCallLoading(true);
    try {
      const result = await voiceApi.testCall({ to_number: '+919652852014' });
      toast.success(`Test call initiated! SID: ${result.twilio_call_sid?.slice(0, 10)}...`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to make test call');
    } finally {
      setTestCallLoading(false);
    }
  }, []);

  // ── Render ─────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen jarvis-page-body">
      <div className="p-6 lg:p-8 space-y-6">
        {/* Header */}
        <div className="pb-6 border-b border-white/[0.06]">
          <h1 className="text-xl font-bold text-white">Channels</h1>
          <p className="text-sm text-zinc-500 mt-0.5">
            PARWA supports Email, Chat, SMS, and Voice channels.
          </p>
        </div>

        {/* Channel Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {channelMeta.map((channel) => (
            <ChannelCard
              key={channel.type}
              channel={channel}
              isEnabled={enabledChannels.has(channel.type)}
              isLoading={isLoading}
              onToggle={handleToggle}
              onTest={handleTest}
              extra={
                channel.type === 'voice' ? (
                  <VoiceChannelExtra
                    config={voiceConfig}
                    recentCallCount={recentCallCount}
                    testCallLoading={testCallLoading}
                    onTestCall={handleTestCall}
                  />
                ) : undefined
              }
            />
          ))}
        </div>

        {/* Info */}
        <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-5">
          <div className="flex items-start gap-3">
            <span className="text-lg">{'\uD83D\uDD39'}</span>
            <div>
              <h4 className="text-sm font-semibold text-zinc-300">Need a custom integration?</h4>
              <p className="text-xs text-zinc-500 mt-1">
                PARWA supports custom REST, GraphQL, and webhook integrations. 
                Contact support or use the API to build your own connector.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Voice Channel Extra Section ───────────────────────────────────────

function VoiceChannelExtra({
  config,
  recentCallCount,
  testCallLoading,
  onTestCall,
}: {
  config: VoiceChannelConfig | null;
  recentCallCount: number;
  testCallLoading: boolean;
  onTestCall: () => void;
}) {
  return (
    <div className="mt-3 pt-3 border-t border-white/[0.04] space-y-2.5">
      {/* Voice Config Status */}
      {config && (
        <div className="flex items-center gap-2 text-[10px] text-zinc-600">
          <Phone className="w-3 h-3" />
          <span>Number: {config.twilio_phone_number}</span>
        </div>
      )}

      {/* Recent Calls */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] text-zinc-600">
          {recentCallCount} total call{recentCallCount !== 1 ? 's' : ''} recorded
        </span>
        <div className="flex items-center gap-2">
          {/* Configure Link */}
          <Link
            href="/dashboard/calls"
            className="inline-flex items-center gap-1 text-[10px] font-medium text-orange-400 hover:text-orange-300 transition-colors"
          >
            <Settings className="w-3 h-3" />
            Configure
          </Link>

          {/* Test Call */}
          <button
            onClick={onTestCall}
            disabled={testCallLoading}
            className="inline-flex items-center gap-1 text-[10px] font-medium text-emerald-400 hover:text-emerald-300 transition-colors disabled:opacity-50"
          >
            {testCallLoading ? (
              <Loader2 className="w-3 h-3 animate-spin" />
            ) : (
              <Phone className="w-3 h-3" />
            )}
            Test Call
          </button>
        </div>
      </div>
    </div>
  );
}
