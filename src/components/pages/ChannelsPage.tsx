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
}

const channelMeta: ChannelMeta[] = [
  { type: 'email', name: 'Email', description: 'Inbound/outbound email support', emoji: '📧' },
  { type: 'chat', name: 'Live Chat', description: 'Real-time chat widget on your website', emoji: '💬' },
  { type: 'sms', name: 'SMS', description: 'Text messaging via Twilio', emoji: '📱' },
  { type: 'voice', name: 'Voice', description: 'AI-powered voice calls', emoji: '🎧' },
];

function ChannelCard({
  channel,
  isEnabled,
  isLoading,
  onToggle,
}: {
  channel: ChannelMeta;
  isEnabled: boolean;
  isLoading: boolean;
  onToggle: (type: ChannelType, enabled: boolean) => void;
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

      <div className="flex items-center justify-between pt-3 border-t border-white/[0.04]">
        <div className="flex items-center gap-1.5">
          <span className={cn(
            'w-2 h-2 rounded-full',
            isEnabled ? 'bg-emerald-400' : 'bg-zinc-600'
          )} />
          <span className={cn(
            'text-xs font-medium',
            isEnabled ? 'text-emerald-400' : 'text-zinc-500'
          )}>
            {isEnabled ? 'Active' : 'Disabled'}
          </span>
        </div>
      </div>
    </div>
  );
}

export default function ChannelsPage() {
  const [enabledChannels, setEnabledChannels] = useState<Set<ChannelType>>(new Set());
  const [isLoading, setIsLoading] = useState(false);

  const handleToggle = useCallback(async (type: ChannelType, enabled: boolean) => {
    setIsLoading(true);
    // Simulate API call
    setTimeout(() => {
      setEnabledChannels((prev) => {
        const next = new Set(prev);
        if (enabled) next.add(type);
        else next.delete(type);
        return next;
      });
      toast.success(`${channelMeta.find((c) => c.type === type)?.name} ${enabled ? 'enabled' : 'disabled'}`);
      setIsLoading(false);
    }, 500);
  }, []);

  return (
    <div className="space-y-6">
      <div className="pb-6 border-b border-white/[0.06]">
        <h1 className="text-xl font-bold text-white">Channels</h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          PARWA supports Email, Chat, SMS, and Voice channels.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {channelMeta.map((channel) => (
          <ChannelCard
            key={channel.type}
            channel={channel}
            isEnabled={enabledChannels.has(channel.type)}
            isLoading={isLoading}
            onToggle={handleToggle}
          />
        ))}
      </div>

      <div className="rounded-xl bg-[#1A1A1A] border border-white/[0.06] p-5">
        <div className="flex items-start gap-3">
          <span className="text-lg">🔹</span>
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
  );
}
