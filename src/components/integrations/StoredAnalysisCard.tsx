'use client';

/**
 * StoredAnalysisCard — Shows CRM analysis results from onboarding in Dashboard
 *
 * Displays recommendations that were generated during onboarding so users
 * can continue to act on them after completing setup.
 *
 * Business Value:
 * - Persists onboarding insights into dashboard
 * - Reminds users of recommended integrations
 * - Tracks which recommendations were actioned
 *
 * Usage:
 * ```tsx
 * <StoredAnalysisCard companyId="xxx" onConnect={(key) => {}} />
 * ```
 */

import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Sparkles,
  RefreshCw,
  Plus,
  Users,
  ShoppingCart,
  BarChart3,
  Plug,
  CheckCircle2,
  Clock,
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────

interface Recommendation {
  integration_key: string;
  name: string;
  category: string;
  priority: 'high' | 'medium' | 'low';
  reason: string;
  business_impact: string;
  already_connected?: boolean;
}

interface StoredAnalysis {
  analysis_id: string;
  company_id: string;
  analyzed_at: string | null;
  connected_integrations: Array<{
    id: string;
    type: string;
    name: string;
    category: string;
  }>;
  data_profile: {
    total_contacts: number;
    total_orders: number;
    total_deals: number;
    has_products?: boolean;
    has_shipping_addresses?: boolean;
    has_payment_data?: boolean;
    [key: string]: any;
  };
  detected_gaps: Array<{
    id: string;
    category: string;
    severity: string;
    message: string;
    recommended: string[];
  }>;
  recommendations: Recommendation[];
  analysis_summary: string;
  is_actioned: boolean;
  actioned_at: string | null;
  is_stored: boolean;
}

// ── Component ───────────────────────────────────────────────────────────

interface StoredAnalysisCardProps {
  companyId?: string;
  onConnect?: (integrationKey: string) => void;
}

export function StoredAnalysisCard({ companyId, onConnect }: StoredAnalysisCardProps) {
  const [analysis, setAnalysis] = useState<StoredAnalysis | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch stored analysis on mount
  useEffect(() => {
    if (!companyId) {
      setIsLoading(false);
      return;
    }

    fetchStoredAnalysis();
  }, [companyId]);

  const fetchStoredAnalysis = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch('/api/integrations/analyze/stored', {
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error('Failed to fetch stored analysis');
      }

      const data = await response.json();

      if (data.success && data.analysis_id) {
        setAnalysis(data as StoredAnalysis);
      } else {
        setError(data.message || 'No stored analysis found');
      }
    } catch (err) {
      console.error('Failed to fetch stored analysis:', err);
      setError('Could not load your recommendations');
    } finally {
      setIsLoading(false);
    }
  };

  // Loading state
  if (isLoading) {
    return (
      <Card className="border-orange-500/20 bg-gradient-to-br from-orange-500/5 to-amber-500/5">
        <CardContent className="p-6">
          <div className="flex items-center gap-3">
            <RefreshCw className="w-5 h-5 animate-spin text-orange-400" />
            <div>
              <p className="text-sm font-medium text-white">Loading your recommendations...</p>
              <p className="text-xs text-zinc-500 mt-1">Retrieving analysis from onboarding</p>
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  // Error or no data state
  if (error || !analysis) {
    return null; // Don't show anything if no stored analysis
  }

  // Format date
  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return 'Unknown';
    try {
      const date = new Date(dateStr);
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return 'Unknown';
    }
  };

  // Get priority color config
  const getPriorityConfig = (priority: string) => {
    switch (priority) {
      case 'high':
        return {
          bg: 'bg-red-500/10 border-red-500/30',
          badge: 'bg-red-500/15 text-red-400 border-red-500/25',
          icon: '🔴',
        };
      case 'medium':
        return {
          bg: 'bg-amber-500/10 border-amber-500/30',
          badge: 'bg-amber-500/15 text-amber-400 border-amber-500/25',
          icon: '🟡',
        };
      case 'low':
        return {
          bg: 'bg-blue-500/10 border-blue-500/30',
          badge: 'bg-blue-500/15 text-blue-400 border-blue-500/25',
          icon: '🔵',
        };
      default:
        return {
          bg: 'bg-zinc-500/10 border-zinc-500/30',
          badge: 'bg-zinc-500/15 text-zinc-400 border-zinc-500/25',
          icon: '⚪',
        };
    }
  };

  // Filter out already-connected recommendations
  const actionableRecs = (analysis.recommendations || []).filter(
    (rec) => !rec.already_connected
  );

  return (
    <Card className={`border overflow-hidden ${analysis.is_actioned ? 'border-emerald-500/20' : 'border-orange-500/20'} bg-gradient-to-br ${analysis.is_actioned ? 'from-emerald-500/5 to-green-500/5' : 'from-orange-500/5 to-amber-500/5'}`}>
      {/* Header */}
      <div className="px-6 py-4 border-b border-white/[0.06] bg-white/[0.02]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500/20 to-amber-500/10 border border-orange-500/20 flex items-center justify-center">
              {analysis.is_actioned ? (
                <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              ) : (
                <Sparkles className="w-5 h-5 text-orange-400" />
              )}
            </div>
            <div>
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                Your Integration Recommendations
                {analysis.is_actioned && (
                  <Badge variant="secondary" className="bg-emerald-500/15 text-emerald-400 border-emerald-500/25 text-[10px] px-2 py-0.5">
                    Actioned
                  </Badge>
                )}
              </h3>
              <p className="text-xs text-zinc-500 mt-0.5 flex items-center gap-1.5">
                <Clock className="w-3 h-3" />
                Analyzed on {formatDate(analysis.analyzed_at)}
                {analysis.actioned_at && ` • Updated on ${formatDate(analysis.actioned_at)}`}
              </p>
            </div>
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={fetchStoredAnalysis}
            className="text-zinc-400 hover:text-white hover:bg-white/[0.05]"
          >
            <RefreshCw className="w-4 h-4 mr-1" />
            Refresh
          </Button>
        </div>
      </div>

      <CardContent className="p-6 space-y-5">
        {/* Data Profile Summary */}
        <div className="grid grid-cols-4 gap-3">
          <div className="rounded-lg bg-white/[0.03] p-3 text-center border border-white/[0.04]">
            <Users className="w-5 h-5 text-blue-400 mx-auto mb-1.5" />
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">Contacts</p>
            <p className="text-lg font-bold text-white">{analysis.data_profile?.total_contacts?.toLocaleString() || 0}</p>
          </div>
          <div className="rounded-lg bg-white/[0.03] p-3 text-center border border-white/[0.04]">
            <ShoppingCart className="w-5 h-5 text-green-400 mx-auto mb-1.5" />
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">Orders</p>
            <p className="text-lg font-bold text-white">{analysis.data_profile?.total_orders?.toLocaleString() || 0}</p>
          </div>
          <div className="rounded-lg bg-white/[0.03] p-3 text-center border border-white/[0.04]">
            <BarChart3 className="w-5 h-5 text-purple-400 mx-auto mb-1.5" />
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">Deals</p>
            <p className="text-lg font-bold text-white">{analysis.data_profile?.total_deals?.toLocaleString() || 0}</p>
          </div>
          <div className="rounded-lg bg-white/[0.03] p-3 text-center border border-white/[0.04]">
            <Plug className="w-5 h-5 text-orange-400 mx-auto mb-1.5" />
            <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-medium">Connected</p>
            <p className="text-lg font-bold text-white">{analysis.connected_integrations?.length || 0}</p>
          </div>
        </div>

        {/* Recommendations */}
        {actionableRecs.length > 0 ? (
          <div>
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-medium text-white">
                💡 Recommended for you ({actionableRecs.length})
              </p>
              {!analysis.is_actioned && (
                <span className="text-[10px] text-zinc-500">
                  From your onboarding analysis
                </span>
              )}
            </div>

            <div className="space-y-2.5">
              {actionableRecs.slice(0, 6).map((rec, idx) => {
                const config = getPriorityConfig(rec.priority);

                return (
                  <div
                    key={idx}
                    className={`rounded-xl border p-4 transition-all hover:bg-white/[0.02] ${config.bg}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1.5">
                          <span className="text-base">{config.icon}</span>
                          <span className="font-semibold text-white">
                            {rec.name || rec.integration_key}
                          </span>
                          <Badge 
                            variant="outline" 
                            className={`text-[9px] px-2 py-0.5 font-medium ${config.badge}`}
                          >
                            {rec.priority.toUpperCase()}
                          </Badge>
                        </div>
                        
                        <p className="text-sm text-zinc-300 leading-relaxed mb-2">
                          {rec.reason}
                        </p>
                        
                        {rec.business_impact && (
                          <p className="text-xs text-zinc-500 italic">
                            → {rec.business_impact}
                          </p>
                        )}
                      </div>

                      {onConnect && !rec.already_connected && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => onConnect(rec.integration_key)}
                          className="shrink-0 border-orange-500/30 text-orange-400 hover:bg-orange-500/10 hover:text-orange-300"
                        >
                          <Plus className="w-4 h-4 mr-1" />
                          Connect
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          /* All recommendations actioned */
          <div className="text-center py-8 rounded-xl bg-emerald-500/5 border border-emerald-500/20">
            <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto mb-3" />
            <p className="text-sm font-medium text-emerald-300 mb-1">
              All caught up! 🎉
            </p>
            <p className="text-xs text-zinc-500">
              You've connected all recommended integrations.
            </p>
          </div>
        )}

        {/* Analysis Summary */}
        {analysis.analysis_summary && (
          <div className="rounded-xl bg-white/[0.02] p-4 border border-white/[0.04]">
            <p className="text-xs text-zinc-400 uppercase tracking-wider font-medium mb-2">
              Summary
            </p>
            <p className="text-sm text-zinc-300 leading-relaxed">
              {analysis.analysis_summary}
            </p>
          </div>
        )}

        {/* Connected Integrations List */}
        {analysis.connected_integrations && analysis.connected_integrations.length > 0 && (
          <div>
            <p className="text-xs text-zinc-500 uppercase tracking-wider font-medium mb-2">
              Currently Connected ({analysis.connected_integrations.length})
            </p>
            <div className="flex flex-wrap gap-1.5">
              {analysis.connected_integrations.map((integ, idx) => (
                <Badge
                  key={idx}
                  variant="secondary"
                  className="bg-emerald-500/10 text-emerald-400 border-emerald-500/20 text-xs px-2.5 py-1"
                >
                  ✓ {integ.name || integ.type}
                </Badge>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default StoredAnalysisCard;
