'use client';

import React, { useState, useEffect } from 'react';
import {
  Loader2, Sparkles, CheckCircle2, AlertTriangle,
  Lightbulb, Wrench, Bot, RefreshCw,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface Recommendation {
  name: string;
  reason?: string;
  priority?: string;
  category?: string;
}

interface AgentRecommendation {
  capability: string;
  reason: string;
  priority: string;
}

interface HealthStatus {
  name: string;
  status: string;
  healthy: boolean;
  message: string;
}

interface RecommendationsData {
  status: string;
  tickets_scanned: number;
  connected_integrations: any[];
  recommended_integrations: Recommendation[];
  recommended_agents: AgentRecommendation[];
  integration_health: HealthStatus[];
  analysis_summary: string;
}

interface RecommendationsPanelProps {
  companyId?: string;
}

export function RecommendationsPanel({ companyId }: RecommendationsPanelProps) {
  const [data, setData] = useState<RecommendationsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [crmStatus, setCrmStatus] = useState<string>('idle');
  const [crmRequestId, setCrmRequestId] = useState<string | null>(null);
  const [autoBuildStarted, setAutoBuildStarted] = useState(false);

  const fetchRecommendations = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/api/onboarding/recommendations');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  };

  // Start CRM analysis (called automatically when integration is connected)
  const startCRMAnalysis = async () => {
    try {
      setCrmStatus('starting');
      const res = await fetch('/api/onboarding/crm-analysis/start', {
        method: 'POST',
        credentials: 'include',
      });
      if (res.ok) {
        const json = await res.json();
        if (json.request_id) {
          setCrmRequestId(json.request_id);
          setCrmStatus('processing');
        }
      }
    } catch {
      setCrmStatus('idle');
    }
  };

  // Poll CRM analysis status
  useEffect(() => {
    if (!crmRequestId) return;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/onboarding/crm-analysis/status?id=${crmRequestId}`, {
          credentials: 'include',
        });
        if (res.ok) {
          const json = await res.json();
          if (json.status === 'completed') {
            setCrmStatus('completed');
            setCrmRequestId(null);
            // Refresh recommendations with new CRM data
            fetchRecommendations();
          } else if (json.status === 'failed') {
            setCrmStatus('failed');
            setCrmRequestId(null);
          }
        }
      } catch {
        // Keep polling
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [crmRequestId]);

  // Auto-start builder when CRM analysis completes
  useEffect(() => {
    if (crmStatus === 'completed' && !autoBuildStarted) {
      setAutoBuildStarted(true);
      // Trigger agent builder (checks if agents exist first — skips if they do)
      fetch('/api/builder-agent/build-from-onboarding', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ force_rebuild: false }),
      }).catch(() => {
        // Non-blocking — builder runs in background
      });
    }
  }, [crmStatus, autoBuildStarted]);

  useEffect(() => {
    fetchRecommendations();
  }, [companyId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-4 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Analyzing your tickets and integrations...
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4 text-sm text-muted-foreground">
        <AlertTriangle className="inline h-4 w-4 mr-1" />
        Could not load recommendations. You can still connect integrations manually.
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="space-y-4">
      {/* Summary */}
      {data.analysis_summary && (
        <div className="rounded-lg bg-blue-50 dark:bg-blue-950/20 p-4 border border-blue-200 dark:border-blue-800">
          <div className="flex items-start gap-2">
            <Lightbulb className="h-5 w-5 text-blue-500 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-medium text-blue-900 dark:text-blue-100">
                AI Analysis ({data.tickets_scanned} tickets scanned)
              </p>
              <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
                {data.analysis_summary}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Recommended Integrations */}
      {data.recommended_integrations.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-amber-500" />
            Recommended Integrations
          </h3>
          <div className="space-y-2">
            {data.recommended_integrations.slice(0, 5).map((rec, i) => (
              <div
                key={i}
                className="flex items-start gap-3 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm">{rec.name}</span>
                    {rec.priority === 'high' && (
                      <span className="text-xs px-1.5 py-0.5 rounded bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-200">
                        High Priority
                      </span>
                    )}
                  </div>
                  {rec.reason && (
                    <p className="text-xs text-muted-foreground mt-1">{rec.reason}</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommended Agents */}
      {data.recommended_agents.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
            <Bot className="h-4 w-4 text-purple-500" />
            Recommended AI Agents
          </h3>
          <div className="space-y-2">
            {data.recommended_agents.map((agent, i) => (
              <div
                key={i}
                className="flex items-start gap-3 p-3 rounded-lg border bg-card"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-sm capitalize">
                      {agent.capability.replace(/_/g, ' ')}
                    </span>
                    <span
                      className={cn(
                        'text-xs px-1.5 py-0.5 rounded',
                        agent.priority === 'high'
                          ? 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-200'
                          : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-200'
                      )}
                    >
                      {agent.priority}
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{agent.reason}</p>
                </div>
              </div>
            ))}
          </div>
          <p className="text-xs text-muted-foreground mt-2">
            These agents will be built automatically in Step 3 using your connected integrations.
          </p>
        </div>
      )}

      {/* Integration Health */}
      {data.integration_health.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-2 flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-green-500" />
            Connected Integrations Health
          </h3>
          <div className="space-y-1">
            {data.integration_health.map((health, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                {health.healthy ? (
                  <CheckCircle2 className="h-4 w-4 text-green-500" />
                ) : (
                  <AlertTriangle className="h-4 w-4 text-yellow-500" />
                )}
                <span className="font-medium">{health.name}</span>
                <span className="text-muted-foreground text-xs">— {health.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Refresh button */}
      <button
        onClick={fetchRecommendations}
        className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1"
      >
        <RefreshCw className="h-3 w-3" />
        Refresh analysis
      </button>
    </div>
  );
}
