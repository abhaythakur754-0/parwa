'use client';

/**
 * SuperglueIntegrationsSection — replaces the removed NangoConnectButton.
 *
 * Shows a grid of popular systems (Shopify, Gmail, Slack, etc.) that users
 * can connect via Superglue. Each card has a "Connect" button that opens
 * an inline form (name + URL + API key). Connected systems show a green
 * "Connected — Click to disconnect" button.
 *
 * Used in:
 *   - Onboarding Step 2 (IntegrationStep.tsx)
 *   - /dashboard/integrations page
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Loader2, CheckCircle2, Link2, X, Plug } from 'lucide-react';
import toast from 'react-hot-toast';
import { cn } from '@/lib/utils';

// ── Types ────────────────────────────────────────────────────────────

interface CatalogSystem {
  id: string;
  name: string;
  icon: string;
  url_hint: string;
  category: string;
}

interface ConnectedSystem {
  id: string;
  name: string;
  url: string;
  icon: string;
}

// ── Component ────────────────────────────────────────────────────────

export function SuperglueIntegrationsSection() {
  const [catalog, setCatalog] = useState<CatalogSystem[]>([]);
  const [connected, setConnected] = useState<ConnectedSystem[]>([]);
  const [loading, setLoading] = useState(true);
  const [connectingId, setConnectingId] = useState<string | null>(null);
  const [disconnectingId, setDisconnectingId] = useState<string | null>(null);
  // Inline connect form state
  const [formOpen, setFormOpen] = useState(false);
  const [formSystem, setFormSystem] = useState<CatalogSystem | null>(null);
  const [formName, setFormName] = useState('');
  const [formUrl, setFormUrl] = useState('');
  const [formApiKey, setFormApiKey] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // ── Fetch catalog + connected systems ────────────────────────────
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [catalogRes, systemsRes] = await Promise.all([
        fetch('/api/superglue/systems/catalog'),
        fetch('/api/superglue/systems'),
      ]);
      const catalogData = catalogRes.ok ? await catalogRes.json() : { systems: [] };
      const systemsData = systemsRes.ok ? await systemsRes.json() : { systems: [] };
      setCatalog(catalogData.systems || []);
      setConnected(systemsData.systems || []);
    } catch {
      // Silently fail — catalog is static, systems list is best-effort
      setCatalog([]);
      setConnected([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // ── Open connect form for a catalog system ────────────────────────
  const openConnectForm = (sys: CatalogSystem) => {
    setFormSystem(sys);
    setFormName(sys.name === 'Custom System' ? '' : sys.name);
    setFormUrl(sys.url_hint || '');
    setFormApiKey('');
    setFormOpen(true);
  };

  // ── Submit connect ───────────────────────────────────────────────
  const handleConnect = async () => {
    if (!formSystem || !formName.trim() || !formUrl.trim()) {
      toast.error('Name and URL are required');
      return;
    }
    setSubmitting(true);
    setConnectingId(formSystem.id);
    try {
      const res = await fetch('/api/superglue/systems', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          system_id: formSystem.id,
          name: formName.trim(),
          url: formUrl.trim(),
          credentials: formApiKey.trim() ? { api_key: formApiKey.trim() } : {},
          icon: formSystem.icon,
        }),
      });
      const data = await res.json();
      if (res.ok) {
        toast.success(`${formName} connected via Superglue`);
        setFormOpen(false);
        setFormSystem(null);
        await load(); // refresh list
      } else {
        toast.error(data.detail || data.error?.message || 'Failed to connect');
      }
    } catch {
      toast.error('Network error — could not reach Superglue');
    } finally {
      setSubmitting(false);
      setConnectingId(null);
    }
  };

  // ── Disconnect ───────────────────────────────────────────────────
  const handleDisconnect = async (sys: ConnectedSystem) => {
    setDisconnectingId(sys.id);
    try {
      const res = await fetch(`/api/superglue/systems/${encodeURIComponent(sys.id)}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        toast.success(`${sys.name} disconnected`);
        await load();
      } else {
        const data = await res.json().catch(() => ({}));
        toast.error(data.detail || 'Failed to disconnect');
      }
    } catch {
      toast.error('Network error');
    } finally {
      setDisconnectingId(null);
    }
  };

  // ── Render ───────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-5 h-5 animate-spin text-violet-400" />
        <span className="ml-2 text-sm text-zinc-500">Loading integrations...</span>
      </div>
    );
  }

  const connectedIds = new Set(connected.map((s) => s.id));

  return (
    <div className="space-y-3">
      {/* Superglue badge */}
      <div className="flex items-center gap-2 mb-3">
        <div className="px-2 py-1 rounded-md bg-violet-500/10 border border-violet-500/20 text-violet-300 text-[10px] font-bold uppercase tracking-wider">
          ⚡ Powered by Superglue
        </div>
        <span className="text-xs text-zinc-500">Connect your apps — Superglue handles auth, retries &amp; execution</span>
      </div>

      {/* Integration cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {catalog.map((sys) => {
          const isConnected = connectedIds.has(sys.id);
          const connectedSys = connected.find((s) => s.id === sys.id);
          return (
            <div
              key={sys.id}
              className={cn(
                'rounded-xl border p-4 flex items-center justify-between transition-all duration-200',
                isConnected
                  ? 'border-emerald-500/20 bg-emerald-500/[0.02]'
                  : 'border-white/[0.06] bg-white/[0.02] hover:border-violet-500/20 hover:bg-violet-500/[0.02]',
              )}
            >
              <div className="flex items-center gap-3">
                <span className="text-2xl">{sys.icon}</span>
                <div>
                  <p className="text-sm font-medium text-white">{sys.name}</p>
                  <p className="text-[10px] text-zinc-500">{sys.category}</p>
                </div>
              </div>
              {isConnected ? (
                <button
                  onClick={() => connectedSys && handleDisconnect(connectedSys)}
                  disabled={disconnectingId === sys.id}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-red-500/10 hover:text-red-400 hover:border-red-500/20 transition-all"
                >
                  {disconnectingId === sys.id ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  )}
                  {disconnectingId === sys.id ? 'Disconnecting...' : 'Connected — Click to disconnect'}
                </button>
              ) : (
                <button
                  onClick={() => openConnectForm(sys)}
                  disabled={connectingId === sys.id}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium bg-violet-500/15 text-violet-300 border border-violet-500/30 hover:bg-violet-500/25 hover:border-violet-500/40 transition-all"
                >
                  {connectingId === sys.id ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Link2 className="w-3.5 h-3.5" />
                  )}
                  {connectingId === sys.id ? 'Connecting...' : 'Connect'}
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Inline Connect Form Modal */}
      {formOpen && formSystem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-zinc-900 p-6 shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-white flex items-center gap-2">
                <span className="text-xl">{formSystem.icon}</span>
                Connect {formSystem.name}
              </h3>
              <button
                onClick={() => { setFormOpen(false); setFormSystem(null); }}
                className="text-zinc-500 hover:text-white transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs text-zinc-400 mb-1">Display Name *</label>
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="My Shopify Store"
                  className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-violet-500/50"
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-400 mb-1">System URL *</label>
                <input
                  type="text"
                  value={formUrl}
                  onChange={(e) => setFormUrl(e.target.value)}
                  placeholder={formSystem.url_hint || 'https://api.example.com'}
                  className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-violet-500/50 font-mono"
                />
              </div>
              <div>
                <label className="block text-xs text-zinc-400 mb-1">API Key / Token (optional)</label>
                <input
                  type="password"
                  value={formApiKey}
                  onChange={(e) => setFormApiKey(e.target.value)}
                  placeholder="sk_••••••••••••"
                  className="w-full px-3 py-2 rounded-lg bg-white/5 border border-white/10 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-violet-500/50 font-mono"
                />
                <p className="text-[10px] text-zinc-600 mt-1">Stored securely in Superglue. Never exposed to the frontend.</p>
              </div>
            </div>

            <div className="flex gap-2 mt-5">
              <button
                onClick={() => { setFormOpen(false); setFormSystem(null); }}
                className="flex-1 px-4 py-2 rounded-lg text-xs font-medium bg-white/5 border border-white/10 text-zinc-400 hover:bg-white/10 transition-all"
              >
                Cancel
              </button>
              <button
                onClick={handleConnect}
                disabled={submitting || !formName.trim() || !formUrl.trim()}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-xs font-medium bg-violet-500/20 text-violet-300 border border-violet-500/40 hover:bg-violet-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <Plug className="w-3.5 h-3.5" />
                )}
                {submitting ? 'Connecting...' : 'Connect via Superglue'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
