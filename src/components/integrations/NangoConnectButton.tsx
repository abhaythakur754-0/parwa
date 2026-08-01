'use client';

import React, { useState, useEffect } from 'react';
import { Loader2, CheckCircle2, Link2, ExternalLink } from 'lucide-react';

// ── Nango configuration ──
const NANGO_PUBLIC_KEY = '4d84e009-5b78-4ee1-b7b0-12f0396f9db8';
const NANGO_HOST = 'https://api.nango.dev';

// ── Integration definitions (OAuth-based) ──
export const NANGO_INTEGRATIONS = [
  {
    providerConfigKey: 'google-mail',
    name: 'Gmail',
    description: 'Sync email conversations and auto-respond via AI.',
    icon: '📧',
  },
  {
    providerConfigKey: 'google-analytics',
    name: 'Google Analytics',
    description: 'Access website traffic, user behavior, and conversion data.',
    icon: '📊',
  },
  {
    providerConfigKey: 'hubspot',
    name: 'HubSpot (OAuth)',
    description: 'Look up customers, deals, and contact info via OAuth.',
    icon: '🎯',
  },
  {
    providerConfigKey: 'slack',
    name: 'Slack (OAuth)',
    description: 'Send notifications and sync conversations from Slack.',
    icon: '💬',
  },
  {
    providerConfigKey: 'github',
    name: 'GitHub (OAuth)',
    description: 'Access repos, issues, and pull requests via OAuth.',
    icon: '🔧',
  },
  {
    providerConfigKey: 'notion',
    name: 'Notion (OAuth)',
    description: 'Access pages, databases, and docs from Notion.',
    icon: '📝',
  },
];

// ── Hook: Check connection status via Nango backend API ──
export function useNangoConnections(userId: string | undefined) {
  const [connections, setConnections] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!userId) {
      setLoading(false);
      return;
    }

    async function checkConnections() {
      setLoading(true);
      const results: Record<string, boolean> = {};

      for (const integration of NANGO_INTEGRATIONS) {
        try {
          // Check connection via Nango backend API
          const resp = await fetch(
            `${NANGO_HOST}/connection/${integration.providerConfigKey}?connectionId=parwa-${userId}`,
            {
              headers: { 'Authorization': `Bearer ${NANGO_PUBLIC_KEY}` },
            }
          );
          results[integration.providerConfigKey] = resp.ok;
        } catch {
          results[integration.providerConfigKey] = false;
        }
      }

      setConnections(results);
      setLoading(false);
    }

    checkConnections();
  }, [userId]);

  return { connections, loading };
}

// ── NangoConnectButton Component ──
// Uses redirect-based OAuth (more reliable than popup)
export function NangoConnectButton({
  providerConfigKey,
  connectionId,
  connected,
  onConnected,
  onDisconnected,
}: {
  providerConfigKey: string;
  connectionId: string;
  connected: boolean;
  onConnected?: () => void;
  onDisconnected?: () => void;
}) {
  const [loading, setLoading] = useState(false);

  const handleConnect = () => {
    // Use redirect-based OAuth instead of popup
    // This opens the Nango auth URL in the same tab
    const authUrl = `${NANGO_HOST}/oauth/connect?providerConfigKey=${providerConfigKey}&connectionId=parwa-${connectionId}&publicKey=${NANGO_PUBLIC_KEY}&redirectUri=${encodeURIComponent(window.location.href)}`;
    window.location.href = authUrl;
  };

  const handleDisconnect = async () => {
    setLoading(true);
    try {
      await fetch(
        `${NANGO_HOST}/connection/${providerConfigKey}?connectionId=parwa-${connectionId}`,
        {
          method: 'DELETE',
          headers: { 'Authorization': `Bearer ${NANGO_PUBLIC_KEY}` },
        }
      );
      setLoading(false);
      onDisconnected?.();
    } catch {
      setLoading(false);
    }
  };

  if (connected) {
    return (
      <button
        onClick={handleDisconnect}
        disabled={loading}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/20 transition-all"
      >
        {loading ? (
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
        ) : (
          <CheckCircle2 className="w-3.5 h-3.5" />
        )}
        {loading ? 'Disconnecting...' : 'Connected — Click to disconnect'}
      </button>
    );
  }

  return (
    <button
      onClick={handleConnect}
      disabled={loading}
      className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-violet-500/15 text-violet-300 border border-violet-500/30 hover:bg-violet-500/25 hover:border-violet-500/40 transition-all"
    >
      {loading ? (
        <Loader2 className="w-3.5 h-3.5 animate-spin" />
      ) : (
        <Link2 className="w-3.5 h-3.5" />
      )}
      {loading ? 'Connecting...' : 'Connect with OAuth'}
    </button>
  );
}

// ── Nango Integrations Section ──
export function NangoIntegrationsSection({ userId }: { userId: string | undefined }) {
  const { connections, loading } = useNangoConnections(userId);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-5 h-5 animate-spin text-violet-400" />
        <span className="ml-2 text-sm text-zinc-500">Loading OAuth integrations...</span>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Nango badge */}
      <div className="flex items-center gap-2 mb-3">
        <div className="px-2 py-1 rounded-md bg-violet-500/10 border border-violet-500/20 text-violet-300 text-[10px] font-bold uppercase tracking-wider">
          ⚡ Powered by Nango
        </div>
        <span className="text-xs text-zinc-500">OAuth-based integrations — click to connect securely</span>
      </div>

      {/* Integration cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {NANGO_INTEGRATIONS.map((integration) => {
          const isConnected = connections[integration.providerConfigKey] || false;
          return (
            <div
              key={integration.providerConfigKey}
              className={`rounded-xl border p-4 flex items-center justify-between transition-all duration-200 ${
                isConnected
                  ? 'border-emerald-500/20 bg-emerald-500/[0.02]'
                  : 'border-white/[0.06] bg-white/[0.02] hover:border-violet-500/20 hover:bg-violet-500/[0.02]'
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="text-2xl">{integration.icon}</span>
                <div>
                  <p className="text-sm font-medium text-white">{integration.name}</p>
                  <p className="text-[10px] text-zinc-500">{integration.description}</p>
                </div>
              </div>
              <NangoConnectButton
                providerConfigKey={integration.providerConfigKey}
                connectionId={userId || 'default'}
                connected={isConnected}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}
