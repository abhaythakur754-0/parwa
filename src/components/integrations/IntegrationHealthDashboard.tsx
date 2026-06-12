"use client";

import { useState, useEffect } from "react";
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RefreshCw,
  Loader2,
  Shield,
} from "lucide-react";

interface IntegrationHealth {
  integration_id: string;
  integration_name: string;
  status: string;
  last_tested_at: string | null;
  circuit_breaker: string;
  rate_limit: string;
}

interface HealthData {
  integrations: IntegrationHealth[];
  total: number;
  healthy: number;
  unhealthy: number;
}

export function IntegrationHealthDashboard() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadHealth();
  }, []);

  const loadHealth = async () => {
    try {
      const res = await fetch("/api/integrations/health");
      if (res.ok) {
        const data = await res.json();
        setHealth(data);
      }
    } catch {
      // Error handled silently
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadHealth();
    setRefreshing(false);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "active": return <CheckCircle2 className="h-4 w-4 text-emerald-400" />;
      case "error": return <XCircle className="h-4 w-4 text-red-400" />;
      case "disconnected": return <AlertTriangle className="h-4 w-4 text-amber-400" />;
      default: return <Activity className="h-4 w-4 text-zinc-500" />;
    }
  };

  const getCircuitBreakerBadge = (state: string) => {
    switch (state) {
      case "closed": return <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 uppercase tracking-wider">Closed (Healthy)</span>;
      case "open": return <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 uppercase tracking-wider">Open (Failing)</span>;
      case "half-open": return <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 uppercase tracking-wider">Half-Open (Testing)</span>;
      default: return <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.04] text-zinc-500 uppercase tracking-wider">{state}</span>;
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-10">
        <Loader2 className="w-5 h-5 animate-spin text-orange-400" />
      </div>
    );
  }

  const isHealthy = health && health.unhealthy === 0;
  const isDegraded = health && health.unhealthy > 0 && health.healthy > health.unhealthy;

  return (
    <div className="space-y-4">
      {/* Overall Health */}
      <div className="rounded-xl border border-orange-500/10 bg-[#1A1A1A] overflow-hidden">
        <div className="px-4 py-3 border-b border-white/[0.06] flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-orange-400" />
            <h3 className="text-sm font-semibold text-white">Integration Health</h3>
          </div>
          <div className="flex items-center gap-2">
            {!health || health.total === 0 ? (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.04] text-zinc-500 uppercase tracking-wider">No Integrations</span>
            ) : isHealthy ? (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 uppercase tracking-wider flex items-center gap-1"><CheckCircle2 className="w-3 h-3" /> Healthy</span>
            ) : isDegraded ? (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-400 uppercase tracking-wider flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> Degraded</span>
            ) : (
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 uppercase tracking-wider flex items-center gap-1"><XCircle className="w-3 h-3" /> Unhealthy</span>
            )}
            <button onClick={handleRefresh} className="h-7 w-7 rounded-lg flex items-center justify-center text-zinc-500 hover:text-white hover:bg-white/[0.04] transition-colors">
              <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>
        <div className="p-4">
          {health && health.total > 0 ? (
            <div className="flex gap-4 text-sm">
              <span className="text-emerald-400 font-medium">{health.healthy} healthy</span>
              <span className="text-red-400 font-medium">{health.unhealthy} unhealthy</span>
              <span className="text-zinc-500">{health.total} total</span>
            </div>
          ) : (
            <p className="text-sm text-zinc-500">No integrations connected yet.</p>
          )}
        </div>
      </div>

      {/* Per-Integration Health */}
      {health && health.integrations.length > 0 && (
        <div className="space-y-2">
          {health.integrations.map((ih) => (
            <div key={ih.integration_id} className="p-3 rounded-lg border border-white/[0.06] bg-white/[0.02]">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {getStatusIcon(ih.status)}
                  <span className="text-sm font-medium text-white">{ih.integration_name}</span>
                </div>
                {ih.status === "error" && (
                  <span className="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400">
                    <Shield className="h-3 w-3" />
                    Key may need rotation
                  </span>
                )}
              </div>
              <div className="flex items-center gap-3 text-xs">
                {getCircuitBreakerBadge(ih.circuit_breaker)}
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.04] text-zinc-500">
                  Rate limit: {ih.rate_limit}
                </span>
                {ih.last_tested_at && (
                  <span className="text-zinc-500">
                    Last tested: {new Date(ih.last_tested_at).toLocaleDateString()}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
