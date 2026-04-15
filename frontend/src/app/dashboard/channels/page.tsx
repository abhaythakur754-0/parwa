'use client';

import React, { useState, useEffect, useCallback } from 'react';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';
import { getErrorMessage } from '@/lib/api';
import { getChannelConfig, updateChannelConfig, testChannelConnection } from '@/lib/channels-api';
import type { ChannelType } from '@/types/analytics';

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
  { type: 'whatsapp', name: 'WhatsApp', description: 'WhatsApp Business API integration', emoji: '\uD83D\uDCAC' },
  { type: 'messenger', name: 'Messenger', description: 'Facebook Messenger integration', emoji: '\uD83D\uDCAC' },
  { type: 'twitter', name: 'X (Twitter)', description: 'Twitter/X DMs and mentions', emoji: '\uD83D\uDC26' },
  { type: 'instagram', name: 'Instagram', description: 'Instagram DMs integration', emoji: '\uD83D\uDCF8' },
  { type: 'telegram', name: 'Telegram', description: 'Telegram bot integration', emoji: '\u2708\uFE0F' },
  { type: 'slack', name: 'Slack', description: 'Slack workspace integration', emoji: '\uD83D\uDCA1' },
  { type: 'webchat', name: 'Webchat', description: 'Embeddable web chat widget', emoji: '\uD83C\uDF10' },
];

// ── Channel Card Component ────────────────────────────────────────────

function ChannelCard({
  channel,
  isEnabled,
  isLoading,
  onToggle,
  onTest,
}: {
  channel: ChannelMeta;
  isEnabled: boolean;
  isLoading: boolean;
  onToggle: (type: ChannelType, enabled: boolean) => void;
  onTest: (type: ChannelType) => void;
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
    </div>
  );
}

// ── Channels Page ─────────────────────────────────────────────────────

export default function ChannelsPage() {
  const [enabledChannels, setEnabledChannels] = useState<Set<ChannelType>>(new Set());
  const [isLoading, setIsLoading] = useState(false);

  // ── Load channel config ────────────────────────────────────────────

  useEffect(() => {
    loadChannelConfig();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function loadChannelConfig() {
    try {
      setIsLoading(true);
      const configs = await getChannelConfig();
      const enabled = new Set<ChannelType>();
      configs.forEach((ch) => {
        if (ch.is_enabled) enabled.add(ch.channel_type as ChannelType);
      });
      setEnabledChannels(enabled);
    } catch (error) {
      console.error('Failed to load channels:', error);
      toast.error(getErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }

  // ── Toggle Channel ─────────────────────────────────────────────────

  const handleToggle = useCallback(async (type: ChannelType, enabled: boolean) => {
    try {
      await updateChannelConfig(type, { is_enabled: enabled });
      setEnabledChannels((prev) => {
        const next = new Set(prev);
        if (enabled) next.add(type);
        else next.delete(type);
        return next;
      });
      toast.success(`${channelMeta.find((c) => c.type === type)?.name} ${enabled ? 'enabled' : 'disabled'}`);
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  }, []);

  // ── Test Connection ────────────────────────────────────────────────

  const handleTest = useCallback(async (type: ChannelType) => {
    try {
      toast.loading(`Testing ${channelMeta.find((c) => c.type === type)?.name}...`, { id: 'test-channel' });
      const result = await testChannelConnection(type);

      if (result.success) {
        toast.success(`${channelMeta.find((c) => c.type === type)?.name} connection successful`, { id: 'test-channel' });
      } else {
        toast.error(result.message || 'Connection failed', { id: 'test-channel' });
      }
    } catch (error) {
      toast.error(getErrorMessage(error), { id: 'test-channel' });
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
            Manage your communication channels. Enable and configure how customers reach you.
          </p>
        </div>

        {/* Channel Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
          {channelMeta.map((channel) => (
            <ChannelCard
              key={channel.type}
              channel={channel}
              isEnabled={enabledChannels.has(channel.type)}
              isLoading={isLoading}
              onToggle={handleToggle}
              onTest={handleTest}
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
