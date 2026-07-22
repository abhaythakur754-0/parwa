'use client';

/**
 * CRMAnalyzerCard — Smart Integration Recommendations
 *
 * Analyzes connected CRM data and recommends which integrations to add next.
 * Uses LLM-powered analysis for personalized suggestions.
 *
 * Business Value:
 * - Reduces user confusion about which integrations they need
 * - Increases activation rate (more integrations = more value)
 * - Personalized recommendations based on actual data patterns
 *
 * Usage:
 * ```tsx
 * <CRMAnalyzerCard companyId="xxx" onConnect={(key) => {}} />
 * ```
 */

import React, { useState, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Plus,
  RefreshCw,
  Zap,
  TrendingUp,
  ShoppingCart,
  Truck,
  CreditCard,
  Mail,
  MessageSquare,
  BarChart3,
  Users,
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────

interface DataProfile {
  total_contacts: number;
  total_orders: number;
  total_deals: number;
  has_products: boolean;
  has_shipping_addresses: boolean;
  has_payment_data: boolean;
  has_email_campaigns: boolean;
  has_ticket_data: boolean;
  industries_detected: string[];
}

interface Recommendation {
  integration_key: string;
  name: string;
  category: string;
  priority: 'high' | 'medium' | 'low';
  reason: string;
  business_impact: string;
  icon_id?: string;
  color_gradient?: string;
  already_connected: boolean;
}

interface DetectedGap {
  id: string;
  condition: boolean;
  category: string;
  severity: string;
  message: string;
  recommended: string[];
}

interface AnalysisResult {
  company_id: string;
  analyzed_at: string;
  connected_integrations: Array<{
    id: string;
    type: string;
    name: string;
    category: string;
    connected_at?: string;
  }>;
  data_profile: DataProfile;
  detected_gaps: DetectedGap[];
  recommendations: Recommendation[];
  analysis_summary: string;
}

// ── Category Icons ─────────────────────────────────────────────────────

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  payments: <CreditCard className="h-4 w-4" />,
  shipping: <Truck className="h-4 w-4" />,
  marketing: <Mail className="h-4 w-4" />,
  helpdesk: <MessageSquare className="h-4 w-4" />,
  analytics: <BarChart3 className="h-4 w-4" />,
  communication: <MessageSquare className="h-4 w-4" />,
  crm: <Users className="h-4 w-4" />,
  ecommerce: <ShoppingCart className="h-4 w-4" />,
};

// ── Priority Colors ────────────────────────────────────────────────────

const PRIORITY_STYLES: Record<string, { bg: string; text: string; border: string; badge: string }> = {
  high: {
    bg: 'bg-red-950/30',
    text: 'text-red-400',
    border: 'border-red-900/50',
    badge: 'bg-red-500/20 text-red-300 border-red-500/30',
  },
  medium: {
    bg: 'bg-amber-950/30',
    text: 'text-amber-400',
    border: 'border-amber-900/50',
    badge: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  },
  low: {
    bg: 'bg-blue-950/30',
    text: 'text-blue-400',
    border: 'border-blue-900/50',
    badge: 'bg-blue-500/20 text-blue-300 border-blue-500/30',
  },
};

// ── Component ──────────────────────────────────────────────────────────

interface CRMAnalyzerCardProps {
  companyId?: string;
  onConnect?: (integrationKey: string) => void;
  compact?: boolean;
}

export function CRMAnalyzerCard({ 
  companyId, 
  onConnect,
  compact = false 
}: CRMAnalyzerCardProps) {
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  const runAnalysis = useCallback(async () => {
    if (!companyId) return;

    setLoading(true);
    setError(null);
    setAnalyzing(true);

    try {
      const response = await fetch('/api/integrations/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Analysis failed: ${response.statusText}`);
      }

      const result: AnalysisResult = await response.json();
      setAnalysis(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to analyze integrations');
    } finally {
      setLoading(false);
      setAnalyzing(false);
    }
  }, [companyId]);

  // Auto-run on mount if companyId provided
  React.useEffect(() => {
    if (companyId && !analysis && !loading) {
      runAnalysis();
    }
  }, [companyId, analysis, loading, runAnalysis]);

  // ── Loading State ───────────────────────────────────────────────

  if (loading && !analysis) {
    return (
      <Card className="border-zinc-800 bg-zinc-900/50">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-purple-400 animate-pulse" />
            <CardTitle className="text-lg">Analyzing Your Setup...</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-20 w-full bg-zinc-800" />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <Skeleton className="h-24 w-full bg-zinc-800" />
            <Skeleton className="h-24 w-full bg-zinc-800" />
          </div>
        </CardContent>
      </Card>
    );
  }

  // ── Error State ─────────────────────────────────────────────────

  if (error) {
    return (
      <Alert variant="destructive" className="border-red-900/50 bg-red-950/20">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription className="flex items-center justify-between">
          <span>{error}</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={runAnalysis}
            className="text-red-400 hover:text-red-300"
          >
            <RefreshCw className="h-4 w-4 mr-1" />
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  // ── No Analysis Yet ────────────────────────────────────────────

  if (!analysis) {
    return (
      <Card 
        className="border-dashed border-purple-900/50 bg-gradient-to-br from-purple-950/20 to-zinc-900/50 cursor-pointer hover:border-purple-700/50 transition-colors"
        onClick={runAnalysis}
      >
        <CardContent className="flex flex-col items-center justify-center py-8 gap-3">
          <div className="p-3 rounded-full bg-purple-500/10">
            <Sparkles className="h-8 w-8 text-purple-400" />
          </div>
          <div className="text-center">
            <p className="font-medium text-white">Get Smart Integration Recommendations</p>
            <p className="text-sm text-zinc-500 mt-1">
              Let Parwa analyze your data and tell you exactly which integrations you need
            </p>
          </div>
          <Button variant="outline" size="sm" className="border-purple-700 text-purple-400 hover:bg-purple-950/30">
            <Zap className="h-4 w-4 mr-1" />
            Analyze My Setup
          </Button>
        </CardContent>
      </Card>
    );
  }

  // ── Results View ────────────────────────────────────────────────

  const highPriorityRecs = analysis.recommendations.filter(r => r.priority === 'high' && !r.already_connected);
  const mediumPriorityRecs = analysis.recommendations.filter(r => r.priority === 'medium' && !r.already_connected);
  const lowPriorityRecs = analysis.recommendations.filter(r => r.priority === 'low' && !r.already_connected);

  return (
    <div className="space-y-4">
      {/* Header */}
      {!compact && (
        <Card className="border-zinc-800 bg-zinc-900/50">
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-purple-400" />
                  <CardTitle className="text-lg">Integration Health Check</CardTitle>
                </div>
                <CardDescription className="text-sm">{analysis.analysis_summary}</CardDescription>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={runAnalysis}
                disabled={analyzing}
                className="text-zinc-400 hover:text-white"
              >
                <RefreshCw className={`h-4 w-4 ${analyzing ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </CardHeader>

          {/* Data Profile Summary */}
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <DataPoint label="Contacts" value={analysis.data_profile.total_contacts} icon={<Users className="h-3.5 w-3.5" />} />
              <DataPoint label="Orders" value={analysis.data_profile.total_orders} icon={<ShoppingCart className="h-3.5 w-3.5" />} />
              <DataPoint label="Deals" value={analysis.data_profile.total_deals} icon={<TrendingUp className="h-3.5 w-3.5" />} />
              <DataPoint label="Connected" value={analysis.connected_integrations.length} icon={<CheckCircle2 className="h-3.5 w-3.5" />} />
            </div>
          </CardContent>
        </Card>
      )}

      {/* High Priority Recommendations */}
      {highPriorityRecs.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium text-red-400">
            <AlertTriangle className="h-4 w-4" />
            Urgent Recommendations ({highPriorityRecs.length})
          </div>
          <div className="grid gap-3">
            {highPriorityRecs.map((rec) => (
              <RecommendationCard
                key={rec.integration_key}
                recommendation={rec}
                onConnect={() => onConnect?.(rec.integration_key)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Medium Priority Recommendations */}
      {mediumPriorityRecs.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2 text-sm font-medium text-amber-400">
            <Zap className="h-4 w-4" />
            Suggested Improvements ({mediumPriorityRecs.length})
          </div>
          <div className="grid gap-3">
            {mediumPriorityRecs.map((rec) => (
              <RecommendationCard
                key={rec.integration_key}
                recommendation={rec}
                onConnect={() => onConnect?.(rec.integration_key)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Low Priority / Optional */}
      {!compact && lowPriorityRecs.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer list-none flex items-center gap-2 text-sm font-medium text-zinc-400 hover:text-zinc-200 transition-colors">
            <BarChart3 className="h-4 w-4" />
            Optional Enhancements ({lowPriorityRecs.length})
            <span className="text-xs text-zinc-600">(click to expand)</span>
          </summary>
          <div className="mt-2 grid gap-3 pl-6">
            {lowPriorityRecs.map((rec) => (
              <RecommendationCard
                key={rec.integration_key}
                recommendation={rec}
                onConnect={() => onConnect?.(rec.integration_key)}
                compact
              />
            ))}
          </div>
        </details>
      )}

      {/* All Good State */}
      {highPriorityRecs.length === 0 && mediumPriorityRecs.length === 0 && (
        <Card className="border-green-900/50 bg-green-950/10">
          <CardContent className="flex items-center gap-3 py-4">
            <CheckCircle2 className="h-5 w-5 text-green-400" />
            <div>
              <p className="font-medium text-green-300">Your Integration Setup Looks Great!</p>
              <p className="text-sm text-zinc-500 mt-0.5">
                No critical gaps detected. You have {analysis.connected_integrations.length} integration(s) connected.
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────

function DataPoint({ 
  label, 
  value, 
  icon 
}: { 
  label: string; 
  value: number; 
  icon: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2 p-2 rounded-lg bg-zinc-800/50">
      <span className="text-zinc-500">{icon}</span>
      <div>
        <p className="text-lg font-semibold text-white">{value.toLocaleString()}</p>
        <p className="text-xs text-zinc-500">{label}</p>
      </div>
    </div>
  );
}

function RecommendationCard({
  recommendation,
  onConnect,
  compact = false,
}: {
  recommendation: Recommendation;
  onConnect: () => void;
  compact?: boolean;
}) {
  const styles = PRIORITY_STYLES[recommendation.priority] || PRIORITY_STYLES.low;
  const icon = CATEGORY_ICONS[recommendation.category] || <Plus className="h-4 w-4" />;

  return (
    <Card className={`${styles.bg} ${styles.border} border`}>
      <CardContent className={`p-4 ${compact ? '' : 'p-4'}`}>
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <div className={`p-2 rounded-lg ${styles.badge} border mt-0.5`}>
              {icon}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h4 className="font-medium text-white truncate">{recommendation.name}</h4>
                <Badge variant="outline" className={`${styles.badge} text-xs capitalize`}>
                  {recommendation.priority}
                </Badge>
                <Badge variant="outline" className="text-xs border-zinc-700 text-zinc-400 capitalize">
                  {recommendation.category}
                </Badge>
              </div>
              {!compact && (
                <>
                  <p className="text-sm text-zinc-400 mt-1">{recommendation.reason}</p>
                  <p className="text-xs text-zinc-500 mt-0.5 italic">{recommendation.business_impact}</p>
                </>
              )}
            </div>
          </div>
          <Button
            size="sm"
            onClick={onConnect}
            disabled={recommendation.already_connected}
            className={`shrink-0 ${
              recommendation.already_connected
                ? 'bg-green-900/30 text-green-400 border-green-800 cursor-default'
                : 'bg-purple-600 hover:bg-purple-500 text-white'
            }`}
          >
            {recommendation.already_connected ? (
              <>
                <CheckCircle2 className="h-3.5 w-3.5 mr-1" />
                Connected
              </>
            ) : (
              <>
                <Plus className="h-3.5 w-3.5 mr-1" />
                Connect
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default CRMAnalyzerCard;
